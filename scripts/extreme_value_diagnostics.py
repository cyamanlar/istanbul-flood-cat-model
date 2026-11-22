"""
Extreme-value diagnostics requested in the review (v0.3):
  1. 90 % confidence intervals of the GEV 100- and 200-year return levels
     (bootstrap over years, regional shape re-estimated in each sample);
  2. stationarity: Mann-Kendall test and Sen slope of ERA5 annual maxima,
     per cell and for the regional mean;
  3. POT / GPD cross-check: peaks over the 99.5th percentile of daily rainfall
     (declustered, 3-day separation), GPD by L-moments, 100-year level vs GEV.
All on raw ERA5 (before the station-scale factors), 1950-2025.
    python scripts/extreme_value_diagnostics.py
Outputs: outputs/tables/gev_return_level_ci.csv, outputs/tables/stationarity_mann_kendall.csv,
         outputs/tables/pot_gpd_vs_gev.csv
"""
import os, sys, glob, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from src.gev import fit_gev_lmom, return_level, sample_lmoments

am = pd.read_csv("data/hazard/era5_annual_max.csv")
cells = am.groupby(["lat", "lon"])
years = np.sort(am.year.unique())
W = am.pivot_table(index="year", columns=["lat", "lon"], values="pmax_mm")
rng = np.random.default_rng(42)

def regional_fit(Wsub):
    fits = {c: fit_gev_lmom(Wsub[c].dropna().to_numpy()) for c in Wsub.columns}
    k = np.mean([f["k"] for f in fits.values()])
    g = math.gamma(1 + k); out = {}
    for c, f in fits.items():
        alpha = f["l2"] * k / ((1 - 2 ** (-k)) * g); xi = f["l1"] - alpha * (1 - g) / k
        out[c] = (xi, alpha, k)
    return out

# 1. bootstrap CI
base = regional_fit(W)
B = 500; bs = {c: [] for c in W.columns}
for _ in range(B):
    idx = rng.integers(0, len(W), len(W))
    f = regional_fit(W.iloc[idx])
    for c in W.columns:
        bs[c].append([return_level(100, *f[c]), return_level(200, *f[c])])
rows = []
for c in W.columns:
    a = np.array(bs[c])
    rows.append(dict(lat=c[0], lon=c[1], rl100_mm=round(return_level(100, *base[c]), 1),
                     rl100_p05=round(np.percentile(a[:, 0], 5), 1), rl100_p95=round(np.percentile(a[:, 0], 95), 1),
                     rl200_mm=round(return_level(200, *base[c]), 1),
                     rl200_p05=round(np.percentile(a[:, 1], 5), 1), rl200_p95=round(np.percentile(a[:, 1], 95), 1)))
ci = pd.DataFrame(rows); ci["rl100_ci_rel_halfwidth"] = ((ci.rl100_p95 - ci.rl100_p05) / 2 / ci.rl100_mm).round(2)
ci.to_csv("outputs/tables/gev_return_level_ci.csv", index=False)
print("GEV 100-yr level, 90% CI relative half-width: median", ci.rl100_ci_rel_halfwidth.median(),
      "range", ci.rl100_ci_rel_halfwidth.min(), "-", ci.rl100_ci_rel_halfwidth.max())

# 2. Mann-Kendall + Sen slope
def mann_kendall(x):
    n = len(x); s = 0
    for i in range(n - 1): s += np.sign(x[i + 1:] - x[i]).sum()
    var = n * (n - 1) * (2 * n + 5) / 18
    z = (s - np.sign(s)) / math.sqrt(var) if s != 0 else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    slopes = [(x[j] - x[i]) / (j - i) for i in range(n) for j in range(i + 1, n)]
    return z, p, float(np.median(slopes))
rows = []
for c in W.columns:
    z, p, sen = mann_kendall(W[c].to_numpy()); rows.append(dict(lat=c[0], lon=c[1], z=round(z, 2), p=round(p, 3), sen_mm_per_decade=round(sen * 10, 2)))
z, p, sen = mann_kendall(W.mean(axis=1).to_numpy())
mk = pd.DataFrame(rows); mk.loc[len(mk)] = dict(lat=np.nan, lon=np.nan, z=round(z, 2), p=round(p, 3), sen_mm_per_decade=round(sen * 10, 2))
mk.to_csv("outputs/tables/stationarity_mann_kendall.csv", index=False)
print(f"Mann-Kendall: {int((mk.p.iloc[:-1] < 0.05).sum())}/{len(mk) - 1} cells significant at 5 %; "
      f"regional mean z={z:.2f}, p={p:.3f}, Sen slope {sen * 10:+.2f} mm/decade")

# 3. POT / GPD from daily ERA5
try:
    import xarray as xr
    files = sorted(glob.glob("data/hazard/era5_raw/*.nc"))
    parts = []
    for f in files:                                   # file by file (no dask needed)
        ds = xr.open_dataset(f)
        tdim = "valid_time" if "valid_time" in ds.dims else "time"
        tp = ds["tp"].rename({tdim: "time"}) * 1000.0
        parts.append(tp.resample(time="1D").sum().load()); ds.close()
    daily = xr.concat(parts, dim="time")
    rows = []
    for c in W.columns:
        s = daily.sel(latitude=c[0], longitude=c[1], method="nearest").to_series().dropna()
        u = s.quantile(0.995); exc = s[s > u]
        # decluster: keep the largest value within 3 days
        peaks = []; last = None
        for t, v in exc.items():
            if last is not None and (t - last[0]).days <= 3:
                if v > last[1]: peaks[-1] = (t, v); last = (t, v)
            else:
                peaks.append((t, v)); last = (t, v)
        y = np.array([v for _, v in peaks]) - u
        lam = len(y) / (len(s) / 365.25)
        l1, l2, _ = sample_lmoments(y)
        kk = l1 / l2 - 2; sig = l1 * (1 + kk)              # GPD (Hosking) shape k, scale sigma
        T = 100; m = lam * T
        rl = u + sig / kk * (1 - m ** (-kk)) if abs(kk) > 1e-6 else u + sig * math.log(m)
        rows.append(dict(lat=c[0], lon=c[1], threshold_mm=round(u, 1), events_per_year=round(lam, 2),
                         gpd_shape_k=round(kk, 3), pot_rl100_mm=round(rl, 1), gev_rl100_mm=round(return_level(100, *base[c]), 1)))
    pot = pd.DataFrame(rows); pot["pot_over_gev"] = (pot.pot_rl100_mm / pot.gev_rl100_mm).round(2)
    pot.to_csv("outputs/tables/pot_gpd_vs_gev.csv", index=False)
    print("POT/GPD vs GEV 100-yr level: median ratio", pot.pot_over_gev.median(), "range", pot.pot_over_gev.min(), "-", pot.pot_over_gev.max())
except ImportError as e:
    print("POT/GPD part skipped:", e)
