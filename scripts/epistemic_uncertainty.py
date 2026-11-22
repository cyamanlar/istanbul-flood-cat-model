"""
Epistemic uncertainty band for the portfolio results (review points 3 and 2 of
"how to take it forward": separate Monte Carlo error from model uncertainty).

Each run draws one value of every uncertain assumption:
  * ERA5 bias multiplier  ~ lognormal, P5/P95 = 0.89/1.13 (matched-period bootstrap)
  * correlation length    ~ uniform {20, 40, 60} km (radar 2009 event / gauges / v0.2)
  * depth coefficient     ~ uniform x[0.8, 1.2]
  * drainage threshold    ~ uniform x[0.8, 1.2] (flood-prone zones)
  * portfolio realisation ~ one of 20 random illustrative portfolios
and runs 10,000 simulated years. Monte Carlo (sampling) error is estimated
separately by bootstrap of the 50,000-year base run.

    python scripts/epistemic_uncertainty.py [n_runs]      (default 40, ~3 min)
Outputs: outputs/tables/epistemic_uncertainty_runs.csv,
         outputs/tables/epistemic_uncertainty_summary.csv
"""
import os, sys, json
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from src import exposure, financial, hazard

base = json.load(open("config.json", encoding="utf-8"))
n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
out_runs = "outputs/tables/epistemic_uncertainty_runs.csv"
done = pd.read_csv(out_runs) if os.path.exists(out_runs) else pd.DataFrame()
rng = np.random.default_rng(777)
draws = []
sd = np.log(1.13 / 0.89) / (2 * 1.645)
for i in range(n):
    draws.append(dict(run=i, bias_mult=float(np.exp(rng.normal(np.log(np.sqrt(0.89 * 1.13)), sd))),
                      corr_km=int(rng.choice([20, 40, 60])), coef_mult=float(rng.uniform(0.8, 1.2)),
                      drain_mult=float(rng.uniform(0.8, 1.2)), exp_seed=int(5001 + rng.integers(0, 20))))
rows = [] if done.empty else done.to_dict("records")
todo = [d for d in draws if done.empty or d["run"] not in set(done.run)]
import time; t0 = time.time()
for d in todo:
    if time.time() - t0 > 150: break          # resume on the next call
    cfg = json.loads(json.dumps(base)); h = cfg["hazard"]; v = cfg["vulnerability"]["prone"]
    h["bias_multiplier"] = d["bias_mult"]; h["corr_length_km"] = d["corr_km"]
    v["coef_m_per_mm"] *= d["coef_mult"]; v["drainage_capacity_mm"] *= d["drain_mult"]
    cfg["n_sim_years"] = 10000
    r = np.random.default_rng(cfg["random_seed"] + d["run"])
    cells = hazard.grid_cells(); am, _ = hazard.load_annual_max(cfg, cells, r)
    gev = hazard.fit_cells(am, regional_shape=h.get("regional_shape", True))
    ev = hazard.simulate_event_set(gev, cfg["n_sim_years"], h["corr_length_km"], r, h.get("max_daily_rain_mm", 400.0))
    loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(d["exp_seed"]))
    res = financial.run_losses(ev, gev, loc, cfg, np.random.default_rng(cfg["random_seed"] + 1))
    s = financial.summarise(res, loc.TIV.sum())
    rows.append({**d, "AAL_m": s["AAL_gross_EUR"] / 1e6, "L200_m": s["VaR_99_5_1in200_EUR"] / 1e6,
                 "TVaR995_m": s["TVaR_99_5_EUR"] / 1e6})
runs = pd.DataFrame(rows).sort_values("run"); runs.round(4).to_csv(out_runs, index=False)
print(f"{len(runs)}/{n} runs done")
if len(runs) >= n:
    q = runs[["AAL_m", "L200_m", "TVaR995_m"]].quantile([0.05, 0.5, 0.95]).T
    q.columns = ["P5", "P50", "P95"]
    # Monte Carlo error of the 50,000-year base run (bootstrap of years)
    cfg = json.loads(json.dumps(base)); r = np.random.default_rng(cfg["random_seed"])
    cells = hazard.grid_cells(); am, _ = hazard.load_annual_max(cfg, cells, r)
    gev = hazard.fit_cells(am, regional_shape=True)
    ev = hazard.simulate_event_set(gev, cfg["n_sim_years"], cfg["hazard"]["corr_length_km"], r, 400.0)
    loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))
    g = financial.run_losses(ev, gev, loc, cfg, np.random.default_rng(cfg["random_seed"] + 1))["gross"]
    b = np.random.default_rng(9); bs = []
    for _ in range(300):
        x = g[b.integers(0, len(g), len(g))]
        bs.append((x.mean() / 1e6, np.quantile(x, 0.995) / 1e6, financial.tvar(x, 0.995) / 1e6))
    bs = np.array(bs)
    q["MC_error_90pct_halfwidth"] = (np.percentile(bs, 95, axis=0) - np.percentile(bs, 5, axis=0)) / 2
    q.round(2).to_csv("outputs/tables/epistemic_uncertainty_summary.csv")
    print(q.round(2))
    # variance share by driver (rank correlation)
    for c in ["bias_mult", "corr_km", "coef_mult", "drain_mult", "exp_seed"]:
        print(c, "rank corr with L200:", round(runs[c].rank().corr(runs.L200_m.rank()), 2))
