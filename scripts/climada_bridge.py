"""
Cross-check the in-house engine with CLIMADA (ETH Zurich).

Builds CLIMADA Hazard / Exposures / ImpactFuncSet objects from this model's
stochastic event set and portfolio, runs ImpactCalc and compares AAL and the
1-in-200 loss with run_model.py (ground-up, mean damage, no deductible).

  conda create -n climada_env -c conda-forge climada   # see CLIMADA docs
  conda activate climada_env
  python scripts/climada_bridge.py

Intensity = daily rainfall (mm). One impact function per
(occupancy x flood zone) class, built by composing the rainfall->depth
transfer with the JRC depth-damage curves, so both engines share the same
physics and any difference comes from the implementation only.
"""
import json
import os
import sys

import numpy as np
from scipy import sparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from climada.engine import ImpactCalc
from climada.entity import Exposures, ImpactFunc, ImpactFuncSet
from climada.hazard import Centroids, Hazard

from src import exposure, hazard
from src.oasis_export import OCC_ID, vulnerability_id
from src.vulnerability import mean_damage_ratio, rain_to_depth

HAZ = "FL"


def main():
    cfg = json.load(open("config.json"))
    rng = np.random.default_rng(cfg["random_seed"])
    cells = hazard.grid_cells()
    amax, _ = hazard.load_annual_max(cfg, cells, rng)
    gev = hazard.fit_cells(amax, regional_shape=cfg["hazard"].get("regional_shape", True))
    ev = hazard.simulate_event_set(gev, cfg["n_sim_years"], cfg["hazard"]["corr_length_km"], rng,
                                    cfg["hazard"].get("max_daily_rain_mm", 400.0))
    loc = exposure.build_portfolio(cfg, cells, np.random.default_rng(cfg["random_seed"] + 100))

    n = ev.shape[0]
    haz = Hazard(haz_type=HAZ, units="mm",
                 centroids=Centroids(lat=gev.lat.to_numpy(), lon=gev.lon.to_numpy()),
                 event_id=np.arange(1, n + 1), event_name=[str(i) for i in range(1, n + 1)],
                 date=np.ones(n, dtype=int), orig=np.ones(n, dtype=bool),
                 frequency=np.full(n, 1.0 / n),
                 intensity=sparse.csr_matrix(ev), fraction=sparse.csr_matrix(np.ones_like(ev)))
    haz.check()

    p = np.arange(0, 401, 5.0)
    funcs = []
    for occ in OCC_ID:
        for prone in (False, True):
            d = rain_to_depth(p[:, None], np.array([prone]), np.array([1.0]), cfg["vulnerability"])
            mdd = mean_damage_ratio(d, np.array([occ]))[:, 0]
            funcs.append(ImpactFunc(haz_type=HAZ, id=OCC_ID[occ] * 10 + int(prone), intensity=p,
                                    mdd=mdd, paa=np.ones_like(p), intensity_unit="mm",
                                    name=f"{occ}_{'prone' if prone else 'std'}"))
    impfset = ImpactFuncSet(funcs)

    import geopandas as gpd
    gdf = gpd.GeoDataFrame({"value": loc.TIV.to_numpy(),
                            f"impf_{HAZ}": vulnerability_id(loc.occupancy, loc.flood_prone),
                            f"centr_{HAZ}": loc.cell_id.to_numpy() - 1},
                           geometry=gpd.points_from_xy(loc.Longitude, loc.Latitude), crs="EPSG:4326")
    exp = Exposures(gdf, value_unit="EUR")
    exp.check()
    # NB: CLIMADA ignores the per-location depth amplification used in run_model.py
    imp = ImpactCalc(exp, impfset, haz).impact(assign_centroids=False)
    fc = imp.calc_freq_curve(return_per=np.array([10, 50, 100, 200, 500]))
    print(f"CLIMADA AAL (ground-up): EUR {imp.aai_agg / 1e6:.2f} m")
    for rp, v in zip(fc.return_per, fc.impact):
        print(f"  1-in-{rp:.0f}: EUR {v / 1e6:.1f} m")


if __name__ == "__main__":
    main()
