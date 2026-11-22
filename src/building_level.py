"""
BUILDING-LEVEL MODULE - western Istanbul (Ayamama, Haramidere, Alibey and
Catalca catchments), validated against the 8-9 September 2009 flash flood.

Inputs (all open data)
  * OpenStreetMap building footprints  (c) OpenStreetMap contributors, ODbL
  * OpenStreetMap waterways + named river systems (Ayamama, Haramidere, Alibey)
  * Copernicus DEM GLO-30 (1 arc-second, ~30 m)
  * MGM / AKOM station rainfall of 8-9 Sept 2009 as published in
    HIRLAM Newsletter 56 (2010) and EJOSAT 13 (2018), doi:10.31590/ejosat.417535

Method
  1. Exposure    : footprint area x storeys x replacement cost -> building & contents
                   value; only the ground floor (+ basement) is exposed to flooding.
  2. Flood-zone  : HAND-type index = building ground elevation - elevation of the
                   most hazardous nearby stream point (+ 1 m per km distance as a
                   head-loss / attenuation term). No more guessing which district is
                   "flood-prone": every building gets its own value from the DEM.
  3. Hazard      : daily rainfall P -> stream stage  S = a * max(0, P - P0) * class
                   factor (main stem 1.0 ... drains 0.3); depth = max(0, S - HAND).
  4. Damage      : JRC Europe depth-damage curves (same as the portfolio model).
  5. Validation  : 2009 observed rainfall footprint (IDW of 18 stations) ->
                   modelled depths vs Gulbaz et al. (2018) at Ikitelli OSB, Evren,
                   Cobancesme; event loss vs reported economic loss.

Pure NumPy / pandas / Pillow - runs on a laptop without GIS libraries.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from .vulnerability import mean_damage_ratio

# --- local metric projection (good to <0.5 % over western Istanbul) ---------
LON0, LAT0 = 28.8, 41.0
KX = np.cos(np.radians(LAT0)) * 111_320.0
KY = 110_574.0


def to_xy(lon, lat):
    return (np.asarray(lon) - LON0) * KX, (np.asarray(lat) - LAT0) * KY


# ---------------------------------------------------------------------------
# DEM
# ---------------------------------------------------------------------------
class DEM:
    """Copernicus GLO-30 GeoTIFF read with Pillow (no GDAL needed)."""

    def __init__(self, path: str):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(path)
        t = im.tag_v2
        self.res_x, self.res_y = t[33550][0], t[33550][1]
        self.lon0, self.lat0 = t[33922][3], t[33922][4]
        z = np.array(im, dtype=np.float32)
        # GLO-30 is a surface model (includes roofs / trees): a 3x3 minimum
        # filter (~90 m) gives a better estimate of the ground level.
        p = np.pad(z, 1, mode="edge")
        zmin = z.copy()
        for dy in range(3):
            for dx in range(3):
                zmin = np.minimum(zmin, p[dy:dy + z.shape[0], dx:dx + z.shape[1]])
        self.z = zmin

    def sample(self, lon, lat):
        c = np.clip(((np.asarray(lon) - self.lon0) / self.res_x).astype(int), 0, self.z.shape[1] - 1)
        r = np.clip(((self.lat0 - np.asarray(lat)) / self.res_y).astype(int), 0, self.z.shape[0] - 1)
        return self.z[r, c]


# ---------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------
STREAM_FACTOR = {"main": 1.0, "river": 0.8, "canal": 0.8, "stream": 0.5, "drain": 0.3, "ditch": 0.3}


def _densify(coords, step_m=25.0):
    c = np.asarray(coords, dtype=float)
    x, y = to_xy(c[:, 0], c[:, 1])
    out_lon, out_lat = [c[0, 0]], [c[0, 1]]
    for i in range(len(c) - 1):
        seg = np.hypot(x[i + 1] - x[i], y[i + 1] - y[i])
        n = max(1, int(seg // step_m))
        t = np.arange(1, n + 1) / n
        out_lon.extend(c[i, 0] + t * (c[i + 1, 0] - c[i, 0]))
        out_lat.extend(c[i, 1] + t * (c[i + 1, 1] - c[i, 1]))
    return np.array(out_lon), np.array(out_lat)


def load_streams(river_systems_path: str, waterways_path: str, dem: DEM, factors: dict | None = None) -> pd.DataFrame:
    rows = []
    rs = json.load(open(river_systems_path, encoding="utf-8"))["features"]
    for f in rs:
        p = f["properties"]
        cls = "main" if p.get("role") == "main_stream" else "stream"
        lon, lat = _densify(f["geometry"]["coordinates"])
        rows.append(pd.DataFrame({"lon": lon, "lat": lat, "cls": cls, "name": p.get("river_name"),
                                  "system": p.get("river_name")}))
    ww = json.load(open(waterways_path, encoding="utf-8"))["features"]
    for f in ww:
        p = f["properties"]
        cls = p.get("waterway")
        if cls not in STREAM_FACTOR or f["geometry"]["type"] != "LineString":
            continue
        lon, lat = _densify(f["geometry"]["coordinates"])
        rows.append(pd.DataFrame({"lon": lon, "lat": lat, "cls": cls, "name": p.get("name"), "system": "local"}))
    s = pd.concat(rows, ignore_index=True)
    s["system"] = s["system"].fillna("local")
    s["factor"] = s["cls"].map(factors or STREAM_FACTOR)
    s["z"] = dem.sample(s.lon, s.lat)
    s["x"], s["y"] = to_xy(s.lon, s.lat)
    return s


# ---------------------------------------------------------------------------
# Buildings / exposure
# ---------------------------------------------------------------------------
DEFAULT_LEVELS = {"apartments": 5, "residential": 4, "house": 2, "detached": 2, "semidetached_house": 2,
                  "terrace": 2, "industrial": 1, "warehouse": 1, "commercial": 3, "retail": 2, "office": 5,
                  "school": 3, "university": 4, "hospital": 5, "mosque": 1, "yes": 3}
INDUSTRIAL = {"industrial", "warehouse", "manufacture", "factory", "hangar", "storage_tank"}
COMMERCIAL = {"commercial", "retail", "office", "school", "university", "hospital", "public", "hotel",
              "kindergarten", "mosque", "civic", "government", "supermarket"}
EXCLUDE = {"construction", "roof", "ruins", "collapsed", "shed", "garage", "garages", "hut", "container"}


def load_buildings(path: str, dem: DEM, ex: dict) -> pd.DataFrame:
    fs = json.load(open(path, encoding="utf-8"))["features"]
    recs = []
    for f in fs:
        p = f.get("properties") or {}
        btype = p.get("building", "yes")
        if btype in EXCLUDE or f["geometry"]["type"] != "Polygon":
            continue
        ring = np.asarray(f["geometry"]["coordinates"][0], dtype=float)
        x, y = to_xy(ring[:, 0], ring[:, 1])
        area = 0.5 * abs(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))
        if area < ex["min_footprint_m2"]:
            continue
        try:
            lv = float(str(p.get("building:levels", "")).split(";")[0].replace(",", "."))
        except ValueError:
            lv = np.nan
        if not (0 < lv < 60):
            lv = DEFAULT_LEVELS.get(btype, 3)
        recs.append((p.get("id"), ring[:-1, 0].mean(), ring[:-1, 1].mean(), btype, area, lv))
    b = pd.DataFrame(recs, columns=["osm_id", "lon", "lat", "building", "footprint_m2", "levels"])
    b["occupancy"] = np.where(b.building.isin(INDUSTRIAL), "industrial",
                              np.where(b.building.isin(COMMERCIAL), "commercial", "residential"))
    cost = b.occupancy.map(ex["cost_eur_per_m2"])
    b["building_value"] = b.footprint_m2 * b.levels * cost
    b["contents_value"] = b.building_value * b.occupancy.map(ex["contents_ratio"])
    # only ground floor + basement are reachable by flood water
    b["exposed_share"] = np.minimum(1.0, (1.0 + ex["basement_share"]) / b.levels)
    b["value_at_risk"] = (b.building_value + b.contents_value) * b.exposed_share
    b["z_ground"] = dem.sample(b.lon, b.lat)
    b["x"], b["y"] = to_xy(b.lon, b.lat)
    return b


# ---------------------------------------------------------------------------
# HAND-type flood-zone index
# ---------------------------------------------------------------------------
def flood_zone_index(b: pd.DataFrame, s: pd.DataFrame, radius_m=1500.0, bin_m=500.0,
                     head_loss_m_per_km=1.0, ref_stage_m=3.0) -> pd.DataFrame:
    """For every building pick the stream point that would flood it first
    (max of factor*ref_stage - HAND_eff) and store HAND_eff, factor, distance."""
    bx, by = b.x.to_numpy(), b.y.to_numpy()
    sx, sy, sz, sf = (s[c].to_numpy() for c in ("x", "y", "z", "factor"))
    sbx, sby = np.floor(sx / bin_m).astype(np.int64), np.floor(sy / bin_m).astype(np.int64)
    lookup = pd.Series(np.arange(len(sx))).groupby([sbx, sby]).apply(np.asarray).to_dict()
    r = int(np.ceil(radius_m / bin_m))

    bbx, bby = np.floor(bx / bin_m).astype(np.int64), np.floor(by / bin_m).astype(np.int64)
    groups = pd.Series(np.arange(len(bx))).groupby([bbx, bby]).apply(np.asarray).to_dict()
    hand = np.full(len(b), np.inf)
    fac = np.zeros(len(b))
    dist = np.full(len(b), np.inf)
    sidx = np.full(len(b), -1)
    zb = b.z_ground.to_numpy()
    for (kx, ky), idx in groups.items():
        cand = [lookup[(kx + i, ky + j)] for i in range(-r, r + 1) for j in range(-r, r + 1)
                if (kx + i, ky + j) in lookup]
        if not cand:
            continue
        c = np.concatenate(cand)
        d = np.hypot(bx[idx, None] - sx[None, c], by[idx, None] - sy[None, c])
        h = np.maximum(zb[idx, None] - sz[None, c], 0) + head_loss_m_per_km * d / 1000.0
        h = np.where(d <= radius_m, h, np.inf)
        score = sf[None, c] * ref_stage_m - h
        j = np.argmax(score, axis=1)
        rows = np.arange(len(idx))
        hand[idx] = h[rows, j]
        fac[idx] = np.where(np.isfinite(h[rows, j]), sf[c][j], 0)
        dist[idx] = d[rows, j]
        sidx[idx] = np.where(np.isfinite(h[rows, j]), c[j], -1)
    out = b.copy()
    out["hand_eff_m"], out["stream_factor"], out["dist_stream_m"] = hand, fac, dist
    out["stream_idx"] = sidx
    return out


# ---------------------------------------------------------------------------
# Hazard -> depth -> loss
# ---------------------------------------------------------------------------
def stage(p_mm, hz: dict):
    return hz["stage_m_per_mm"] * np.maximum(0.0, np.asarray(p_mm) - hz["stage_threshold_mm"])


def driving_rainfall(p_stream: np.ndarray, s: pd.DataFrame, b: pd.DataFrame) -> np.ndarray:
    """Rainfall that drives the water level at each building's stream.

    p_stream : (n_events, n_stream_points) daily rainfall at stream points.
    Named river systems (Ayamama, Haramidere, Alibey) respond to the
    catchment-average rainfall along the whole system; small local streams
    respond to the rainfall at the stream point itself.
    """
    sys_codes, sys_idx = np.unique(s["system"].to_numpy(), return_inverse=True)
    drive = p_stream.copy()
    for k, name in enumerate(sys_codes):
        if name == "local":
            continue
        m = sys_idx == k
        drive[:, m] = p_stream[:, m].mean(axis=1, keepdims=True)
    j = b["stream_idx"].to_numpy()
    out = np.zeros((p_stream.shape[0], len(b)))
    ok = j >= 0
    out[:, ok] = drive[:, j[ok]]
    return out


def building_depth(p_drive: np.ndarray, b: pd.DataFrame, hz: dict) -> np.ndarray:
    """p_drive: (n_events, n_buildings) driving rainfall (see driving_rainfall)."""
    s = stage(p_drive, hz) * b.stream_factor.to_numpy()[None, :]
    return np.maximum(0.0, s - b.hand_eff_m.to_numpy()[None, :])


def building_loss(depth: np.ndarray, b: pd.DataFrame) -> np.ndarray:
    dr = mean_damage_ratio(depth, b.occupancy.to_numpy())
    return dr * b.value_at_risk.to_numpy()[None, :]


def idw_rainfall(stations: pd.DataFrame, lon, lat, col="p_event_mm", power=2.0) -> np.ndarray:
    sx, sy = to_xy(stations.lon.to_numpy(), stations.lat.to_numpy())
    bx, by = to_xy(lon, lat)
    d = np.hypot(np.asarray(bx)[:, None] - sx[None, :], np.asarray(by)[:, None] - sy[None, :]) + 1.0
    w = 1.0 / d ** power
    return (w * stations[col].to_numpy()[None, :]).sum(1) / w.sum(1)
