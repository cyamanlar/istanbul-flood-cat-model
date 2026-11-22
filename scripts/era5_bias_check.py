"""
How well does ERA5 see Istanbul's extreme rainfall?  -> sets bias_correction_factor

Compares ERA5 annual-maximum daily rainfall (0.25 deg cells, 1950-2025) with
  (a) MGM station all-time daily records (official climate statistics), and
  (b) station totals of the 8-9 September 2009 flash flood.
ERA5 is an area average over ~25 x 30 km and smooths convective peaks, so
station (point) extremes are systematically higher.

    python scripts/era5_bias_check.py
Outputs: outputs/tables/era5_vs_stations.csv, outputs/figures/06_era5_vs_stations.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from src.gev import fit_gev_lmom, return_level  # noqa: E402
from src.plots import NAVY, ORANGE, RED, GREY  # noqa: E402


def nearest(d, lat, lon):
    g = d.assign(dd=(d.lat - lat) ** 2 + (d.lon - lon) ** 2)
    c = g.loc[g.dd.idxmin()]
    return d[(d.lat == c.lat) & (d.lon == c.lon)]


def main():
    d = pd.read_csv("data/hazard/era5_annual_max.csv")
    rec = pd.read_csv("data/hazard/station_records_mgm.csv")
    rows = []
    for s in rec.itertuples():
        gc = nearest(d, s.lat, s.lon)
        p = fit_gev_lmom(gc.pmax_mm.to_numpy())
        rows.append({"comparison": "MGM all-time daily record", "station": s.station, "station_mm": s.record_daily_mm,
                     "era5_mm": float(return_level(75, p["xi"], p["alpha"], p["k"])),
                     "era5_measure": "1-in-75 yr ERA5 return level (record length ~75 yrs)"})
    st = pd.read_csv("data/hazard/stations_2009_sep.csv")
    st["p"] = st[["obs_8sep_mm", "obs_9sep_mm"]].max(axis=1)
    a9 = d[d.year == 2009]
    for s in st.itertuples():
        if 28 <= s.lon <= 29.8 and 40.7 <= s.lat <= 41.6:
            rows.append({"comparison": "8-9 Sept 2009 event", "station": s.station, "station_mm": s.p,
                         "era5_mm": float(nearest(a9, s.lat, s.lon).pmax_mm.iloc[0]),
                         "era5_measure": "ERA5 2009 annual maximum in station cell"})
    t = pd.DataFrame(rows)
    t["ratio"] = t.station_mm / t.era5_mm
    os.makedirs("outputs/tables", exist_ok=True)
    t.round(2).to_csv("outputs/tables/era5_vs_stations.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.6]})
    r = t[t.comparison.str.startswith("MGM")]
    x = np.arange(len(r))
    axes[0].bar(x - 0.2, r.station_mm, 0.4, color=NAVY, label="MGM station record")
    axes[0].bar(x + 0.2, r.era5_mm, 0.4, color=ORANGE, label="ERA5 1-in-75 yr (same cell)")
    axes[0].set_xticks(x, r.station, rotation=30)
    axes[0].set(ylabel="Daily rainfall (mm)", title=f"All-time records: median ratio {r.ratio.median():.1f}x")
    axes[0].legend(fontsize=8)
    e = t[t.comparison.str.startswith("8-9")].sort_values("station_mm", ascending=False)
    x = np.arange(len(e))
    axes[1].bar(x - 0.2, e.station_mm, 0.4, color=NAVY, label="Station, 8-9 Sept 2009")
    axes[1].bar(x + 0.2, e.era5_mm, 0.4, color=ORANGE, label="ERA5 2009 max (same cell)")
    axes[1].set_xticks(x, e.station, rotation=45, ha="right")
    axes[1].set(title="2009 flash flood: ERA5 misses the convective core (up to 6x)")
    axes[1].legend(fontsize=8)
    fig.suptitle("ERA5 (0.25 deg) vs station rainfall in Istanbul", fontweight="bold")
    fig.tight_layout()
    fig.savefig("outputs/figures/06_era5_vs_stations.png", dpi=130)
    print(t.groupby("comparison").ratio.describe().round(2))


if __name__ == "__main__":
    main()
