"""
Building-level flood model for western Istanbul + validation against 8-9 Sept 2009.

    python run_building_level.py
    python run_building_level.py --data-dir "D:/data/istanbul_open_data"

Needs (open data, not stored in this repo because of size):
    ayamama_buildings.geojson, ayamama_waterways.geojson,
    ayamama_river_systems.geojson   (OpenStreetMap extracts)
    rasters_COP30.tar.gz            (Copernicus DEM GLO-30)
Outputs -> outputs/building_level/, data/exposure/west_istanbul_buildings.csv.gz
"""
from __future__ import annotations

import argparse
import json
import os
import tarfile
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import building_level as bl
from src import hazard, financial
from src.plots import NAVY, ORANGE, RED, TEAL, GREY

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = "outputs/building_level"

# Gulbaz et al. (2018), J. Hydrol. Eng. 24(1): 05018026 - Table 2 (2009 event, Ayamama)
GULBAZ_2018 = pd.DataFrame({
    "location": ["Ikitelli OSB", "Ataturk", "Inonu", "Evren", "Cobancesme"],
    "observed_depth_m": [0.85, 0.87, 1.58, 2.19, 13.75],
    # v0.3: neighbourhood centroids geocoded with OpenStreetMap Nominatim (2026-11-22);
    # Evren Mahallesi (Bagcilar) was renamed 15 Temmuz Mahallesi in 2016.
    "lat": [41.0699, 41.0504, 41.0234, 41.0379, 40.9997],
    "lon": [28.8051, 28.7974, 28.7965, 28.8195, 28.8226],
    "note": ["", "watermark ~1 m", "", "watermark ~2 m",
             "flow blocked at highway culvert (watermark 12-14 m) - not representable without hydraulics"],
})


def prepare(cfg_bl, data_dir):
    f = cfg_bl["files"]
    dem_path = os.path.join("data", "external", f["dem_tif"])
    if not os.path.exists(dem_path):
        os.makedirs(os.path.dirname(dem_path), exist_ok=True)
        with tarfile.open(os.path.join(data_dir, f["dem_archive"])) as t:
            t.extract(f["dem_tif"], path=os.path.dirname(dem_path), **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    dem = bl.DEM(dem_path)
    fz = cfg_bl["flood_zone"]
    s = bl.load_streams(os.path.join(data_dir, f["river_systems"]), os.path.join(data_dir, f["waterways"]),
                        dem, fz["stream_factor"])
    b = bl.load_buildings(os.path.join(data_dir, f["buildings"]), dem, cfg_bl["exposure"])
    gf = f.get("buildings_gapfill")
    if gf and os.path.exists(os.path.join(data_dir, gf)):  # v0.3: Microsoft footprints where OSM has none
        g = bl.load_buildings(os.path.join(data_dir, gf), dem, cfg_bl["exposure"])
        print(f"[buildings] gap-fill: +{len(g):,} Microsoft footprints with no OSM overlap")
        b = pd.concat([b, g], ignore_index=True)
    b = bl.flood_zone_index(b, s, radius_m=fz["search_radius_m"], head_loss_m_per_km=fz["head_loss_m_per_km"])
    return dem, s, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--years", type=int, default=None)
    a = ap.parse_args()
    os.chdir(ROOT)
    cfg = json.load(open("config.json", encoding="utf-8"))
    cb = cfg["building_level"]
    data_dir = a.data_dir or os.path.normpath(os.path.join(ROOT, cb["data_dir"]))
    n_years = a.years or cb["n_sim_years"]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    dem, s, b = prepare(cb, data_dir)
    hz = cb["hazard"]
    tiv = float((b.building_value + b.contents_value).sum())
    print(f"[buildings] {len(b):,} buildings | TIV EUR {tiv / 1e9:.1f} bn | "
          f"{(b.hand_eff_m < 3).mean() * 100:.1f}% within 3 m of a nearby stream level")

    # ---------------- 2009 observed event ----------------
    st = pd.read_csv("data/hazard/stations_2009_sep.csv")
    st["p_event_mm"] = st[["obs_8sep_mm", "obs_9sep_mm"]].max(axis=1)
    p_stream = bl.idw_rainfall(st, s.lon, s.lat)[None, :]
    p_drive = bl.driving_rainfall(p_stream, s, b)
    d09 = bl.building_depth(p_drive, b, hz)[0]
    l09 = bl.building_loss(d09[None, :], b)[0]
    b["depth_2009_m"], b["loss_2009_eur"] = d09.round(2), l09.round(0)
    on_ay = (s.system.to_numpy()[b.stream_idx.clip(0)] == "Ayamama Deresi") & (b.stream_idx.to_numpy() >= 0)
    fa = d09[on_ay & (d09 > 0)]
    ay_rain = p_stream[0][(s.system == "Ayamama Deresi").to_numpy()].mean()
    val = {
        "ayamama_catchment_rain_2009_mm": float(ay_rain),
        "ayamama_main_stage_m": float(bl.stage(ay_rain, hz)),
        "ayamama_flooded_buildings": int(len(fa)),
        "ayamama_depth_median_m": float(np.median(fa)) if len(fa) else 0.0,
        "ayamama_depth_p90_m": float(np.percentile(fa, 90)) if len(fa) else 0.0,
        "ayamama_depth_max_m": float(fa.max()) if len(fa) else 0.0,
        "observed_depth_range_m_excl_blockage": [0.85, 2.19],
        "all_flooded_buildings": int((d09 > 0).sum()),
        "event_loss_eur": float(l09.sum()),
        "ayamama_event_loss_eur": float(l09[on_ay].sum()),
        "reported_economic_loss_2009_usd": [70e6, 175e6],
    }
    GULBAZ_2018.assign(model_main_channel_stage_m=round(val["ayamama_main_stage_m"], 2),
                       model_p90_building_depth_m=round(val["ayamama_depth_p90_m"], 2)) \
        .to_csv(f"{OUT}/validation_2009_vs_gulbaz2018.csv", index=False)
    # v0.3 point-by-point check: flooded buildings on the Ayamama within 1 km of each location
    pts = []
    blat, blon = b.lat.to_numpy(), b.lon.to_numpy()
    for _, p in GULBAZ_2018.iterrows():
        dk = np.hypot((blat - p.lat) * 111.0, (blon - p.lon) * 111.0 * np.cos(np.radians(41.0)))
        sel = on_ay & (dk <= 1.0) & (d09 > 0)
        dd = d09[sel]
        pts.append(dict(location=p.location, observed_depth_m=p.observed_depth_m,
                        n_flooded_buildings_1km=int(sel.sum()),
                        model_median_m=round(float(np.median(dd)), 2) if len(dd) else 0.0,
                        model_p90_m=round(float(np.percentile(dd, 90)), 2) if len(dd) else 0.0,
                        model_max_m=round(float(dd.max()), 2) if len(dd) else 0.0))
    pv = pd.DataFrame(pts)
    m = pv[pv.location != "Cobancesme"]
    for col in ["model_median_m", "model_p90_m", "model_max_m"]:
        e = m[col] - m.observed_depth_m
        val[f"pointwise_{col}_MAE"] = round(float(e.abs().mean()), 2)
        val[f"pointwise_{col}_RMSE"] = round(float(np.sqrt((e ** 2).mean())), 2)
        val[f"pointwise_{col}_bias"] = round(float(e.mean()), 2)
    pv.to_csv(f"{OUT}/validation_2009_pointwise.csv", index=False)
    print(pv.to_string(index=False))

    # ---------------- stochastic (same event set as portfolio model) --------
    rng = np.random.default_rng(cfg["random_seed"])
    cells = hazard.grid_cells()
    amax, synthetic = hazard.load_annual_max(cfg, cells, rng)
    gev = hazard.fit_cells(amax, regional_shape=cfg["hazard"].get("regional_shape", True))
    ev = hazard.simulate_event_set(gev, n_years, cfg["hazard"]["corr_length_km"], rng,
                                    cfg["hazard"].get("max_daily_rain_mm", 400.0))
    from src.exposure import nearest_cell
    sc = pd.Index(gev.cell_id).get_indexer(nearest_cell(s.lat, s.lon, cells))
    # only buildings that can flood at all at 400 mm/day
    can = (b.stream_factor * bl.stage(400, hz) > b.hand_eff_m).to_numpy()
    bc = b[can].reset_index(drop=True)
    annual = np.zeros(n_years)
    for i in range(0, n_years, 500):
        p_drive = bl.driving_rainfall(ev[i:i + 500][:, sc], s, bc)
        annual[i:i + 500] = bl.building_loss(bl.building_depth(p_drive, bc, hz), bc).sum(1)
    rp = financial.loss_at_rp(annual)
    summ = {"hazard_data": "SYNTHETIC_DEMO" if synthetic else "ERA5", "n_buildings": len(b),
            "TIV_EUR": tiv, "buildings_can_flood": int(can.sum()),
            "AAL_EUR": float(annual.mean()), "PML_EUR_by_RP": rp,
            "TVaR_99_5_EUR": financial.tvar(annual, 0.995),
            "validation_2009": val}
    json.dump(summ, open(f"{OUT}/summary.json", "w"), indent=2, default=float)
    pd.DataFrame([{"return_period_yrs": k, "loss_EUR": v} for k, v in rp.items()]).round(0) \
        .to_csv(f"{OUT}/pml_by_return_period.csv", index=False)
    cols = ["osm_id", "lon", "lat", "building", "occupancy", "levels", "footprint_m2", "building_value",
            "contents_value", "value_at_risk", "z_ground", "hand_eff_m", "stream_factor", "dist_stream_m",
            "depth_2009_m", "loss_2009_eur"]
    b[cols].replace(np.inf, np.nan).round(3).to_csv("data/exposure/west_istanbul_buildings.csv.gz", index=False)

    figures(b, s, st, d09, annual, rp, val, synthetic)
    m = 1e6
    print(f"\n2009 event   : Ayamama stage {val['ayamama_main_stage_m']:.2f} m | flooded buildings on Ayamama "
          f"{val['ayamama_flooded_buildings']} (median {val['ayamama_depth_median_m']:.2f} m, "
          f"p90 {val['ayamama_depth_p90_m']:.2f} m) vs observed 0.85-2.19 m")
    print(f"               total flooded buildings {val['all_flooded_buildings']:,} | "
          f"event loss EUR {val['event_loss_eur'] / m:.0f} m (reported 2009: USD 70-175 m)")
    print(f"Stochastic   : AAL EUR {annual.mean() / m:.1f} m | 1-in-100 EUR {rp[100] / m:.0f} m | "
          f"1-in-200 EUR {rp[200] / m:.0f} m | {'DEMO hazard' if synthetic else 'ERA5'}")
    print(f"Run time {time.time() - t0:.0f}s")


def figures(b, s, st, d09, annual, rp, val, synthetic):
    # 1 - rainfall footprint 2009
    fig, ax = plt.subplots(figsize=(8, 5))
    g = np.meshgrid(np.linspace(28.0, 29.3, 140), np.linspace(40.85, 41.45, 70))
    pg = bl.idw_rainfall(st, g[0].ravel(), g[1].ravel()).reshape(g[0].shape)
    cf = ax.contourf(g[0], g[1], pg, levels=np.arange(0, 221, 20), cmap="Blues")
    plt.colorbar(cf, ax=ax, label="Daily rainfall, max of 8 & 9 Sept 2009 (mm)")
    main = s[s.cls == "main"]
    ax.scatter(main.lon, main.lat, s=0.3, c=NAVY, label="Ayamama / Haramidere / Alibey")
    ax.scatter(st.lon, st.lat, c=ORANGE, edgecolor="k", s=40, zorder=3, label="MGM / AKOM stations")
    for r in st.itertuples():
        if 28.0 <= r.lon <= 29.3:
            ax.annotate(f"{r.station} {r.p_event_mm:.0f}", (r.lon, r.lat), fontsize=7, xytext=(3, 3),
                        textcoords="offset points")
    ax.set(xlim=(28.0, 29.3), ylim=(40.85, 41.45), xlabel="Longitude", ylabel="Latitude",
           title="Observed rainfall footprint, 8-9 September 2009 (IDW of station totals)")
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout(); fig.savefig(f"{OUT}/bl_01_rainfall_2009.png", dpi=130); plt.close(fig)

    # 2 - modelled depths at buildings, Ayamama zoom
    fig, ax = plt.subplots(figsize=(7, 7))
    box = (b.lon.between(28.74, 28.87)) & (b.lat.between(40.96, 41.14))
    bb = b[box]
    ax.scatter(bb.lon, bb.lat, s=0.4, c="#d9d9d9", label="Buildings (OSM)")
    ss = s[(s.lon.between(28.74, 28.87)) & (s.lat.between(40.96, 41.14))]
    ax.scatter(ss.lon, ss.lat, s=0.3, c=TEAL, label="Streams")
    fl = bb[bb.depth_2009_m > 0]
    sc = ax.scatter(fl.lon, fl.lat, s=6, c=fl.depth_2009_m, cmap="YlOrRd", vmin=0, vmax=2, zorder=3,
                    label="Flooded buildings (model)")
    plt.colorbar(sc, ax=ax, shrink=0.7, label="Modelled water depth at building (m)")
    ax.set(xlabel="Longitude", ylabel="Latitude", aspect=1 / np.cos(np.radians(41)),
           title="Ayamama valley - modelled 2009 flood depths at buildings")
    ax.text(0.01, 0.01, "OSM building coverage is incomplete in parts of Bagcilar / Bahcelievler",
            transform=ax.transAxes, fontsize=7, color=GREY)
    ax.legend(loc="upper right", fontsize=7, markerscale=4)
    fig.tight_layout(); fig.savefig(f"{OUT}/bl_02_depths_2009_ayamama.png", dpi=130); plt.close(fig)

    # 3 - validation
    fig, ax = plt.subplots(figsize=(7, 3.8))
    obs = GULBAZ_2018[GULBAZ_2018.location != "Cobancesme"]
    ax.barh(obs.location, obs.observed_depth_m, color=GREY, label="Gulbaz et al. (2018): observed / modelled")
    for v, lab, col in [(val["ayamama_depth_median_m"], "This model: median", TEAL),
                        (val["ayamama_depth_p90_m"], "This model: 90th pct", ORANGE),
                        (val["ayamama_main_stage_m"], "This model: main-channel stage", RED)]:
        ax.axvline(v, color=col, lw=2, label=f"{lab} ({v:.2f} m)")
    ax.set(xlabel="Flood depth (m)", title="2009 Ayamama flood depths: model vs published study")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(f"{OUT}/bl_03_validation_2009.png", dpi=130); plt.close(fig)

    # 4 - EP curve
    ep = financial.ep_curve(annual)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    m = ep.return_period <= 1000
    ax.plot(ep.return_period[m], ep.loss[m] / 1e6, color=NAVY, lw=2, label="Stochastic (10,000 yrs)")
    ax.axhline(val["event_loss_eur"] / 1e6, color=RED, ls="--", lw=1.2,
               label=f"2009 observed rainfall replay: EUR {val['event_loss_eur'] / 1e6:.0f} m")
    ax.scatter([200], [rp[200] / 1e6], color=RED, zorder=4)
    ax.set_xscale("log")
    ax.set(xlabel="Return period (years)", ylabel="Economic loss, buildings + contents (EUR m)",
           title="Building-level EP curve - western Istanbul", xlim=(2, 1000))
    if synthetic:
        ax.text(0.99, 0.99, "DEMO hazard - replace with ERA5", transform=ax.transAxes, ha="right", va="top",
                fontsize=7, color=RED)
    ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(f"{OUT}/bl_04_ep_curve.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
