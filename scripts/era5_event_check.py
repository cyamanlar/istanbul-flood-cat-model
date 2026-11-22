"""
Event-day check of ERA5 against station rainfall.

Answers two review points:
  1. For the 7-9 September 2009 event, what did ERA5 give on the event days
     (not the 2009 annual maximum) in the cell of each station?
  2. Which stations share an ERA5 cell (independent comparisons)?
Optionally repeats the check for the 13-15 October 2026 event once the 2026
ERA5 file has been downloaded (python scripts/download_era5.py --start 2026 --end 2026).

Daily totals are given for two day definitions:
  * UTC day 00-24 UTC
  * 06-06 UTC (closer to a 09-09 local climatological day)

Usage
  python scripts/era5_event_check.py
Outputs
  outputs/tables/era5_event_check_2009.csv
  outputs/tables/era5_cell_sharing.csv
  outputs/tables/era5_event_check_2026.csv  (if data/events/istanbul_2026-10_stations.csv has coordinates)
"""
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

RAW = "data/hazard/era5_raw"
OUT = "outputs/tables"


def load_year(year):
    f = os.path.join(RAW, f"tp_levels_{year}.nc")
    if not os.path.exists(f):
        return None
    ds = xr.open_dataset(f)
    tdim = "valid_time" if "valid_time" in ds.dims else "time"
    ds = ds.rename({tdim: "time"})
    tp = ds["tp"] * 1000.0  # m -> mm (hourly accumulation)
    return tp


def daily(tp, shift_h=0):
    """Daily sums. ERA5 'tp' at valid time t is the accumulation of the hour
    ending at t, so we shift by 1 h to label each hour by its start; shift_h
    moves the day boundary (6 -> 06-06 UTC)."""
    s = tp.assign_coords(time=tp.time - np.timedelta64(1 + shift_h, "h"))
    return s.resample(time="1D").sum()


def nearest(da, lat, lon):
    return da.sel(latitude=lat, longitude=lon, method="nearest")


def cell_id(da, lat, lon):
    p = nearest(da.isel(time=0), lat, lon)
    return float(p.latitude), float(p.longitude)


def check_2009():
    st = pd.read_csv("data/hazard/stations_2009_sep.csv")
    tp = load_year(2009)
    if tp is None:
        raise SystemExit("tp_levels_2009.nc missing")
    d_utc = daily(tp)
    d_06 = daily(tp, shift_h=6)
    rows = []
    for _, r in st.iterrows():
        la, lo = cell_id(tp, r.lat, r.lon)
        s_utc = nearest(d_utc, r.lat, r.lon).to_series()
        s_06 = nearest(d_06, r.lat, r.lon).to_series()
        amax_day = s_utc.idxmax()
        for day, obs_col in [("2009-09-08", "obs_8sep_mm"), ("2009-09-09", "obs_9sep_mm")]:
            e_utc = float(s_utc.loc[day])
            e_06 = float(s_06.loc[day])
            obs = float(r[obs_col])
            rows.append(dict(station=r.station, cell_lat=la, cell_lon=lo, day=day, obs_mm=obs,
                             era5_utc_mm=round(e_utc, 1), era5_06utc_mm=round(e_06, 1),
                             ratio_obs_to_era5_utc=round(obs / e_utc, 2) if e_utc > 0.1 else np.nan,
                             era5_2009_annual_max_mm=round(float(s_utc.max()), 1),
                             annual_max_date=str(amax_day.date())))
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "era5_event_check_2009.csv"), index=False)
    # event-day of each station's maximum observation
    peak = df.loc[df.groupby("station").obs_mm.idxmax()].sort_values("obs_mm", ascending=False)
    print("\n2009 event: station peak day vs ERA5 on the same day")
    print(peak[["station", "day", "obs_mm", "era5_utc_mm", "era5_06utc_mm", "ratio_obs_to_era5_utc",
                "era5_2009_annual_max_mm", "annual_max_date"]].to_string(index=False))
    # pooled ratio: sum(obs)/sum(era5) for stations with obs >= 50 mm
    big = peak[peak.obs_mm >= 50]
    print(f"\nPooled obs/ERA5 (UTC) for peak days >= 50 mm: {big.obs_mm.sum() / big.era5_utc_mm.sum():.2f}"
          f" over {len(big)} stations in {big[['cell_lat','cell_lon']].drop_duplicates().shape[0]} cells")


def cell_sharing():
    tp = load_year(2009)
    rec = pd.read_csv("data/hazard/station_records_mgm.csv")
    st = pd.read_csv("data/hazard/stations_2009_sep.csv")
    rows = []
    for src, df in [("mgm_records", rec), ("2009_stations", st)]:
        for _, r in df.iterrows():
            la, lo = cell_id(tp, r.lat, r.lon)
            rows.append(dict(set=src, station=r.station, cell=f"{la:.2f}N {lo:.2f}E"))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "era5_cell_sharing.csv"), index=False)
    g = out.groupby(["set", "cell"]).station.apply(lambda s: ", ".join(s)).reset_index()
    print("\nStations per ERA5 cell")
    print(g.to_string(index=False))
    for s in out.set.unique():
        print(f"{s}: {len(out[out.set == s])} stations in {out[out.set == s].cell.nunique()} independent cells")


def check_2026():
    f = "data/events/istanbul_2026-10_stations.csv"
    f26 = "data/events/era5_tp_2026-10-10_20.nc"   # kept apart from era5_raw (partial year)
    tp = None
    if os.path.exists(f26):
        ds = xr.open_dataset(f26); tdim = "valid_time" if "valid_time" in ds.dims else "time"
        tp = ds["tp"].rename({tdim: "time"}) * 1000.0
    if tp is None or not os.path.exists(f):
        print("\n2026: skipped (needs data/events/era5_tp_2026-10-10_20.nc from CDS)")
        return
    st = pd.read_csv(f).dropna(subset=["lat", "lon"])
    d_utc = daily(tp)
    win = d_utc.sel(time=slice("2026-10-13", "2026-10-15")).sum("time")
    rows = []
    for _, r in st.iterrows():
        e = float(nearest(win, r.lat, r.lon))
        la, lo = cell_id(tp, r.lat, r.lon)
        rows.append(dict(station=r.station, cell=f"{la:.2f}N {lo:.2f}E", reported_mm=r.reported_mm,
                         era5_13_15oct_mm=round(e, 1), ratio=round(r.reported_mm / e, 2) if e > 0.1 else np.nan))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "era5_event_check_2026.csv"), index=False)
    print("\n2026 event (13-15 Oct, ERA5 UTC days summed)")
    print(df.to_string(index=False))


if __name__ == "__main__":
    check_2009()
    cell_sharing()
    check_2026()
