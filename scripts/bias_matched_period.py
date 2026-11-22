"""
Matched-period ERA5 bias estimate from independent daily gauges (review points 1 and 3).

Gauges: IBB open data, daily rainfall at Istanbul water-supply dams, 2011-2024
        (data/ibb/ibb_dam_rainfall_daily.xlsx, IBB Open Data Licence).
ERA5:   data/hazard/era5_annual_max.csv (annual max daily rain per 0.25 deg cell).
Compares annual maxima year by year (2011-2023) in the ERA5 cell of each dam.
Dam coordinates are approximate reservoir locations (+-3 km), well inside one
0.25 deg cell. Dams outside the model grid (Kazandere, Pabucdere, Istrancalar)
are excluded.
Output: outputs/tables/bias_matched_period.csv and a summary on screen.
"""
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
DAMS = {  # name in file: (lat, lon)
    "Ömerli": (41.04, 29.35), "Darlik": (41.09, 29.58), "Elmali": (41.08, 29.10),
    "Terkos": (41.33, 28.60), "B.çekmece": (41.05, 28.55), "Sazlidere": (41.13, 28.69),
    "Alibey": (41.10, 28.92)}
GL = np.array([40.75, 41.00, 41.25, 41.50]); GO = np.arange(28.0, 29.76, 0.25)
g = pd.read_excel("data/ibb/ibb_dam_rainfall_daily.xlsx")
g["Tarih"] = pd.to_datetime(g["Tarih"]); g["year"] = g.Tarih.dt.year
e = pd.read_csv("data/hazard/era5_annual_max.csv")
rows = []
for dam, (la, lo) in DAMS.items():
    cl = GL[np.abs(GL - la).argmin()]; co = round(GO[np.abs(GO - lo).argmin()], 2)
    am = g.groupby("year")[dam].agg(["max", "count"])
    am = am[am["count"] >= 330]["max"]
    ee = e[(e.lat == cl) & (np.isclose(e.lon, co))].set_index("year").pmax_mm
    for y in am.index:
        if y in ee.index:
            rows.append(dict(dam=dam, cell=f"{cl:.2f}N {co:.2f}E", year=y, gauge_amax=am[y], era5_amax=ee[y]))
d = pd.DataFrame(rows); d["ratio"] = d.gauge_amax / d.era5_amax
d.to_csv("outputs/tables/bias_matched_period.csv", index=False)
s = d.groupby(["dam", "cell"]).agg(years=("year", "count"), mean_gauge=("gauge_amax", "mean"),
                                   mean_era5=("era5_amax", "mean")).reset_index()
s["index_ratio"] = (s.mean_gauge / s.mean_era5).round(2)
print(s.round(1).to_string(index=False))
# quantile ratio: pooled sorted annual maxima (station-scale vs ERA5-scale distributions)
qs = [0.5, 0.75, 0.9]
qr = {q: round(d.gauge_amax.quantile(q) / d.era5_amax.quantile(q), 2) for q in qs}
print("\npooled quantile ratios (gauge/ERA5) of annual maxima:", qr)
# bootstrap the index ratio over dams and years
rng = np.random.default_rng(1)
bs = []
for _ in range(5000):
    i = rng.integers(0, len(d), len(d)); x = d.iloc[i]
    bs.append(x.gauge_amax.mean() / x.era5_amax.mean())
print("pooled mean-annual-max ratio:", round(d.gauge_amax.mean() / d.era5_amax.mean(), 2),
      " 90% bootstrap CI:", np.round(np.percentile(bs, [5, 95]), 2))
print("cells:", d.cell.nunique(), "dams:", d.dam.nunique(), "station-years:", len(d))
