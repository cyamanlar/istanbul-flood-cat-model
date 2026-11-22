"""
Export the model as Oasis LMF model files (CSV flavour of the ktools formats).

oasis/
  keys.csv                         location -> areaperil_id / vulnerability_id lookup result
  model_data/events.csv            event_id
  model_data/footprint.csv         event_id, areaperil_id, intensity_bin_id, probability
  model_data/intensity_bin_dict.csv
  model_data/damage_bin_dict.csv
  model_data/vulnerability.csv     vulnerability_id, intensity_bin_id, damage_bin_id, probability

Convert to binaries with ktools, e.g.
  footprinttobin -i 81 < footprint.csv
  vulnerabilitytobin -d 22 < vulnerability.csv > vulnerability.bin
  damagebintobin < damage_bin_dict.csv > damage_bin_dict.bin
  evetobin < events.csv > events.bin
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .vulnerability import mean_damage_ratio, rain_to_depth, sample_damage_ratio

INT_STEP_MM = 5
INT_MAX_MM = 400
OCC_ID = {"residential": 1, "commercial": 2, "industrial": 3}


def vulnerability_id(occupancy, prone):
    return np.array([OCC_ID[o] * 10 + (1 if p else 0) for o, p in zip(occupancy, prone)])


def export_oasis(gev, events, loc, cfg, out_dir="oasis", mc=4000):
    md = os.path.join(out_dir, "model_data")
    os.makedirs(md, exist_ok=True)
    rng = np.random.default_rng(cfg["random_seed"] + 7)

    # intensity bins: rainfall in mm
    edges = np.arange(0, INT_MAX_MM + INT_STEP_MM, INT_STEP_MM)
    ib = pd.DataFrame({"bin_index": np.arange(1, len(edges) + 1),
                       "bin_from": edges, "bin_to": np.r_[edges[1:], 1000]})
    ib["interpolation"] = (ib.bin_from + ib.bin_to.clip(upper=INT_MAX_MM + INT_STEP_MM)) / 2
    ib.to_csv(os.path.join(md, "intensity_bin_dict.csv"), index=False)

    # damage bins: exact zero, 20 x 5% bins, exact one
    d_from = np.r_[0, np.arange(0, 1, 0.05), 1]
    d_to = np.r_[0, np.arange(0.05, 1.0001, 0.05), 1]
    db = pd.DataFrame({"bin_index": np.arange(1, len(d_from) + 1), "bin_from": d_from.round(2),
                       "bin_to": d_to.round(2), "interpolation": ((d_from + d_to) / 2).round(3)})
    db.to_csv(os.path.join(md, "damage_bin_dict.csv"), index=False)

    # vulnerability: Monte Carlo discretisation of the Beta secondary uncertainty
    rows = []
    cv = cfg["vulnerability"]["secondary_uncertainty_cv"]
    for occ in OCC_ID:
        for prone in (False, True):
            vid = OCC_ID[occ] * 10 + int(prone)
            p_mid = ib["interpolation"].to_numpy()[:, None]
            depth = rain_to_depth(p_mid, np.array([prone]), np.array([1.0]), cfg["vulnerability"])
            mdr = mean_damage_ratio(depth, np.array([occ]))[:, 0]
            for i, m in enumerate(mdr):
                if m <= 1e-6:
                    rows.append((vid, i + 1, 1, 1.0)); continue
                s = sample_damage_ratio(np.full(mc, m), cv, rng)
                idx = np.where(s <= 0, 1, np.where(s >= 1, len(db), 2 + np.minimum((s / 0.05).astype(int), 19)))
                cnt = np.bincount(idx, minlength=len(db) + 1)
                for b in np.nonzero(cnt)[0]:
                    rows.append((vid, i + 1, int(b), cnt[b] / mc))
    pd.DataFrame(rows, columns=["vulnerability_id", "intensity_bin_id", "damage_bin_id", "probability"]) \
        .round(6).to_csv(os.path.join(md, "vulnerability.csv"), index=False)

    # events + footprint (deterministic intensity per cell, probability 1)
    n_ev = events.shape[0]
    pd.DataFrame({"event_id": np.arange(1, n_ev + 1)}).to_csv(os.path.join(md, "events.csv"), index=False)
    bins = np.minimum(np.searchsorted(edges, events, side="right"), len(edges))
    ev_id = np.repeat(np.arange(1, n_ev + 1), events.shape[1])
    ap_id = np.tile(gev["cell_id"].to_numpy(), n_ev)
    fp = pd.DataFrame({"event_id": ev_id, "areaperil_id": ap_id,
                       "intensity_bin_id": bins.ravel(), "probability": 1.0})
    fp[fp.intensity_bin_id > 1].to_csv(os.path.join(md, "footprint.csv"), index=False)

    # keys: one row per location x coverage (1 building, 3 contents, 4 BI)
    vids = vulnerability_id(loc["occupancy"], loc["flood_prone"])
    keys = []
    for cov in (1, 3, 4):
        keys.append(pd.DataFrame({"LocID": np.arange(1, len(loc) + 1), "PerilID": "OO1",
                                  "CoverageTypeID": cov, "AreaPerilID": loc["cell_id"].to_numpy(),
                                  "VulnerabilityID": vids}))
    pd.concat(keys).sort_values(["LocID", "CoverageTypeID"]).to_csv(os.path.join(out_dir, "keys.csv"), index=False)
    print(f"[oasis]    model files written to {out_dir}/ ({len(fp):,} footprint rows)")
