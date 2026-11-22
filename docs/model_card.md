# Model Card: Istanbul Pluvial Flood Cat Model (v0.3, 22 November 2026)

## Purpose
This is a transparent, open probabilistic flood model for Istanbul property exposure. It produces the EP curve, AAL, PML, VaR 99.5 % and TVaR, together with a sensitivity and uncertainty analysis. It is a **research prototype and scenario tool**, suitable for portfolio steering, accumulation control and climate scenario analysis (ORSA). Its results are very sensitive to assumptions; it is not fit for pricing individual risks or for an internal-model capital figure, and it is not a substitute for a vendor or hydrodynamic model. Losses refer to an illustrative portfolio, not to Istanbul as a whole.

## Scope
| Item | Value |
|---|---|
| Peril | Pluvial / flash flood driven by extreme daily rainfall (OED peril OO1) |
| Region | Istanbul province, 32 ERA5 cells at 0.25°; building level on the European side |
| Lines | Property: residential, commercial, industrial; building, contents, BI |
| Event set | 50,000 simulated years, one dominant event per year |
| Currency | EUR; illustrative portfolio TIV EUR 5 bn (1,505 locations); 145,978 buildings: 77,819 OSM + 68,159 Microsoft gap-fill footprints in the Ayamama basin (EUR 159.8 bn) |

## Key assumptions (all in `config.json`)
| Assumption | Value | Evidence or test |
|---|---|---|
| Hazard data | ERA5 annual maxima 1950–2025 × zonal factor 1.69 (Europe) / 1.41 (Asia) / 1.55 (Bosphorus column) | IBB dam gauges vs ERA5 2011–2023, 91 station-years; P5–P95 ×0.89–1.13 |
| Extreme value distribution | GEV, L-moments, regional shape k = −0.142 | Cell-by-cell shape changes the 1-in-200 loss by −4 % |
| Rainfall cap | 400 mm/day | 300 / 600 mm changes the 1-in-200 loss by about 2 % or less |
| Spatial correlation | ρ = exp(−d / 40 km) | Radar 2009: 22 km; gauges: 34–51 km. 20 / 60 km: 1-in-200 loss −18 % / +10 % |
| Drainage capacity, flood-prone zone | 70 mm/day, 0.008 m/mm | −20 % / +20 %: 1-in-200 loss +23 % / −21 % |
| Standard zone | 140 mm/day, 0.0015 m/mm | |
| Flood-prone share by district class | 12 / 6 / 2.5 % | Portfolio realisations: 1-in-200 loss EUR 22–41 m |
| Building level: stage | 0.03 m per mm above 40 mm, class factors 1.0–0.15 | Calibrated to 2009 Ayamama depths |
| Building level: HAND | DEM 90 m minimum filter, +3 m per km | |
| Depth–damage | JRC Europe (Huizinga et al., 2017) | Not validated for Turkey |
| Secondary uncertainty | Beta, CV 0.4 | CV 0 / 0.8: < 3 % on the 1-in-200 loss |
| Deductible / limit | 1 % / 100 % of TIV | |
| Climate scaling | +7 % per °C (stress test) | Not a projection; sub-daily extremes may scale faster or slower |

## Validation status
See README (Validation status) and CHANGELOG. Summary: ERA5 factors are estimated from matched-period gauges; spatial correlation is checked against radar and gauges; the 2009 event is the calibration event (point-wise MAE 0.40 m at four sites); an independent hazard check with October 2026 is done (ERA5 1.4–3.3× below the İBB/AKOM station totals; model return periods 20–115 years); depth validation for October 2026 is pending. Damage curves are not validated locally.

## Headline results (illustrative EUR 5 bn portfolio)
Central (P50) and 90 % range from a 40-run epistemic ensemble: AAL EUR 1.6 m (0.9–3.9), 1-in-200 EUR 34 m (24–49), TVaR 99.5 % EUR 53 m (40–77). Monte Carlo error of 50,000 years: ±0.8 m on the 1-in-200 loss.

## Known limitations
* Rainfall–depth proxy; no routing, river or coastal flood, or defences.
* Daily rainfall; one event per year (OEP ≈ AEP).
* ERA5 factors from 7 gauges and 13 years; the building module lacks an areal reduction factor (2009 appears as about 1-in-24 there, against about 1-in-680 in the portfolio model reference run).
* Illustrative exposure; OSM gaps filled only in the Ayamama basin; the DEM is a surface model.

## Intended users
Cat modelling, exposure management, actuarial pricing, capital modelling (Solvency II) and climate-risk (ORSA, TCFD/ISSB) teams.
