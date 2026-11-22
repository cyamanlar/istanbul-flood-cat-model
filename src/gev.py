"""
Generalised Extreme Value (GEV) utilities - pure NumPy, no SciPy dependency.

Parameterisation follows Hosking (1990) / Hosking & Wallis (1997):

    F(x) = exp( -[1 - k (x - xi) / alpha]^(1/k) )      k != 0

k < 0  -> heavy (Frechet-type) upper tail, typical for extreme daily rainfall.
Note: SciPy's `genextreme` uses c = k (same sign convention as Hosking).

Parameters are estimated with L-moments, which are robust for the short
annual-maximum series (~75 years) available from ERA5 (1950-present).
"""
from __future__ import annotations

import math
import numpy as np


def sample_lmoments(x: np.ndarray) -> tuple[float, float, float]:
    """Return (l1, l2, t3) - first two L-moments and L-skewness."""
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    if n < 10:
        raise ValueError("Need at least 10 annual maxima for a stable GEV fit")
    j = np.arange(1, n + 1)
    b0 = x.mean()
    b1 = np.sum((j - 1) / (n - 1) * x) / n
    b2 = np.sum((j - 1) * (j - 2) / ((n - 1) * (n - 2)) * x) / n
    l1 = b0
    l2 = 2 * b1 - b0
    l3 = 6 * b2 - 6 * b1 + b0
    return l1, l2, l3 / l2


def fit_gev_lmom(x: np.ndarray) -> dict:
    """Fit GEV by L-moments (Hosking 1985 rational approximation)."""
    l1, l2, t3 = sample_lmoments(x)
    c = 2.0 / (3.0 + t3) - math.log(2) / math.log(3)
    k = 7.8590 * c + 2.9554 * c ** 2
    g = math.gamma(1 + k)
    alpha = l2 * k / ((1 - 2 ** (-k)) * g)
    xi = l1 - alpha * (1 - g) / k
    return {"xi": xi, "alpha": alpha, "k": k, "l1": l1, "l2": l2, "t3": t3}


def gev_quantile(F, xi: float, alpha: float, k: float):
    """Inverse CDF. F may be an array of non-exceedance probabilities."""
    F = np.clip(np.asarray(F, dtype=float), 1e-12, 1 - 1e-12)
    y = -np.log(F)
    if abs(k) < 1e-8:
        return xi - alpha * np.log(y)
    return xi + alpha * (1 - y ** k) / k


def return_level(rp_years, xi: float, alpha: float, k: float):
    """Rainfall depth with a given return period (years)."""
    rp = np.asarray(rp_years, dtype=float)
    return gev_quantile(1 - 1 / rp, xi, alpha, k)


def gev_sample(n: int, xi: float, alpha: float, k: float, rng: np.random.Generator):
    return gev_quantile(rng.uniform(size=n), xi, alpha, k)


# --- standard normal CDF without SciPy -------------------------------------
_erf = np.frompyfunc(math.erf, 1, 1)


def norm_cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + _erf(np.asarray(z) / math.sqrt(2.0)).astype(float))
