"""Export the compact data the browser simulator needs -> docs/simulator/model_data.json

    python run_model.py && python scripts/build_simulator_data.py
The simulator (docs/simulator/index.html) re-runs a simplified version of the
portfolio model in the browser: same GEV parameters, portfolio, rainfall-depth
transfer and JRC damage curves; mean damage ratio (no secondary uncertainty).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from src import exposure, hazard  # noqa: E402
from src.vulnerability import DAMAGE_CURVES, DEPTH_M, FIRST_FLOOR_M  # noqa: E402

cfg = json.load(open("config.json", encoding="utf-8"))
cells = hazard.grid_cells()
amax, synthetic = hazard.load_annual_max(cfg, cells, None)
gev = hazard.fit_cells(amax, regional_shape=cfg["hazard"].get("regional_shape", True))
loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))
ci = pd.Index(gev.cell_id).get_indexer(loc.cell_id)
occ = {"residential": 0, "commercial": 1, "industrial": 2}
districts = sorted(loc.district.unique())
d = {
    "meta": {"hazard": "SYNTHETIC" if synthetic else "ERA5 1950-2025", "bias_factor_base": 1.0, "bias_zonal": cfg["hazard"].get("bias_correction"),
             "cap_mm": cfg["hazard"].get("max_daily_rain_mm", 400), "corr_km": cfg["hazard"]["corr_length_km"],
             "cc_rate": cfg["hazard"]["climate_scaling_per_degC"], "deductible": cfg["financial"]["deductible_pct_tiv"],
             "vuln": cfg["vulnerability"], "tiv_total": float(loc.TIV.sum())},
    "cells": {"lat": gev.lat.round(3).tolist(), "lon": gev.lon.round(3).tolist(), "xi": gev.xi.round(4).tolist(),
              "alpha": gev.alpha.round(4).tolist(), "k": gev.k.round(5).tolist()},
    "curves": {"depth": DEPTH_M.tolist(), "res": DAMAGE_CURVES["residential"].tolist(),
               "com": DAMAGE_CURVES["commercial"].tolist(), "ind": DAMAGE_CURVES["industrial"].tolist(),
               "ffh": [FIRST_FLOOR_M["residential"], FIRST_FLOOR_M["commercial"], FIRST_FLOOR_M["industrial"]]},
    "districts": districts,
    "loc": {"cell": ci.tolist(), "occ": loc.occupancy.map(occ).tolist(), "prone": loc.flood_prone.astype(int).tolist(),
            "amp": loc.local_amp.round(3).tolist(), "tiv": (loc.TIV / 1e3).round(1).tolist(),
            "dist": [districts.index(x) for x in loc.district], "u": np.random.default_rng(7).uniform(size=len(loc)).round(4).tolist()},
    "prone_share": dict(zip(exposure.districts_df().district, exposure.districts_df().prone_class.map(exposure.PRONE_SHARE))),
}
os.makedirs("docs/simulator", exist_ok=True)
json.dump(d, open("docs/simulator/model_data.json", "w"), separators=(",", ":"))
print("locations", len(loc), "bytes", os.path.getsize("docs/simulator/model_data.json"))
