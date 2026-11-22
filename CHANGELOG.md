# Changelog

Dates are when the change was made. Each entry says what changed, why and with which evidence.

## v0.3 – 22 November 2026 – review revision

Response to an expert review of v0.2. All data used are official or open sources; MGM data supplied for research are used for analysis only and are not redistributed.

### Hazard
* **ERA5 correction: single factor 1.8 → zonal factors 1.69 (European side) and 1.41 (Asian side), Bosphorus column 1.55.** Estimated from IBB dam gauges vs ERA5 over the same years 2011–2023 (7 gauges, 6 cells, 91 station-years; `scripts/bias_matched_period.py`, `outputs/tables/bias_matched_period.csv`). The factor now has an uncertainty range (P5–P95 = ×0.89–×1.13) that enters the results. *Why:* the v0.2 factor rested on all-time records at 5 stations in 3 cells and on one event-day comparison that used the wrong ERA5 day.
* **ERA5 on single events re-checked with event-day values.** `scripts/era5_event_check.py` compares ERA5 on the event days (UTC and 06–06 UTC) with the 2009 station totals and lists stations per ERA5 cell. `scripts/era5_vs_mgm_2009.py` repeats the check with MGM hourly gauges over identical 48-hour windows (ratios 1.5–6.3 on the European side, below 1 on the Asian side).
* **Correlation length 60 km → 40 km**, tested at 20–60 km. Evidence: MGM radar, 2009 storm, e-folding about 22 km (`scripts/radar_2009_footprint.py`); dam gauges, daily rainfall about 51 km and annual maxima about 34 km.

### Exposure and validation
* **OSM gap fill in the Ayamama basin** with 68,159 Microsoft Global ML Building Footprints (ODbL) that do not overlap OSM (`scripts/gapfill_buildings_ms.py`). OSM held about one third of the buildings in the box.
* **Point-by-point 2009 validation** at the five survey locations (Nominatim-geocoded; `outputs/building_level/validation_2009_pointwise.csv`): MAE 0.40 m, bias −0.38 m for the median depth at four locations; the Çobançeşme culvert backwater is reported as not representable. Channel stage and building depth are reported separately.
* **2009 is now labelled the calibration event.** Independent validation with the 13–15 October 2026 event is prepared (`data/events/istanbul_2026-10_stations.csv`) and waits for ERA5 October 2026 data from CDS.

### Uncertainty
* **40-run epistemic ensemble** (`scripts/epistemic_uncertainty.py`): central values and 90 % ranges, reported separately from the Monte Carlo error of the 50,000-year run.
* New sensitivity cases: ERA5 correction P5/P95, correlation 20/60 km, v0.2 settings (reproduce the v0.2 results exactly: AAL 2.08, 1-in-200 32.2 EUR m).

### Extreme-value diagnostics
* `scripts/extreme_value_diagnostics.py`: bootstrap 90 % CI of the GEV 100- and 200-year levels (about ±15 %), Mann-Kendall stationarity test (no significant trend in ERA5 annual maxima), POT/GPD cross-check (100-year levels within −15 % to +12 % of the GEV).
* Loss definitions stated explicitly: insured loss of the illustrative portfolio after the deductible, before reinsurance; not economic loss.

### Results (illustrative EUR 5 bn portfolio)
| | v0.2 | v0.3 reference run | v0.3 central (90 % range) |
|---|---:|---:|---:|
| AAL (EUR m) | 2.08 | 1.19 | 1.6 (0.9–3.9) |
| 1-in-200 (EUR m) | 32.2 | 21.9 | 34 (24–49) |
| TVaR 99.5 % (EUR m) | 63.7 | 39.8 | 53 (40–77) |

Of the change in the reference 1-in-200 loss (32.2 → 21.9), the ERA5 factors account for 32.2 → 24.0 and the shorter correlation length for the rest. The central value is higher than the reference run because the reference portfolio is one of the least flood-exposed realisations.

### Communication
* Simulator: Turkish and English, P5–P95 band, new ERA5 lever (multiplier around the gauge-based factors), research-prototype notice, removed the sentence "ERA5 sees about half of station extremes".
* Climate results are worded as "under this model's 7 %/°C assumption", not as projections.
* README: one licence table; results table with ranges.

## v0.2 – first public release, 22 November 2026
* Portfolio model with ERA5 hazard (single bias factor 1.8), illustrative portfolio, JRC curves, EP curve, AAL, 1-in-200, Oasis and CLIMADA exports.
* Building-level module with the 2009 replay, regional GEV shape, 400 mm cap, separate hazard and exposure random streams, uncertainty tornado, paper, interactive simulator.
