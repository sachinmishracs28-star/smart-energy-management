# GreenGrid: AIoT Smart Energy Management for Green Buildings (macOS)

## Quick start (MacBook, Apple Silicon or Intel)
1. Open Terminal in this folder (right-click folder > New Terminal at Folder).
2. Run:

       chmod +x run.command
       ./run.command

   It creates a virtual environment, installs Flask, scikit-learn and numpy, starts the server
   and opens http://127.0.0.1:5001 in your browser. Stop it with Ctrl+C.

If macOS blocks double-clicking run.command: System Settings > Privacy & Security > Open Anyway,
or just use Terminal as above.

## Manual run
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python app.py

## Notes for Mac
- Port 5001 is used on purpose: macOS AirPlay Receiver occupies port 5000 and causes a 403 error.
- No Python? Install with `brew install python` or from python.org (3.9 or newer).
- Chart.js loads from a CDN, so the first page load needs internet.
- First run creates energy.db with 14 days of simulated history and trains the model.
  Delete energy.db to reset the data.

## Architecture
Simulated sensors (simulator.py) -> gateway thread writes every 5 s -> SQLite (energy.db)
-> Flask REST API (app.py) + scikit-learn RandomForest (ml_model.py) -> dashboard (HTML/CSS/JS + Chart.js)

## API
GET /api/latest, /api/history?room=, /api/forecast?room=, /api/summary; POST /api/retrain

## Assumptions
Tariff Rs 8/kWh, grid emission 0.82 kg CO2/kWh, solar peak 6 kW. Edit in app.py / simulator.py.

## Replace simulation with real hardware
Make an ESP32 with DHT22 + PIR + LDR POST JSON to a new /api/ingest route that calls save().
