import os, sqlite3, threading, time
from contextlib import contextmanager
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request
import simulator as sim
import ml_model as ml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("ENERGY_DB_PATH", os.path.join(BASE_DIR, "energy.db"))
TARIFF = 8.0     # Rs per kWh (assumption)
CO2 = 0.82       # kg CO2 per kWh grid electricity (approx. India average)
app = Flask(__name__)

@contextmanager
def db():
    # Close every connection deterministically and wait for concurrent writers.
    c = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

# Serialize simulator writes within this application process.
_write_lock = threading.Lock()

def save(c, r):
    c.execute("INSERT INTO readings(ts,room,hour,temperature,occupancy,lux,energy,solar) "
              "VALUES(:ts,:room,:hour,:temperature,:occupancy,:lux,:energy,:solar)", r)

def init_db():
    # WAL allows dashboard reads while the simulator writes new readings.
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("""CREATE TABLE IF NOT EXISTS readings(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, room TEXT, hour INTEGER,
            temperature REAL, occupancy INTEGER, lux REAL, energy REAL, solar REAL)""")
        if c.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 0:
            start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=14)
            for i in range(14 * 24):                       # 14 days of hourly history
                for room in sim.ROOMS:
                    save(c, sim.make_reading(room, start + timedelta(hours=i)))
    train_model()

def train_model():
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 5000")]
    ml.train(rows)

def live_loop():                       # the "IoT gateway": new readings every 5 s
    while True:
        now = datetime.now()
        try:
            with _write_lock:
                with db() as c:
                    for room in sim.ROOMS:
                        save(c, sim.make_reading(room, now))
        except sqlite3.OperationalError:
            # A transient lock should not permanently stop simulated readings.
            app.logger.exception("Temporary SQLite write issue in simulator")
        time.sleep(5)

def is_waste(r):
    return r["occupancy"] <= 1 and r["energy"] > 0.6 * sim.ROOMS[r["room"]]["base"]

def latest_rows():
    with db() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM readings WHERE id IN (SELECT MAX(id) FROM readings GROUP BY room)")]
    for r in rows:
        r["predicted"] = ml.predict([(r["hour"], r["temperature"], r["occupancy"], r["room"])])[0]
        r["status"] = ("waste" if is_waste(r)
                       else "high" if r["energy"] > 1.3 * r["predicted"] else "normal")
    return sorted(rows, key=lambda r: r["room"])

def alerts(rows):
    out = []
    for r in rows:
        if r["status"] == "waste":
            out.append(("danger", f"{r['room']} is empty but using {r['energy']} kW. Switch off lights and AC."))
        elif r["status"] == "high":
            out.append(("warning", f"{r['room']} uses {r['energy']} kW, above the forecast of {r['predicted']} kW."))
        if r["temperature"] > 30 and r["occupancy"] > 5:
            out.append(("warning", f"{r['room']} is at {r['temperature']} °C with people inside. Check cooling and ventilation."))
        if r["solar"] > 1.2:
            out.append(("info", f"Solar is strong ({r['solar']} kW per room). Run heavy loads like lab equipment now."))
            break
    return out or [("ok", "All rooms are running normally.")]

@app.route("/")
def index():
    return render_template("index.html", rooms=list(sim.ROOMS))

@app.route("/api/latest")
def api_latest():
    return jsonify(latest_rows())

@app.route("/api/history")
def api_history():
    room = request.args.get("room", "All")
    with db() as c:
        if room == "All":
            q = c.execute("SELECT ts, SUM(energy) energy, SUM(solar) solar, AVG(temperature) temperature, "
                          "SUM(occupancy) occupancy FROM readings GROUP BY ts ORDER BY ts DESC LIMIT 60")
        else:
            q = c.execute("SELECT * FROM readings WHERE room=? ORDER BY id DESC LIMIT 60", (room,))
        rows = [dict(r) for r in q][::-1]
    return jsonify([{"t": r["ts"][11:19], "energy": round(r["energy"], 2), "solar": round(r["solar"], 2),
                     "temperature": round(r["temperature"], 1), "occupancy": r["occupancy"]} for r in rows])

@app.route("/api/forecast")
def api_forecast():
    room = request.args.get("room", "All")
    rooms = list(sim.ROOMS) if room == "All" else [room]
    now = datetime.now().replace(minute=0)
    labels, demand, solar = [], [], []
    for i in range(24):
        h = (now + timedelta(hours=i)).hour
        items = [(h, *sim.expected(h, rm), rm) for rm in rooms]
        demand.append(round(sum(ml.predict(items)), 2))
        solar.append(round(sim.solar_total_kw(h) * len(rooms) / len(sim.ROOMS), 2))
        labels.append(f"{h:02d}:00")
    grid = [round(max(d - so, 0), 2) for d, so in zip(demand, solar)]
    hourly_cost = [round(g * TARIFF, 2) for g in grid]
    hourly_co2 = [round(g * CO2, 2) for g in grid]
    return jsonify({"labels": labels, "demand": demand, "solar": solar,
                    "grid": grid, "hourly_cost": hourly_cost, "hourly_co2": hourly_co2,
                    "tariff": TARIFF, "grid_co2_factor": CO2})

@app.route("/api/summary")
def api_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM readings WHERE ts LIKE ?", (today + "%",))]
    buckets = {}                                   # average kW per (hour, room) = kWh
    for r in rows:
        b = buckets.setdefault((r["hour"], r["room"]), [0, 0, 0])
        b[0] += r["energy"]; b[1] += r["solar"]; b[2] += 1
    total = sum(b[0] / b[2] for b in buckets.values())
    solar = sum(b[1] / b[2] for b in buckets.values())
    grid = max(total - solar, 0)
    waste_ratio = sum(is_waste(r) for r in rows) / max(len(rows), 1)
    score = round(100 * (0.5 * min(1, solar / max(total, 0.1) * 2) + 0.5 * (1 - min(1, waste_ratio * 5))))
    rl = latest_rows()
    return jsonify({"total_kwh": round(total, 1), "solar_kwh": round(solar, 1), "grid_kwh": round(grid, 1),
                    "cost": round(grid * TARIFF), "co2_saved": round(solar * CO2, 1),
                    "score": score, "alerts": alerts(rl), "model": ml.metrics})

@app.route("/api/retrain", methods=["POST"])
def api_retrain():
    train_model()
    return jsonify(ml.metrics)

# Initialize data and start the simulated IoT gateway when the app is imported by
# either the local Python runner or a production WSGI server such as Gunicorn.
init_db()
_gateway = threading.Thread(target=live_loop, daemon=True, name="simulated-iot-gateway")
_gateway.start()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
