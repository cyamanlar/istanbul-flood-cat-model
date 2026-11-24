"""
Catalogue of the largest rainfall days over Istanbul in ERA5, 1950-2026.

Used to pick extra extreme events for testing (WRF re-runs, ERA5 bias by
storm type). Reads the hourly ERA5 files one by one (no dask).

    python scripts/extreme_event_catalogue.py [--top 25]
Output: outputs/tables/extreme_event_catalogue.csv
Columns: date (UTC day), max_cell_mm, lat/lon of that cell, mean_mm (32 cells),
         cells_ge_50mm, side (where the core is: europe / asia / bosphorus).
Days closer than 3 days to a larger day are dropped (one row per storm).
"""
import argparse, glob, os
import numpy as np, pandas as pd, xarray as xr

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default="data/hazard/era5_raw")
ap.add_argument("--extra", default="data/events/era5_tp_2026-10-10_20.nc")
ap.add_argument("--top", type=int, default=25)
a = ap.parse_args()
LATS = np.array([40.75, 41.00, 41.25, 41.50]); LONS = np.arange(28.00, 29.76, 0.25)

rows = []
files = sorted(glob.glob(os.path.join(a.raw, "*.nc"))) + ([a.extra] if os.path.exists(a.extra) else [])
for f in files:
    ds = xr.open_dataset(f)
    t = "valid_time" if "valid_time" in ds.dims else "time"
    tp = ds["tp"].rename({t: "time"}) * 1000.0
    tp = tp.assign_coords(time=tp.time - np.timedelta64(1, "h"))   # hour-ending -> hour-starting
    d = tp.resample(time="1D").sum()
    d = d.sel(latitude=LATS, longitude=LONS, method="nearest").load()
    v = d.values  # time, lat, lon
    for i, day in enumerate(pd.to_datetime(d.time.values)):
        x = v[i]; j = np.unravel_index(np.nanargmax(x), x.shape)
        rows.append(dict(date=day.date(), max_cell_mm=float(x[j]), lat=float(LATS[j[0]]), lon=float(LONS[j[1]]),
                         mean_mm=float(np.nanmean(x)), cells_ge_50mm=int((x >= 50).sum())))
    ds.close()
df = pd.DataFrame(rows).drop_duplicates("date").sort_values("max_cell_mm", ascending=False)
keep = []
for _, r in df.iterrows():
    if all(abs((pd.Timestamp(r.date) - pd.Timestamp(k.date)).days) > 3 for k in keep):
        keep.append(r)
    if len(keep) >= a.top: break
out = pd.DataFrame(keep)
out["side"] = np.where(out.lon <= 28.75, "europe", np.where(out.lon >= 29.25, "asia", "bosphorus"))
out = out.round(1)
os.makedirs("outputs/tables", exist_ok=True)
out.to_csv("outputs/tables/extreme_event_catalogue.csv", index=False)
print(out.to_string(index=False))
