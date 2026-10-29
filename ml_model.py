"""Energy prediction: RandomForest learns power use from hour, temperature,
occupancy and room."""
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from simulator import ROOMS

NAMES = list(ROOMS)
model = None
metrics = {}

def _x(hour, temp, occ, room):
    return [hour, temp, occ, NAMES.index(room)]

def train(rows):
    global model
    X = np.array([_x(r["hour"], r["temperature"], r["occupancy"], r["room"]) for r in rows])
    y = np.array([r["energy"] for r in rows])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, random_state=42).fit(Xtr, ytr)
    pred = model.predict(Xte)
    metrics.update(mae=round(float(mean_absolute_error(yte, pred)), 3),
                   r2=round(float(r2_score(yte, pred)), 3), samples=len(X))

def predict(items):
    """items = [(hour, temp, occupancy, room), ...] -> list of kW"""
    return model.predict(np.array([_x(*i) for i in items])).round(2).tolist()
