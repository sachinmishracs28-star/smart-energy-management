"""Simulated IoT sensors: each room 'publishes' temperature, occupancy,
daylight (lux), solar generation and power use, like real sensors would."""
import math, random

ROOMS = {
    "Classroom": {"base": 1.2, "cap": 60},
    "Lab":       {"base": 2.5, "cap": 40},
    "Library":   {"base": 1.5, "cap": 80},
    "Office":    {"base": 1.0, "cap": 25},
}

def outdoor_temp(h):            # peaks around 3 pm
    return 29 + 7 * math.sin((h - 9) * 2 * math.pi / 24)

def occ_fraction(h):            # typical college timetable
    if 9 <= h < 17: return 0.7
    if 17 <= h < 20: return 0.2
    return 0.0

def solar_total_kw(h):          # rooftop panel, whole building, peak 6 kW
    return 6.0 * math.sin(math.pi * (h - 6) / 12) if 6 <= h <= 18 else 0.0

def expected(h, room):
    """Typical temperature & occupancy for an hour (used for forecasting)."""
    occ = int(ROOMS[room]["cap"] * occ_fraction(h))
    return round(0.5 * outdoor_temp(h) + 12 + occ * 0.03, 1), occ

def _power(room, temp, occ, lux):
    base, cap = ROOMS[room]["base"], ROOMS[room]["cap"]
    active = occ > 1
    p = base * (0.3 + 0.7 * occ / cap)                                   # equipment
    p += max(0, temp - 24) * 0.1 * base * (1 if active else 0.2)         # cooling
    p += base * 0.3 * (1 - min(lux, 500) / 500) * (1 if active else 0.3) # lighting
    return p + random.gauss(0, 0.05 * base)

def make_reading(room, ts):
    h = ts.hour
    f = occ_fraction(h)
    occ = int(ROOMS[room]["cap"] * f * random.uniform(0.7, 1.3)) if f else 0
    temp = 0.5 * outdoor_temp(h) + 12 + occ * 0.03 + random.gauss(0, 0.4)
    lux = 900 * math.sin(math.pi * (h - 6) / 12) * random.uniform(0.8, 1.0) if 6 <= h <= 18 else 0
    power = _power(room, temp, occ, lux)
    if occ <= 1 and random.random() < 0.08:      # someone forgot to switch off
        power += 0.8
    solar = solar_total_kw(h) / len(ROOMS) * random.uniform(0.85, 1.0)
    return {"ts": ts.strftime("%Y-%m-%d %H:%M:%S"), "room": room, "hour": h,
            "temperature": round(temp, 1), "occupancy": occ, "lux": round(lux),
            "energy": round(max(power, 0.05), 2), "solar": round(solar, 2)}
