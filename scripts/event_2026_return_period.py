"""
Independent check with the 13-15 October 2026 event (not used in calibration).

1. Where does ERA5's largest daily rainfall of 13-17 October 2026 rank against
   each cell's 1950-2025 annual maxima, and what return period does the
   model's hazard (GEV with regional shape, zonal station-scale factors) give it?
2. Loss of the illustrative portfolio if the October 2026 rainfall field
   (ERA5 x zonal factors) hit it, and its return period on the reference EP curve.
    python scripts/event_2026_return_period.py
Output: outputs/tables/event_2026_return_period.csv
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd, xarray as xr
from src import hazard, exposure, financial
cfg = json.load(open("config.json", encoding="utf-8"))
ds = xr.open_dataset("data/events/era5_tp_2026-10-10_20.nc"); t = "valid_time" if "valid_time" in ds.dims else "time"
tp = ds["tp"].rename({t: "time"}) * 1000.0
tp = tp.assign_coords(time=tp.time - np.timedelta64(1, "h"))
d = tp.resample(time="1D").sum().sel(time=slice("2026-10-13", "2026-10-17")).max("time")
cells = hazard.grid_cells()
rng = np.random.default_rng(cfg["random_seed"])
am, _ = hazard.load_annual_max(cfg, cells, rng)                 # station-scale annual maxima
gev = hazard.fit_cells(am, regional_shape=cfg["hazard"].get("regional_shape", True))
raw = pd.read_csv("data/hazard/era5_annual_max.csv")
f = hazard.bias_factors(cfg, gev.lon.to_numpy())
from src.gev import gev_quantile
rows, ev = [], []
for (i, g), fac in zip(gev.iterrows(), f):
    e = float(d.sel(latitude=g.lat, longitude=g.lon, method="nearest"))
    s = raw[(raw.lat == g.lat) & np.isclose(raw.lon, g.lon)].pmax_mm
    x = e * fac
    # non-exceedance probability under the fitted GEV (k sign convention of Hosking)
    k, xi, al = g.k, g.xi, g.alpha
    y = 1 - k * (x - xi) / al
    F = np.exp(-y ** (1 / k)) if y > 0 else (1.0 if k > 0 else 0.0)
    rp = 1 / max(1 - F, 1e-9)
    rows.append(dict(lat=g.lat, lon=g.lon, era5_max_daily_mm=round(e, 1), rank_1950_2026=int((s > e).sum()) + 1,
                     station_scale_mm=round(x, 1), model_return_period_yr=round(rp, 0)))
    ev.append(x)
out = pd.DataFrame(rows); out.to_csv("outputs/tables/event_2026_return_period.csv", index=False)
print(out.sort_values("era5_max_daily_mm", ascending=False).head(8).to_string(index=False))
loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))
res = financial.run_losses(np.array([ev]), gev, loc, cfg, np.random.default_rng(cfg["random_seed"] + 1))
ep = pd.read_csv("outputs/tables/ep_curve_baseline.csv")
L = float(res["gross"][0]); rpL = float(np.interp(L, ep.loss.to_numpy()[::-1], ep.return_period.to_numpy()[::-1])) if "loss" in ep else np.nan
print(f"\nportfolio loss, October 2026 field: EUR {L/1e6:.2f} m  (about 1-in-{rpL:.0f} on the reference EP curve)")
