"""
FINANCIAL MODULE + RISK METRICS

Ground-up loss  : GU = TIV x damage ratio
Gross loss      : min(max(GU - deductible, 0), limit)   per location
Annual loss     : the stochastic set holds one dominant event per year, so
                  annual loss = occurrence loss (AEP ~ OEP in this setup).

Metrics delivered to an insurer
  * EP curve (exceedance probability vs loss)
  * AAL  - average annual loss (technical pure premium)
  * PML / VaR at return periods 10 ... 500 years
  * 1-in-200 (VaR 99.5 %)  - Solvency II SCR calibration point
  * TVaR 99.5 %             - tail risk used in ORSA / Swiss Solvency Test (TVaR 99 %)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .vulnerability import mean_damage_ratio, rain_to_depth, sample_damage_ratio


def run_losses(event_set: np.ndarray, gev_cells: pd.DataFrame, loc: pd.DataFrame,
               cfg: dict, rng: np.random.Generator, chunk: int = 1000) -> dict:
    """Compute annual GU and gross losses, plus per-district gross losses."""
    cell_idx = pd.Index(gev_cells["cell_id"]).get_indexer(loc["cell_id"])
    tiv = loc["TIV"].to_numpy()
    ded = tiv * cfg["financial"]["deductible_pct_tiv"]
    lim = tiv * cfg["financial"]["limit_pct_tiv"]
    occ = loc["occupancy"].to_numpy()
    prone = loc["flood_prone"].to_numpy()
    amp = loc["local_amp"].to_numpy()
    districts = loc["district"].to_numpy()
    dist_codes, dist_idx = np.unique(districts, return_inverse=True)

    n = event_set.shape[0]
    gu = np.zeros(n)
    gross = np.zeros(n)
    by_dist = np.zeros((n, len(dist_codes)))
    for s in range(0, n, chunk):
        p = event_set[s:s + chunk][:, cell_idx]
        depth = rain_to_depth(p, prone, amp, cfg["vulnerability"])
        dr = sample_damage_ratio(mean_damage_ratio(depth, occ),
                                 cfg["vulnerability"]["secondary_uncertainty_cv"], rng)
        l_gu = dr * tiv[None, :]
        l_gr = np.minimum(np.maximum(l_gu - ded[None, :], 0), lim[None, :])
        gu[s:s + chunk] = l_gu.sum(1)
        gross[s:s + chunk] = l_gr.sum(1)
        for j in range(len(dist_codes)):
            by_dist[s:s + chunk, j] = l_gr[:, dist_idx == j].sum(1)
    return {"gu": gu, "gross": gross, "by_district": pd.DataFrame(by_dist, columns=dist_codes)}


def ep_curve(annual_loss: np.ndarray) -> pd.DataFrame:
    x = np.sort(annual_loss)[::-1]
    n = x.size
    ep = np.arange(1, n + 1) / n
    return pd.DataFrame({"loss": x, "exceedance_prob": ep, "return_period": 1 / ep})


def loss_at_rp(annual_loss: np.ndarray, rps=(10, 25, 50, 100, 200, 250, 500)) -> dict:
    return {rp: float(np.quantile(annual_loss, 1 - 1 / rp)) for rp in rps}


def tvar(annual_loss: np.ndarray, level: float) -> float:
    v = np.quantile(annual_loss, level)
    return float(annual_loss[annual_loss >= v].mean())


def tail_contribution(by_district: pd.DataFrame, total: np.ndarray, level: float = 0.995) -> pd.Series:
    """Co-TVaR allocation: each district's mean loss in the years where the
    portfolio loss is beyond VaR(level). Sums exactly to portfolio TVaR."""
    v = np.quantile(total, level)
    return by_district[total >= v].mean().sort_values(ascending=False)


def summarise(res: dict, tiv_total: float) -> dict:
    g, gu = res["gross"], res["gu"]
    rp = loss_at_rp(g)
    return {
        "TIV_EUR": tiv_total,
        "AAL_gross_EUR": float(g.mean()),
        "AAL_ground_up_EUR": float(gu.mean()),
        "AAL_rate_per_mille_TIV": float(g.mean() / tiv_total * 1000),
        "loss_std_EUR": float(g.std()),
        "PML_gross_EUR_by_RP": rp,
        "VaR_99_5_1in200_EUR": rp[200],
        "VaR_99_5_pct_TIV": rp[200] / tiv_total * 100,
        "TVaR_99_5_EUR": tvar(g, 0.995),
        "TVaR_99_EUR": tvar(g, 0.99),
        "prob_any_loss": float((g > 0).mean()),
    }
