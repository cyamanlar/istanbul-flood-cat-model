"""
Download ERA5 hourly total precipitation over Istanbul from the Copernicus
Climate Data Store (CDS) - one NetCDF file per year.

Setup (one time):
  1. Register at https://cds.climate.copernicus.eu and accept the ERA5 licence
  2. Put your API key in ~/.cdsapirc  (see CDS "How to API" page):
         url: https://cds.climate.copernicus.eu/api
         key: <your-personal-access-token>
  3. pip install cdsapi xarray netCDF4

Usage:
  python scripts/download_era5.py --start 1950 --end 2025
  python scripts/download_era5.py --dataset reanalysis-era5-land   # 0.1 deg, better for a city

Then run:  python scripts/process_era5.py
"""
import argparse
import os

import cdsapi

AREA = [41.6, 27.9, 40.7, 29.95]  # N, W, S, E - Istanbul province + margin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1950)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--dataset", default="reanalysis-era5-single-levels",
                    choices=["reanalysis-era5-single-levels", "reanalysis-era5-land"])
    ap.add_argument("--out", default="data/hazard/era5_raw")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    c = cdsapi.Client()
    for year in range(a.start, a.end + 1):
        target = os.path.join(a.out, f"tp_{a.dataset.split('-')[-1]}_{year}.nc")
        if os.path.exists(target):
            print("skip", target); continue
        req = {
            "variable": ["total_precipitation"],
            "year": [str(year)],
            "month": [f"{m:02d}" for m in range(1, 13)],
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        }
        if a.dataset == "reanalysis-era5-single-levels":
            req["product_type"] = ["reanalysis"]
        print("requesting", year)
        c.retrieve(a.dataset, req).download(target)


if __name__ == "__main__":
    main()
