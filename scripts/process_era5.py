"""
Turn ERA5 hourly precipitation NetCDFs into annual-maximum daily rainfall per
grid cell -> data/hazard/era5_annual_max.csv  (columns: year, lat, lon, pmax_mm)

  python scripts/process_era5.py [--raw data/hazard/era5_raw] [--rolling]

Notes
  * ERA5 single levels: 'tp' = hourly accumulation in metres -> sum to days.
  * ERA5-Land: 'tp' is accumulated from 00 UTC; the 00 UTC value of day D+1
    equals the total of day D (de-accumulated below).
  * --rolling uses the max 24-h moving sum (captures events spanning midnight).
  * Results are re-gridded to the model's 0.25 deg grid (nearest cell mean).
  * ERA5 smooths convective peaks: calibrate `bias_correction_factor` in
    config.json against MGM station maxima (e.g. Florya, Kumkoy, Kartal).
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

GRID_LATS = np.array([40.75, 41.00, 41.25, 41.50])
GRID_LONS = np.arange(28.00, 29.76, 0.25)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/hazard/era5_raw")
    ap.add_argument("--out", default="data/hazard/era5_annual_max.csv")
    ap.add_argument("--rolling", action="store_true")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.raw, "*.nc")))
    if not files:
        raise SystemExit(f"No NetCDF files in {a.raw}. Run download_era5.py first.")
    ds = xr.open_mfdataset(files, combine="by_coords")
    tdim = "valid_time" if "valid_time" in ds.dims else "time"
    ds = ds.rename({tdim: "time"})
    if "latitude" in ds.dims:
        ds = ds.rename({"latitude": "lat", "longitude": "lon"})
    tp = ds["tp"] * 1000.0  # m -> mm
    if "land" in files[0]:
        hourly = tp.diff("time").where(tp.time.dt.hour != 1, tp.isel(time=slice(1, None)))
        tp = hourly.clip(min=0)
    if a.rolling:
        daily = tp.rolling(time=24, min_periods=24).sum()
    else:
        daily = tp.resample(time="1D").sum()
    amax = daily.groupby("time.year").max("time").load()

    df = amax.to_dataframe(name="pmax_mm").reset_index()[["year", "lat", "lon", "pmax_mm"]]
    df["lat"] = GRID_LATS[np.abs(df.lat.to_numpy()[:, None] - GRID_LATS).argmin(1)]
    df["lon"] = GRID_LONS[np.abs(df.lon.to_numpy()[:, None] - GRID_LONS).argmin(1)].round(2)
    df = df.groupby(["year", "lat", "lon"], as_index=False)["pmax_mm"].mean()
    df.round(2).to_csv(a.out, index=False)
    print(f"wrote {a.out}: {df.year.nunique()} years x {df.groupby(['lat','lon']).ngroups} cells")


if __name__ == "__main__":
    main()
