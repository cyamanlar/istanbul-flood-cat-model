"""
Istanbul Pluvial Flood Catastrophe Model - end-to-end run.

    python run_model.py                 # uses config.json
    python run_model.py --years 50000   # larger stochastic set

Outputs -> outputs/tables, outputs/figures, outputs/results_summary.json,
           data/exposure (OED), oasis/ (Oasis LMF model files)
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import pandas as pd

from src import exposure, financial, hazard, plots
from src.oasis_export import export_oasis

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    ap.add_argument("--years", type=int, default=None)
    ap.add_argument("--no-oasis", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)
    cfg = json.load(open(args.config))
    if args.years:
        cfg["n_sim_years"] = args.years
    rng = np.random.default_rng(cfg["random_seed"])
    t0 = time.time()
    for d in ("outputs/tables", "outputs/figures", "data/hazard", "data/exposure", "oasis"):
        os.makedirs(d, exist_ok=True)

    # 1 HAZARD ----------------------------------------------------------------
    cells = hazard.grid_cells()
    amax, synthetic = hazard.load_annual_max(cfg, cells, rng)
    if synthetic:
        amax.to_csv("data/hazard/synthetic_annual_max_DEMO.csv", index=False)
    gev = hazard.fit_cells(amax, regional_shape=cfg["hazard"].get("regional_shape", True))
    gev.round(3).to_csv("outputs/tables/hazard_gev_return_levels.csv", index=False)
    events = hazard.simulate_event_set(gev, cfg["n_sim_years"], cfg["hazard"]["corr_length_km"], rng,
                                    cfg["hazard"].get("max_daily_rain_mm", 400.0))
    print(f"[hazard]   {'SYNTHETIC DEMO' if synthetic else 'ERA5'} | {len(gev)} cells | "
          f"{events.shape[0]:,} simulated years")

    # 2 EXPOSURE --------------------------------------------------------------
    # exposure uses its own random stream so that hazard sampling and the
    # (illustrative) portfolio can be varied independently
    loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))
    oed_loc, oed_acc = exposure.to_oed(loc, cfg)
    oed_loc.to_csv("data/exposure/istanbul_portfolio_OED_location.csv", index=False)
    oed_acc.to_csv("data/exposure/istanbul_portfolio_OED_account.csv", index=False)
    tiv = loc["TIV"].sum()
    print(f"[exposure] {len(loc):,} locations | TIV EUR {tiv / 1e9:.2f} bn | "
          f"{loc.flood_prone.mean() * 100:.1f}% of locations flood-prone")

    # 3-4 VULNERABILITY + FINANCIAL, per climate scenario ---------------------
    curves, rows, base_res = {}, [], None
    for dT in cfg["climate_scenarios_degC"]:
        ev = hazard.climate_scale(events, dT, cfg["hazard"]["climate_scaling_per_degC"])
        res = financial.run_losses(ev, gev, loc, cfg, np.random.default_rng(cfg["random_seed"] + 1))
        s = financial.summarise(res, tiv)
        label = "Baseline (current climate)" if dT == 0 else f"+{dT:g} C warming"
        curves[label] = financial.ep_curve(res["gross"])
        rows.append({"warming_degC": dT, "AAL_gross_EUR": s["AAL_gross_EUR"],
                     "VaR_1in200_EUR": s["VaR_99_5_1in200_EUR"], "TVaR_99_5_EUR": s["TVaR_99_5_EUR"]})
        if dT == 0:
            base_res, base = res, s
    climate = pd.DataFrame(rows)
    climate.round(0).to_csv("outputs/tables/climate_stress_test.csv", index=False)

    # Historical-style deterministic scenario
    sc = financial.run_losses(hazard.scenario_2009_footprint(gev), gev, loc,
                              {**cfg, "vulnerability": {**cfg["vulnerability"], "secondary_uncertainty_cv": 0}},
                              rng)
    sc_loss = float(sc["gross"][0])
    sc_rp = float(1 / max((base_res["gross"] >= sc_loss).mean(), 1 / len(base_res["gross"])))

    # 5 TABLES ----------------------------------------------------------------
    ep = curves["Baseline (current climate)"]
    rp_tab = pd.DataFrame([{"return_period_yrs": k, "exceedance_prob": 1 / k, "gross_loss_EUR": v,
                            "pct_of_TIV": v / tiv * 100} for k, v in base["PML_gross_EUR_by_RP"].items()])
    rp_tab.round(4).to_csv("outputs/tables/pml_by_return_period.csv", index=False)
    ep.iloc[::max(1, len(ep) // 2000)].round(2).to_csv("outputs/tables/ep_curve_baseline.csv", index=False)
    contrib = financial.tail_contribution(base_res["by_district"], base_res["gross"])
    aal_d = base_res["by_district"].mean()
    tiv_d = loc.groupby("district")["TIV"].sum()
    dist_tab = pd.DataFrame({"TIV_EUR": tiv_d, "AAL_EUR": aal_d, "AAL_per_mille": aal_d / tiv_d * 1000,
                             "coTVaR_99_5_EUR": contrib}).sort_values("coTVaR_99_5_EUR", ascending=False)
    dist_tab.round(2).to_csv("outputs/tables/district_risk_ranking.csv")

    summary = {**base, "hazard_data": "SYNTHETIC_DEMO" if synthetic else "ERA5",
               "n_sim_years": cfg["n_sim_years"], "n_locations": len(loc),
               "scenario_2009_style_gross_loss_EUR": sc_loss,
               "scenario_2009_style_implied_return_period_yrs": sc_rp,
               "climate_stress_test": climate.to_dict(orient="records")}
    json.dump(summary, open("outputs/results_summary.json", "w"), indent=2, default=float)

    # 6 FIGURES ---------------------------------------------------------------
    plots.hazard_map(gev, loc, "outputs/figures/01_hazard_exposure_map.png", synthetic)
    plots.damage_curves("outputs/figures/02_damage_curves.png")
    plots.ep_curves(curves, "outputs/figures/03_ep_curve.png", synthetic, base["VaR_99_5_1in200_EUR"])
    plots.district_contribution(contrib, "outputs/figures/04_tail_risk_by_district.png", synthetic)
    plots.climate_bars(climate, "outputs/figures/05_climate_stress_test.png", synthetic)

    # 7 OASIS LMF EXPORT ------------------------------------------------------
    if not args.no_oasis:
        export_oasis(gev, events[:10000], loc, cfg, "oasis")  # first 10,000 years keep files small

    # REPORT ------------------------------------------------------------------
    m = 1e6
    print("\n================  RESULTS (gross of deductible, EUR)  ================")
    print(f"AAL                 : {base['AAL_gross_EUR'] / m:8.2f} m  ({base['AAL_rate_per_mille_TIV']:.3f} per mille of TIV)")
    for rp, v in base["PML_gross_EUR_by_RP"].items():
        flag = "   <- Solvency II 99.5% VaR" if rp == 200 else ""
        print(f"1-in-{rp:<4d} loss      : {v / m:8.2f} m  ({v / tiv * 100:.2f}% TIV){flag}")
    print(f"TVaR 99.5%          : {base['TVaR_99_5_EUR'] / m:8.2f} m")
    print(f"2009-style scenario : {sc_loss / m:8.2f} m  (~1-in-{sc_rp:.0f} yr on the baseline EP curve)")
    for r in rows[1:]:
        print(f"+{r['warming_degC']:g} C warming     : AAL {r['AAL_gross_EUR'] / m:.2f} m "
              f"(+{(r['AAL_gross_EUR'] / base['AAL_gross_EUR'] - 1) * 100:.0f}%), "
              f"1-in-200 {r['VaR_1in200_EUR'] / m:.1f} m "
              f"(+{(r['VaR_1in200_EUR'] / base['VaR_99_5_1in200_EUR'] - 1) * 100:.0f}%)")
    print(f"\nTop tail-risk districts: {', '.join(contrib.head(5).index)}")
    print(f"Run time {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
