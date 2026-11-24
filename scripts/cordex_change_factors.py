"""
EURO-CORDEX (EUR-11) change factors for annual-maximum daily rainfall over Istanbul.

Replaces the fixed 7 %/degC scaling with model-based changes, per 0.25 deg cell:
  factor = (mean annual max daily rainfall, future period) / (same, 1981-2010)
for each GCM-RCM pair, then the median and range across pairs.

    python scripts/cordex_change_factors.py download     # on the server (large: ~1.3 GB per 5-year file, cropped at once)
    python scripts/cordex_change_factors.py factors      # -> outputs/tables/cordex_change_factors.csv

Needs the user's own ~/.cdsapirc (never in this repository). Each downloaded
file is cropped to 40.5-41.75N, 27.75-30.0E and the full file is removed.
If a request is refused, open the CDS form for "projections-cordex-domains-single-levels"
and compare the model and member names with PAIRS below.
"""
import glob, os, sys, zipfile
import numpy as np, pandas as pd, xarray as xr

PAIRS = [  # (gcm, rcm, member) - a small spread; add more pairs as needed
    ("mpi_m_mpi_esm_lr", "smhi_rca4", "r1i1p1"),
    ("ichec_ec_earth", "knmi_racmo22e", "r12i1p1"),
    ("cnrm_cerfacs_cnrm_cm5", "clmcom_cclm4_8_17", "r1i1p1"),
]
PERIODS = {"historical": [(1981, 2005)], "rcp_8_5": [(2006, 2010), (2041, 2070), (2071, 2100)]}
BOX = dict(lat=(40.5, 41.75), lon=(27.75, 30.0))
RAW = "data/external/cordex"     # gitignored; only the table is published
LATS = np.array([40.75, 41.00, 41.25, 41.50]); LONS = np.arange(28.00, 29.76, 0.25)


def crop(nc):
    ds = xr.open_dataset(nc)
    la, lo = ds["lat"], ds["lon"]
    m = (la >= BOX["lat"][0]) & (la <= BOX["lat"][1]) & (lo >= BOX["lon"][0]) & (lo <= BOX["lon"][1])
    ys, xs = np.where(m.values)
    sub = ds.isel(rlat=slice(ys.min(), ys.max() + 1), rlon=slice(xs.min(), xs.max() + 1)).load()
    ds.close(); return sub


def download():
    import cdsapi
    c = cdsapi.Client(); os.makedirs(RAW, exist_ok=True)
    for gcm, rcm, mem in PAIRS:
        for exp, spans in PERIODS.items():
            for y0, y1 in spans:
                for s in range(y0, y1 + 1, 5):
                    e = min(s + 4, y1)
                    tag = f"{gcm}__{rcm}__{exp}__{s}_{e}"
                    if glob.glob(f"{RAW}/{tag}.nc"): continue
                    z = f"{RAW}/{tag}.zip"
                    c.retrieve("projections-cordex-domains-single-levels", {
                        "domain": "europe", "experiment": exp, "horizontal_resolution": "0_11_degree_x_0_11_degree",
                        "temporal_resolution": "daily_mean", "variable": ["mean_precipitation_flux"],
                        "gcm_model": gcm, "rcm_model": rcm, "ensemble_member": mem,
                        "start_year": [str(s)], "end_year": [str(e)]}, z)
                    with zipfile.ZipFile(z) as zz:
                        for n in zz.namelist():
                            zz.extract(n, RAW); sub = crop(os.path.join(RAW, n)); os.remove(os.path.join(RAW, n))
                            sub.to_netcdf(f"{RAW}/{tag}.nc")
                    os.remove(z); print("ok", tag)


def annual_max_by_cell(files):
    ds = xr.concat([xr.open_dataset(f) for f in sorted(files)], "time")
    pr = ds["pr"] * 86400.0                                   # kg m-2 s-1 -> mm/day
    am = pr.groupby("time.year").max("time")
    out = {}
    for la in LATS:
        for lo in LONS:
            m = (np.abs(ds["lat"] - la) <= 0.125) & (np.abs(ds["lon"] - lo) <= 0.125)
            out[(la, lo)] = float(am.where(m).mean(("rlat", "rlon")).mean("year"))
    return out


def factors():
    rows = []
    for gcm, rcm, _ in PAIRS:
        base = glob.glob(f"{RAW}/{gcm}__{rcm}__historical__*.nc") + glob.glob(f"{RAW}/{gcm}__{rcm}__rcp_8_5__2006_2010.nc")
        if not base: continue
        b = annual_max_by_cell(base)
        for y0, y1 in [(2041, 2070), (2071, 2100)]:
            fut = [f for f in glob.glob(f"{RAW}/{gcm}__{rcm}__rcp_8_5__*.nc") if y0 <= int(f.split("__")[-1][:4]) <= y1]
            if not fut: continue
            f = annual_max_by_cell(fut)
            for k in b:
                rows.append(dict(gcm=gcm, rcm=rcm, period=f"{y0}-{y1}", lat=k[0], lon=k[1], factor=round(f[k] / b[k], 3)))
    df = pd.DataFrame(rows)
    if df.empty: raise SystemExit(f"no CORDEX files in {RAW}; run the download step first")
    s = df.groupby(["period", "lat", "lon"]).factor.agg(["median", "min", "max"]).round(3).reset_index()
    os.makedirs("outputs/tables", exist_ok=True)
    df.to_csv("outputs/tables/cordex_change_factors_by_model.csv", index=False)
    s.to_csv("outputs/tables/cordex_change_factors.csv", index=False)
    print(s.groupby("period")[["median", "min", "max"]].mean().round(3))


if __name__ == "__main__":
    {"download": download, "factors": factors}[sys.argv[1]]()
