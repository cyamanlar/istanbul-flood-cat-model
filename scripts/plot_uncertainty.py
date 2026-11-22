"""Tornado chart of the 1-in-200 loss across assumptions -> outputs/figures/07_uncertainty_tornado.png

    python scripts/sensitivity_uncertainty.py && python scripts/bias_sensitivity.py 1.4 1.8 2.2
    python scripts/plot_uncertainty.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from src.plots import NAVY, ORANGE, GREY  # noqa: E402

s = pd.read_csv("outputs/tables/sensitivity_uncertainty.csv").set_index("case")
base = s.loc["Base (50,000 years)", "L200_m"]
port = s[s.index.str.startswith("Portfolio realisation")]["L200_m"].tolist() + [base]
seed = s[s.index.str.startswith("Hazard sampling")]["L200_m"].tolist() + [base]
bars = [
    ("ERA5 bias factors P5 / P95 (x0.89 / x1.13)", s.loc["ERA5 bias factors at P5 (x0.89)", "L200_m"], s.loc["ERA5 bias factors at P95 (x1.13)", "L200_m"]),
    ("Portfolio realisation (6 draws)", min(port), max(port)),
    ("Drainage capacity -20% / +20%", s.loc["Drainage capacity, flood-prone zone 84 mm (+20%)", "L200_m"],
     s.loc["Drainage capacity, flood-prone zone 56 mm (-20%)", "L200_m"]),
    ("Depth coefficient -20% / +20%", s.loc["Depth coefficient -20%", "L200_m"], s.loc["Depth coefficient +20%", "L200_m"]),
    ("Correlation length 20 / 60 km", s.loc["Correlation length 20 km (radar, 2009 event)", "L200_m"], s.loc["Correlation length 60 km (v0.2 value)", "L200_m"]),
    ("Secondary uncertainty CV 0 / 0.8", s.loc["No secondary uncertainty", "L200_m"], s.loc["Secondary uncertainty CV 0.8", "L200_m"]),
    ("GEV shape: cell-by-cell", s.loc["Cell-by-cell GEV shape (no regional shape)", "L200_m"], base),
    ("Rainfall cap 300 / 600 mm", s.loc["Rainfall cap 300 mm/day", "L200_m"], s.loc["Rainfall cap 600 mm/day", "L200_m"]),
    ("Hazard sampling seed (4 draws)", min(seed), max(seed)),
]
bars.sort(key=lambda r: r[2] - r[1])
fig, ax = plt.subplots(figsize=(8, 4.6))
for i, (lab, lo, hi) in enumerate(bars):
    ax.barh(i, hi - lo, left=lo, color=NAVY if i >= len(bars) - 2 else GREY, alpha=0.85)
    ax.text(hi + 0.8, i, f"{lo:.0f}–{hi:.0f}", va="center", fontsize=8)
ax.axvline(base, color=ORANGE, lw=2)
ax.text(base, len(bars) - 0.35, f" base {base:.0f}", color=ORANGE, fontsize=8)
ax.set_yticks(range(len(bars)), [r[0] for r in bars], fontsize=8)
ax.set(xlabel="1-in-200 gross loss (EUR m)",
       title="What drives the 1-in-200 loss? (v0.3)")
fig.tight_layout()
fig.savefig("outputs/figures/07_uncertainty_tornado.png", dpi=130)
print("saved")
