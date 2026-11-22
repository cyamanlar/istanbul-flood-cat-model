"""
ERA5 vs MGM hourly gauges for the 7-9 September 2009 event (review point 1).

Input (not redistributed, MGM data licence):
  data/external/mgm_2009-09_hourly_istanbul.csv  (station, lat, lon, hourly rain)
Output:
  outputs/tables/era5_vs_mgm_2009.csv
Same 48-h window (8-9 Sep) for gauge and ERA5; gauge clock assumed local time
(UTC+3) and, as a check, UTC.
"""
import numpy as np, pandas as pd, xarray as xr, os
st = pd.read_csv("data/external/mgm_2009-09_hourly_istanbul.csv", parse_dates=["t"])
ds = xr.open_dataset("data/hazard/era5_raw/tp_levels_2009.nc")
tdim = "valid_time" if "valid_time" in ds.dims else "time"
tp = ds["tp"].rename({tdim: "time"}) * 1000.0
tp = tp.assign_coords(time=tp.time - np.timedelta64(1, "h"))  # label hour by its start (UTC)
rows = []
for (name, lat, lon), g in st.groupby(["Istasyon_Adi", "lat", "lon"]):
    cell = tp.sel(latitude=lat, longitude=lon, method="nearest")
    clat, clon = float(cell.latitude), float(cell.longitude)
    for clock, off in [("local(UTC+3)", 3), ("UTC", 0)]:
        t0 = pd.Timestamp("2009-09-08 00:00") - pd.Timedelta(hours=off)
        t1 = t0 + pd.Timedelta(hours=48)
        e48 = float(cell.sel(time=slice(t0, t1 - pd.Timedelta(hours=1))).sum())
        gg = g[(g.t >= "2009-09-08") & (g.t < "2009-09-10")]
        obs48 = float(gg.TOPLAM_YAGIS_OMGI_mm.sum())
        # max 24 h within window
        ser = g.set_index("t").TOPLAM_YAGIS_OMGI_mm.sort_index()
        o24 = float(ser.rolling(24).sum().loc["2009-09-08":"2009-09-09"].max())
        ce = cell.to_series(); ce.index = ce.index + pd.Timedelta(hours=off)
        e24 = float(ce.rolling(24).sum().loc["2009-09-08":"2009-09-09"].max())
        rows.append(dict(station=name, lat=lat, lon=lon, era5_cell=f"{clat:.2f}N {clon:.2f}E", clock=clock,
                         obs_48h=round(obs48, 1), era5_48h=round(e48, 1),
                         ratio_48h=round(obs48 / e48, 2) if e48 > 0.5 else np.nan,
                         obs_max24h=round(o24, 1), era5_max24h=round(e24, 1),
                         ratio_max24h=round(o24 / e24, 2) if e24 > 0.5 else np.nan))
df = pd.DataFrame(rows).sort_values(["clock", "obs_48h"], ascending=[True, False])
os.makedirs("outputs/tables", exist_ok=True)
df.to_csv("outputs/tables/era5_vs_mgm_2009.csv", index=False)
print(df[df.clock == "local(UTC+3)"].drop(columns=["lat", "lon", "clock"]).to_string(index=False))
loc = df[(df.clock == "local(UTC+3)") & (df.obs_48h >= 30)]
print("\ncells:", loc.era5_cell.nunique(), " median ratio 48h:", loc.ratio_48h.median(),
      " range:", loc.ratio_48h.min(), "-", loc.ratio_48h.max())
