"""
EXPOSURE MODULE - illustrative property portfolio for Istanbul.

A hypothetical insurer's property book (default TIV EUR 5 bn) is distributed
over Istanbul's 39 districts in proportion to population x a value multiplier
(CBD districts carry more commercial value). Each district is disaggregated
into individual risk locations with:

  * occupancy   : residential / commercial / industrial
  * flood_prone : location sits in a stream bed / low-lying zone
                  (e.g. Ayamama, Kagithane, Kurbagalidere, Riva valleys)
  * local_amp   : local depth amplification (topography, drainage)

The portfolio is exported in Oasis Open Exposure Data (OED) format.

ALL VALUES ARE ILLUSTRATIVE. With a real book, replace this module by
reading the insurer's OED location file directly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .hazard import GRID_LATS, GRID_LONS

# district, lat, lon, population (k, approx.), flood-prone class, commercial share, industrial share
DISTRICTS = [
    ("Adalar", 40.87, 29.09, 16, "low", 0.20, 0.00),
    ("Arnavutkoy", 41.18, 28.74, 330, "med", 0.15, 0.25),
    ("Atasehir", 40.98, 29.12, 415, "low", 0.45, 0.05),
    ("Avcilar", 40.98, 28.72, 450, "med", 0.20, 0.05),
    ("Bagcilar", 41.04, 28.83, 735, "high", 0.20, 0.20),
    ("Bahcelievler", 41.00, 28.86, 580, "med", 0.25, 0.05),
    ("Bakirkoy", 40.98, 28.87, 220, "low", 0.45, 0.05),
    ("Basaksehir", 41.09, 28.80, 500, "high", 0.20, 0.35),
    ("Bayrampasa", 41.04, 28.91, 270, "low", 0.20, 0.15),
    ("Besiktas", 41.04, 29.01, 170, "low", 0.50, 0.00),
    ("Beykoz", 41.13, 29.10, 245, "med", 0.15, 0.05),
    ("Beylikduzu", 40.98, 28.64, 400, "low", 0.20, 0.20),
    ("Beyoglu", 41.03, 28.98, 225, "low", 0.50, 0.00),
    ("Buyukcekmece", 41.02, 28.59, 270, "med", 0.20, 0.10),
    ("Catalca", 41.14, 28.46, 75, "med", 0.10, 0.15),
    ("Cekmekoy", 41.03, 29.18, 290, "low", 0.15, 0.05),
    ("Esenler", 41.04, 28.88, 445, "med", 0.20, 0.10),
    ("Esenyurt", 41.03, 28.67, 980, "med", 0.20, 0.20),
    ("Eyupsultan", 41.05, 28.93, 420, "med", 0.20, 0.10),
    ("Fatih", 41.01, 28.95, 370, "low", 0.50, 0.00),
    ("Gaziosmanpasa", 41.06, 28.91, 480, "low", 0.20, 0.05),
    ("Gungoren", 41.02, 28.87, 280, "med", 0.25, 0.10),
    ("Kadikoy", 40.99, 29.03, 465, "med", 0.45, 0.00),
    ("Kagithane", 41.08, 28.97, 455, "high", 0.30, 0.10),
    ("Kartal", 40.89, 29.19, 475, "med", 0.25, 0.15),
    ("Kucukcekmece", 41.00, 28.78, 790, "high", 0.20, 0.15),
    ("Maltepe", 40.94, 29.13, 515, "low", 0.25, 0.05),
    ("Pendik", 40.88, 29.25, 740, "med", 0.20, 0.20),
    ("Sancaktepe", 41.00, 29.23, 480, "low", 0.15, 0.10),
    ("Sariyer", 41.17, 29.05, 340, "med", 0.30, 0.00),
    ("Silivri", 41.07, 28.25, 210, "med", 0.15, 0.10),
    ("Sultanbeyli", 40.96, 29.27, 360, "low", 0.15, 0.05),
    ("Sultangazi", 41.11, 28.87, 540, "low", 0.15, 0.05),
    ("Sile", 41.18, 29.61, 45, "med", 0.15, 0.00),
    ("Sisli", 41.06, 28.99, 265, "low", 0.50, 0.00),
    ("Tuzla", 40.82, 29.30, 285, "med", 0.15, 0.40),
    ("Umraniye", 41.02, 29.12, 725, "low", 0.25, 0.15),
    ("Uskudar", 41.02, 29.02, 525, "low", 0.30, 0.00),
    ("Zeytinburnu", 41.00, 28.90, 285, "med", 0.30, 0.10),
]

PRONE_SHARE = {"high": 0.12, "med": 0.06, "low": 0.025}
OED_OCC = {"residential": 1050, "commercial": 1100, "industrial": 1150}  # OED OccupancyCode
OED_CONS = {"residential": 5000, "commercial": 5000, "industrial": 5000}  # 5000 = unknown/default; refine with real data


def districts_df() -> pd.DataFrame:
    df = pd.DataFrame(DISTRICTS, columns=["district", "lat", "lon", "pop_k", "prone_class",
                                          "com_share", "ind_share"])
    df["value_mult"] = 1.0 + 1.5 * df["com_share"]
    return df


def nearest_cell(lat, lon, cells: pd.DataFrame) -> np.ndarray:
    ilat = np.abs(np.asarray(lat)[:, None] - GRID_LATS[None, :]).argmin(1)
    ilon = np.abs(np.asarray(lon)[:, None] - GRID_LONS[None, :]).argmin(1)
    key = pd.DataFrame({"lat": GRID_LATS[ilat].round(2), "lon": GRID_LONS[ilon].round(2)})
    return key.merge(cells, on=["lat", "lon"], how="left")["cell_id"].to_numpy()


def build_portfolio(cfg: dict, cells: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    ec = cfg["exposure"]
    d = districts_df()
    w = d["pop_k"] * d["value_mult"]
    d["district_tiv"] = ec["total_tiv_eur"] * w / w.sum()
    d["n_loc"] = np.maximum(5, np.round(ec["n_locations"] * w / w.sum())).astype(int)

    recs = []
    for r in d.itertuples():
        n = r.n_loc
        occ = rng.choice(["residential", "commercial", "industrial"], size=n,
                         p=[1 - r.com_share - r.ind_share, r.com_share, r.ind_share])
        size = rng.lognormal(0, 0.8, n) * np.where(occ == "residential", 1.0,
                                                   np.where(occ == "commercial", 2.0, 3.0))
        tiv = r.district_tiv * size / size.sum()
        prone = rng.uniform(size=n) < PRONE_SHARE[r.prone_class]
        amp = np.where(prone, rng.lognormal(0, 0.35, n), 1.0)
        for i in range(n):
            recs.append({
                "district": r.district,
                "Latitude": round(r.lat + rng.normal(0, 0.01), 5),
                "Longitude": round(r.lon + rng.normal(0, 0.01), 5),
                "occupancy": occ[i], "flood_prone": bool(prone[i]), "local_amp": float(amp[i]),
                "TIV": float(tiv[i]),
            })
    loc = pd.DataFrame(recs)
    loc.insert(0, "LocNumber", [f"IST{i:05d}" for i in range(1, len(loc) + 1)])
    loc["cell_id"] = nearest_cell(loc["Latitude"], loc["Longitude"], cells)
    # Building / contents / BI split - typical property split
    split = {"residential": (0.75, 0.25, 0.00), "commercial": (0.55, 0.30, 0.15),
             "industrial": (0.50, 0.35, 0.15)}
    for j, col in enumerate(["BuildingTIV", "ContentsTIV", "BITIV"]):
        loc[col] = loc.apply(lambda x: x.TIV * split[x.occupancy][j], axis=1).round(0)
    return loc


def to_oed(loc: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (location, account) tables in Oasis OED v3 format."""
    fin = cfg["financial"]
    oed = pd.DataFrame({
        "PortNumber": "IST_PROP_2026",
        "AccNumber": "ACC_" + loc["district"].str.upper(),
        "LocNumber": loc["LocNumber"],
        "CountryCode": "TR",
        "Latitude": loc["Latitude"], "Longitude": loc["Longitude"],
        "AreaName1": loc["district"],
        "OccupancyCode": loc["occupancy"].map(OED_OCC),
        "ConstructionCode": loc["occupancy"].map(OED_CONS),
        "LocPerilsCovered": "OO1",            # OED: all flood perils
        "BuildingTIV": loc["BuildingTIV"], "ContentsTIV": loc["ContentsTIV"],
        "BITIV": loc["BITIV"], "OtherTIV": 0,
        "LocCurrency": "EUR",
        "LocDedType6All": 2,                  # 2 = % of TIV
        "LocDed6All": fin["deductible_pct_tiv"],
        "LocLimitType6All": 0,
        "LocLimit6All": (loc["TIV"] * fin["limit_pct_tiv"]).round(0),
        "FloodZone": np.where(loc["flood_prone"], "PRONE", "STANDARD"),
    })
    acc = (oed[["PortNumber", "AccNumber"]].drop_duplicates()
           .assign(AccCurrency="EUR", PolNumber=lambda x: x.AccNumber.str.replace("ACC", "POL"),
                   PolPerilsCovered="OO1", PolPeril="OO1"))
    return oed, acc
