"""
WRF rainfall for one case -> tables the cat model can use.

    python wrf/03_wrf_rain_check.py ist2009 [--dom 3] [--spinup 12]
Reads wrf/cases/<case>/wrf/wrfout_d0<dom>_* (copy them back from the server).

Outputs (outputs/wrf/<case>/):
  stations.csv     WRF vs station rainfall at the nearest grid point (and best point within 10 km,
                   a usual allowance for displacement); 2009: daily 8 and 9 Sep; 2026: event total
  points.csv       lon, lat, p_event_mm (max daily rainfall), max_1h_mm on a 2-km thinned grid
                   -> input for 04_wrf_building_replay.py
  cells.csv        WRF max daily rainfall on the model's 0.25 deg cells vs ERA5, model return period
  summary.json     domain max daily / 1-h rainfall, ratio WRF/ERA5, portfolio loss of the WRF field
"""
import argparse, glob, json, os, sys
import numpy as np, pandas as pd, xarray as xr
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)

ap = argparse.ArgumentParser(); ap.add_argument("case"); ap.add_argument("--dom", type=int, default=3)
ap.add_argument("--spinup", type=int, default=12); a = ap.parse_args()
files = sorted(glob.glob(f"wrf/cases/{a.case}/wrf/wrfout_d0{a.dom}_*"))
if not files: raise SystemExit(f"no wrfout_d0{a.dom} files in wrf/cases/{a.case}/wrf/")
ds = xr.open_mfdataset(files, combine="nested", concat_dim="Time") if len(files) > 1 else xr.open_dataset(files[0])
times = pd.to_datetime([t.decode() if isinstance(t, bytes) else str(t) for t in ds["Times"].values.astype(str)], format="%Y-%m-%d_%H:%M:%S")
acc = (ds["RAINNC"] + ds["RAINC"]).values                                  # accumulated mm
lat = ds["XLAT"].isel(Time=0).values; lon = ds["XLONG"].isel(Time=0).values
keep = times >= times[0] + pd.Timedelta(hours=a.spinup)
acc, times = acc[keep] - acc[keep][0], times[keep]
hourly = np.diff(acc, axis=0, prepend=acc[:1]); hourly[0] = 0
max1h = hourly.max(0)
# hourly[i] = rain in the hour ending at times[i]; group by UTC day of the hour start
hstart = pd.DatetimeIndex(times) - pd.Timedelta(hours=1)
daily = {d: hourly[hstart.normalize() == d].sum(0) for d in hstart.normalize().unique()[1:]}
dmax = np.max(np.stack(list(daily.values())), 0)
out = f"outputs/wrf/{a.case}"; os.makedirs(out, exist_ok=True)

def at(lo, la, field, rad_km=0.0):
    dk = np.hypot((lat - la) * 111.0, (lon - lo) * 111.0 * np.cos(np.radians(la)))
    if rad_km <= 0: return float(field.ravel()[dk.argmin()])
    return float(field[dk <= rad_km].max())

rows = []
if a.case == "ist2009":
    st = pd.read_csv("data/hazard/stations_2009_sep.csv")
    for _, s in st.iterrows():
        for dd, col in [("2009-09-08", "obs_8sep_mm"), ("2009-09-09", "obs_9sep_mm")]:
            f = daily.get(pd.Timestamp(dd));
            if f is None: continue
            rows.append(dict(station=s.station, day=dd, obs_mm=s[col], wrf_nearest_mm=round(at(s.lon, s.lat, f), 1),
                             wrf_best10km_mm=round(at(s.lon, s.lat, f, 10), 1)))
elif a.case == "ist2026":
    st = pd.read_csv("data/events/istanbul_2026-10_stations.csv")
    tot = acc[-1]
    for _, s in st.iterrows():
        rows.append(dict(station=s.station, day="event total", obs_mm=s.reported_mm, wrf_nearest_mm=round(at(s.lon, s.lat, tot), 1),
                         wrf_best10km_mm=round(at(s.lon, s.lat, tot, 10), 1)))
sv = pd.DataFrame(rows)
if len(sv):
    sv["ratio_nearest"] = (sv.wrf_nearest_mm / sv.obs_mm).round(2); sv.to_csv(f"{out}/stations.csv", index=False)

# thinned points for the building-level replay (about every 2 km on d03)
step = max(1, int(round(2000 / float(ds.attrs.get("DX", 1000)))))
pts = pd.DataFrame(dict(lon=lon[::step, ::step].ravel(), lat=lat[::step, ::step].ravel(),
                        p_event_mm=dmax[::step, ::step].ravel().round(1), max_1h_mm=max1h[::step, ::step].ravel().round(1)))
pts.to_csv(f"{out}/points.csv", index=False)

# 0.25 deg cells: WRF max daily (cell max) vs ERA5 and model return period
from src import hazard
from src.gev import gev_quantile  # noqa: F401 (kept for users extending the check)
cfg = json.load(open("config.json", encoding="utf-8"))
cells = hazard.grid_cells(); rng = np.random.default_rng(cfg["random_seed"])
am, _ = hazard.load_annual_max(cfg, cells, rng)
gev = hazard.fit_cells(am, regional_shape=cfg["hazard"].get("regional_shape", True))
crow, ev = [], []
for _, g in gev.iterrows():
    m = (np.abs(lat - g.lat) <= 0.125) & (np.abs(lon - g.lon) <= 0.125)
    x = float(dmax[m].max()) if m.any() else np.nan
    if np.isnan(x): ev.append(0.0); continue
    y = 1 - g.k * (x - g.xi) / g.alpha
    F = np.exp(-y ** (1 / g.k)) if y > 0 else (1.0 if g.k > 0 else 0.0)
    crow.append(dict(lat=g.lat, lon=g.lon, wrf_max_daily_mm=round(x, 1), wrf_cell_mean_mm=round(float(dmax[m].mean()), 1),
                     model_return_period_yr=round(1 / max(1 - F, 1e-9))))
    ev.append(float(dmax[m].mean()))     # cell mean = the model's station-scale cell value
cdf = pd.DataFrame(crow); cdf.to_csv(f"{out}/cells.csv", index=False)

summary = dict(case=a.case, domain=a.dom, n_hours=int(len(times)), domain_max_daily_mm=round(float(dmax.max()), 1),
               domain_max_1h_mm=round(float(max1h.max()), 1),
               station_median_ratio=round(float(sv.ratio_nearest.median()), 2) if len(sv) else None)
try:
    from src import exposure, financial
    loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))
    res = financial.run_losses(np.array([ev]), gev, loc, cfg, np.random.default_rng(cfg["random_seed"] + 1))
    L = float(res["gross"][0]); ep = pd.read_csv("outputs/tables/ep_curve_baseline.csv")
    summary["portfolio_loss_eur_m"] = round(L / 1e6, 2)
    summary["portfolio_loss_return_period_yr"] = round(float(np.interp(L, ep.loss.to_numpy()[::-1], ep.return_period.to_numpy()[::-1])))
except Exception as e:  # keep the rainfall check usable without the loss modules
    summary["portfolio_loss_note"] = f"not computed: {e}"
json.dump(summary, open(f"{out}/summary.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
if len(sv): print(sv.to_string(index=False))
