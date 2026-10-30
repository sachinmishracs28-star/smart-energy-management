#!/bin/bash
# Double-click this file on macOS (or run ./run.command) to start GreenGrid.
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install it with: brew install python  (or from python.org)"; exit 1
fi
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
(sleep 3 && open http://127.0.0.1:5001) &
python app.py
