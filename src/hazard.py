"""
HAZARD MODULE - extreme daily rainfall over Istanbul (pluvial / flash flood driver)

Pipeline
--------
1. Annual-maximum daily precipitation per ERA5 grid cell (0.25 deg)
   -> produced by scripts/download_era5.py + scripts/process_era5.py
2. GEV fit per cell (L-moments)                      -> return-level maps
3. Stochastic event set: N simulated years, one dominant rainfall event per
   year, spatially correlated across cells via a Gaussian copula with
   exponential distance decay  rho(d) = exp(-d / L).
4. Optional climate scaling of intensities (Clausius-Clapeyron, ~7 %/degC).

If no ERA5 file is present the module generates a clearly-flagged
SYNTHETIC demonstration series so the whole pipeline runs out of the box.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from .gev import fit_gev_lmom, gev_quantile, norm_cdf, return_level

# ERA5 0.25 deg cells covering the Istanbul province
GRID_LATS = np.array([40.75, 41.00, 41.25, 41.50])
GRID_LONS = np.arange(28.00, 29.76, 0.25)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def grid_cells() -> pd.DataFrame:
    lat, lon = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    df = pd.DataFrame({"lat": lat.ravel().round(2), "lon": lon.ravel().round(2)})
    df.insert(0, "cell_id", np.arange(1, len(df) + 1))
    return df


def correlation_matrix(cells: pd.DataFrame, corr_length_km: float) -> np.ndarray:
    lat = cells["lat"].to_numpy()
    lon = cells["lon"].to_numpy()
    d = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    return np.exp(-d / corr_length_km)


# ---------------------------------------------------------------------------
# 1. Annual maxima: real ERA5 or synthetic demo
# ---------------------------------------------------------------------------
def make_synthetic_annual_max(cells: pd.DataFrame, years, corr_length_km: float,
                              rng: np.random.Generator) -> pd.DataFrame:
    """Synthetic annual maxima with realistic magnitudes for Istanbul.

    Magnitudes are set to a station-scale climatology (mean annual max daily
    rainfall ~55-60 mm, heavier on the Black Sea side). REPLACE WITH ERA5.
    """
    n_c = len(cells)
    lat = cells["lat"].to_numpy()
    xi = 45.0 + 8.0 * (lat - 41.0) / 0.5 + rng.normal(0, 2.0, n_c)
    alpha = 16.0 + rng.normal(0, 1.0, n_c)
    k = -0.15 + rng.normal(0, 0.02, n_c)
    C = correlation_matrix(cells, corr_length_km)
    L = np.linalg.cholesky(C + 1e-9 * np.eye(n_c))
    z = rng.standard_normal((len(years), n_c)) @ L.T
    u = norm_cdf(z)
    vals = np.column_stack([gev_quantile(u[:, j], xi[j], alpha[j], k[j]) for j in range(n_c)])
    out = pd.DataFrame(vals, columns=cells["cell_id"])
    out.insert(0, "year", list(years))
    long = out.melt(id_vars="year", var_name="cell_id", value_name="pmax_mm")
    return long.merge(cells, on="cell_id")



def bias_factors(cfg: dict, lon) -> np.ndarray:
    """ERA5 -> station-scale multiplier for annual-maximum daily rainfall.

    v0.3: zonal factors estimated from matched-period gauges (IBB dam
    rain gauges 2011-2023 vs ERA5 in the same cell; scripts/bias_matched_period.py).
    The ratio of mean annual maxima is used because the model scales annual
    maxima before the GEV fit (index-flood logic). Cells west of the Bosphorus
    get the European-side factor, cells east of it the Asian-side factor and
    the Bosphorus column (29.00E) the mean of both. ``bias_multiplier`` scales
    all factors together for the uncertainty runs (P5 / P95).
    A plain number in ``bias_correction_factor`` still works (v0.2 behaviour).
    """
    h = cfg["hazard"]
    lon = np.asarray(lon, dtype=float)
    mult = h.get("bias_multiplier", 1.0)
    bc = h.get("bias_correction")
    if not bc:
        return np.full(lon.shape, float(h["bias_correction_factor"]) * mult)
    eu, asia = bc["europe"], bc["asia"]
    f = np.where(lon <= bc["europe_max_lon"], eu, np.where(lon >= bc["asia_min_lon"], asia, 0.5 * (eu + asia)))
    return f * mult

def load_annual_max(cfg: dict, cells: pd.DataFrame, rng) -> tuple[pd.DataFrame, bool]:
    """Return (annual-max table, is_synthetic)."""
    path = cfg["hazard"]["era5_annual_max_csv"]
    src = cfg["hazard"]["source"]
    if src in ("auto", "era5") and os.path.exists(path):
        df = pd.read_csv(path)
        if df["year"].nunique() < 10:
            print(f"[hazard]   {path} has only {df['year'].nunique()} year(s) - need >= 10 for a GEV fit; "
                  "using the synthetic demo hazard for now")
            return make_synthetic_annual_max(cells, range(1950, 2026), cfg["hazard"]["corr_length_km"], rng), True
        df["pmax_mm"] *= bias_factors(cfg, df["lon"].to_numpy())
        df = df.merge(cells, on=["lat", "lon"], how="inner", suffixes=("", "_g"))
        if "cell_id_g" in df:
            df["cell_id"] = df.pop("cell_id_g")
        return df, False
    if src == "era5":
        raise FileNotFoundError(f"{path} not found - run scripts/download_era5.py first")
    years = range(1950, 2026)
    return make_synthetic_annual_max(cells, years, cfg["hazard"]["corr_length_km"], rng), True


# ---------------------------------------------------------------------------
# 2. GEV per cell
# ---------------------------------------------------------------------------
def fit_cells(annual_max: pd.DataFrame, return_periods=(10, 25, 50, 100, 200, 500),
              regional_shape: bool = True) -> pd.DataFrame:
    """GEV per cell by L-moments. With regional_shape=True the shape k is the
    mean of the cell estimates (index-flood idea, Hosking & Wallis 1997): a
    76-year series pins down location and scale well, but not the tail shape."""
    import math
    fits = {key: (fit_gev_lmom(g["pmax_mm"].to_numpy()), len(g))
            for key, g in annual_max.groupby(["cell_id", "lat", "lon"])}
    k_reg = float(np.mean([f[0]["k"] for f in fits.values()]))
    rows = []
    for (cid, lat, lon), (p, n) in fits.items():
        if regional_shape:
            k = k_reg
            gk = math.gamma(1 + k)
            alpha = p["l2"] * k / ((1 - 2 ** (-k)) * gk)
            p = {"xi": p["l1"] - alpha * (1 - gk) / k, "alpha": alpha, "k": k, "k_local": p["k"]}
        row = {"cell_id": cid, "lat": lat, "lon": lon, "n_years": n,
               "xi": p["xi"], "alpha": p["alpha"], "k": p["k"]}
        for rp, rl in zip(return_periods, return_level(return_periods, p["xi"], p["alpha"], p["k"])):
            row[f"RL{rp}_mm"] = rl
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cell_id").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Stochastic event set
# ---------------------------------------------------------------------------
def simulate_event_set(gev: pd.DataFrame, n_years: int, corr_length_km: float,
                       rng: np.random.Generator, max_daily_mm: float = 400.0) -> np.ndarray:
    """Return array (n_years, n_cells) of daily rainfall (mm) of the
    dominant annual event. Event id = simulated year index + 1."""
    C = correlation_matrix(gev, corr_length_km)
    L = np.linalg.cholesky(C + 1e-9 * np.eye(len(gev)))
    z = rng.standard_normal((n_years, len(gev))) @ L.T
    u = norm_cdf(z)
    return np.column_stack([
        gev_quantile(u[:, j], r.xi, r.alpha, r.k) for j, r in enumerate(gev.itertuples())
    ]).clip(min=0, max=max_daily_mm)  # physical upper bound on daily rainfall


def climate_scale(event_set: np.ndarray, warming_degC: float, rate_per_degC: float) -> np.ndarray:
    """Clausius-Clapeyron style intensity scaling: P' = P * (1 + rate)^dT."""
    return event_set * (1 + rate_per_degC) ** warming_degC


def scenario_2009_footprint(gev: pd.DataFrame) -> np.ndarray:
    """Deterministic stress scenario inspired by the 9 Sept 2009 flash flood
    (Ayamama / Ikitelli, European side). Stylised - not a reconstruction."""
    lon = gev["lon"].to_numpy()
    lat = gev["lat"].to_numpy()
    p = np.full(len(gev), 40.0)                                   # Asian side
    p[(lon <= 29.0)] = 120.0                                       # European side
    p[(lon >= 28.5) & (lon <= 28.75) & (lat >= 40.75) & (lat <= 41.25)] = 230.0  # Ayamama core
    p[(lon >= 28.25) & (lon < 28.5) & (lat >= 40.75) & (lat <= 41.25)] = 180.0   # Catalca/Silivri
    return p[None, :]
