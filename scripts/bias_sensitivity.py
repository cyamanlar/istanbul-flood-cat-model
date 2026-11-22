"""
Sensitivity of portfolio results to the ERA5 bias-correction factor.

    python scripts/bias_sensitivity.py 1.0 1.4 1.8 2.2
Output: outputs/tables/bias_sensitivity.csv
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from src import exposure, financial, hazard  # noqa: E402


def main():
    factors = [float(x) for x in sys.argv[1:]] or [1.0, 1.4, 1.8, 2.2]
    base = json.load(open("config.json", encoding="utf-8"))
    rows = []
    for f in factors:
        cfg = json.loads(json.dumps(base))
        cfg["hazard"].pop("bias_correction", None)  # uniform factor test (v0.2 style)
        cfg["hazard"]["bias_correction_factor"] = f
        rng = np.random.default_rng(cfg["random_seed"])
        cells = hazard.grid_cells()
        amax, synthetic = hazard.load_annual_max(cfg, cells, rng)
        gev = hazard.fit_cells(amax, regional_shape=cfg["hazard"].get("regional_shape", True))
        ev = hazard.simulate_event_set(gev, cfg["n_sim_years"], cfg["hazard"]["corr_length_km"], rng,
                                    cfg["hazard"].get("max_daily_rain_mm", 400.0))
        loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))
        res = financial.run_losses(ev, gev, loc, cfg, np.random.default_rng(cfg["random_seed"] + 1))
        s = financial.summarise(res, loc.TIV.sum())
        rows.append({"bias_factor": f, "hazard": "SYNTHETIC" if synthetic else "ERA5",
                     "mean_RL200_mm": gev.RL200_mm.mean(), "AAL_EUR": s["AAL_gross_EUR"],
                     "AAL_per_mille": s["AAL_rate_per_mille_TIV"], "loss_1in200_EUR": s["VaR_99_5_1in200_EUR"],
                     "loss_1in200_pct_TIV": s["VaR_99_5_pct_TIV"]})
        print(rows[-1])
    pd.DataFrame(rows).round(3).to_csv("outputs/tables/bias_sensitivity.csv", index=False)


if __name__ == "__main__":
    main()
