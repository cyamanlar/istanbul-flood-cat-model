"""Figures for the model report (matplotlib only)."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .vulnerability import DAMAGE_CURVES, DEPTH_M

NAVY, TEAL, ORANGE, RED, GREY = "#1f3b57", "#2a9d8f", "#e9a23b", "#c0392b", "#7f8c8d"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "figure.dpi": 130})


def _flag(ax, synthetic):
    if synthetic:
        ax.text(0.99, 0.99, "DEMO DATA - synthetic hazard, replace with ERA5", transform=ax.transAxes,
                ha="right", va="top", fontsize=7, color=RED, alpha=0.8)


def _meur(x):
    return x / 1e6


def hazard_map(gev: pd.DataFrame, loc: pd.DataFrame, path, synthetic, rp=100):
    fig, ax = plt.subplots(figsize=(8, 4.6))
    lats, lons = sorted(gev.lat.unique()), sorted(gev.lon.unique())
    grid = gev.pivot(index="lat", columns="lon", values=f"RL{rp}_mm").loc[lats, lons]
    im = ax.pcolormesh(np.r_[np.array(lons) - 0.125, lons[-1] + 0.125],
                       np.r_[np.array(lats) - 0.125, lats[-1] + 0.125],
                       grid.values, cmap="Blues", shading="flat", alpha=0.85)
    d = loc.groupby("district").agg(lat=("Latitude", "mean"), lon=("Longitude", "mean"), tiv=("TIV", "sum"))
    ax.scatter(d.lon, d.lat, s=d.tiv / d.tiv.max() * 300, c=ORANGE, edgecolor=NAVY, lw=0.6, zorder=3,
               label="Portfolio TIV by district")
    for name, r in d.iterrows():
        if r.tiv > d.tiv.quantile(0.6):
            ax.annotate(name, (r.lon, r.lat), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    plt.colorbar(im, ax=ax, label=f"1-in-{rp} yr daily rainfall (mm)")
    ax.set(xlabel="Longitude", ylabel="Latitude",
           title=f"Hazard x Exposure: 1-in-{rp} year daily rainfall and insured values, Istanbul")
    ax.legend(loc="lower left", fontsize=8)
    _flag(ax, synthetic)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def damage_curves(path):
    fig, ax = plt.subplots(figsize=(6, 4))
    for (occ, c), col in zip(DAMAGE_CURVES.items(), [NAVY, TEAL, ORANGE]):
        ax.plot(DEPTH_M, c, marker="o", ms=3, color=col, label=occ.capitalize())
    ax.set(xlabel="Water depth above first floor (m)", ylabel="Mean damage ratio",
           title="Depth-damage functions (JRC Europe, Huizinga et al. 2017)", ylim=(0, 1.05))
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def ep_curves(curves: dict, path, synthetic, solvency_point=None):
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    cols = [NAVY, ORANGE, RED, TEAL]
    for (label, ep), col in zip(curves.items(), cols):
        m = ep.return_period <= 1000
        ax.plot(ep.return_period[m], _meur(ep.loss[m]), color=col, lw=2, label=label)
    ax.set_xscale("log")
    for rp in (10, 50, 100, 200, 500):
        ax.axvline(rp, color=GREY, lw=0.6, ls=":")
    if solvency_point:
        ax.scatter([200], [_meur(solvency_point)], color=RED, zorder=5)
        ax.annotate(f"1-in-200 (Solvency II)\nEUR {_meur(solvency_point):.0f} m", (200, _meur(solvency_point)),
                    xytext=(-190, 55), textcoords="offset points", fontsize=8,
                    arrowprops=dict(arrowstyle="->", color=RED))
    ax.set(xlabel="Return period (years, log scale)", ylabel="Gross annual loss (EUR m)",
           title="Exceedance probability curve - Istanbul pluvial flood", xlim=(2, 1000))
    ax.legend(fontsize=8); ax.grid(alpha=0.2)
    _flag(ax, synthetic)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def district_contribution(contrib: pd.Series, path, synthetic, top=12):
    c = _meur(contrib.head(top))[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.barh(c.index, c.values, color=TEAL)
    for i, v in enumerate(c.values):
        ax.text(v, i, f" {v:.1f}", va="center", fontsize=8)
    ax.set(xlabel="Contribution to TVaR 99.5% (EUR m)",
           title="Where does the 1-in-200 tail come from? (co-TVaR by district)")
    _flag(ax, synthetic)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def climate_bars(table: pd.DataFrame, path, synthetic):
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.6))
    labels = [f"+{t:g} C" if t else "Baseline" for t in table.warming_degC]
    cols = [NAVY, ORANGE, RED][:len(table)]
    axes[0].bar(labels, _meur(table.AAL_gross_EUR), color=cols)
    axes[0].set(title="AAL (EUR m)")
    axes[1].bar(labels, _meur(table.VaR_1in200_EUR), color=cols)
    axes[1].set(title="1-in-200 loss (EUR m)")
    for ax, col in zip(axes, ["AAL_gross_EUR", "VaR_1in200_EUR"]):
        base = table[col].iloc[0]
        for i, v in enumerate(table[col]):
            ax.text(i, _meur(v), f"{_meur(v):.1f}" + (f"\n(+{(v / base - 1) * 100:.0f}%)" if i else ""),
                    ha="center", va="bottom", fontsize=8)
        ax.margins(y=0.25)
    fig.suptitle("Climate stress test - rainfall intensity +7%/degC (Clausius-Clapeyron)", fontweight="bold")
    _flag(axes[1], synthetic)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
