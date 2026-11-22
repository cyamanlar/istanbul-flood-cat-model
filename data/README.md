# Data sources and licences

| Path | Content | Source | Licence / terms |
|---|---|---|---|
| `hazard/era5_raw/tp_levels_YYYY.nc` | ERA5 hourly total precipitation, Istanbul box (41.6N, 27.9E, 40.7N, 29.95E), 1950–2025 | Copernicus Climate Data Store, *ERA5 hourly data on single levels* (Hersbach et al., 2020) | Copernicus licence: free use with attribution ("Contains modified Copernicus Climate Change Service information") |
| `hazard/era5_annual_max.csv` | Annual maximum daily rainfall per 0.25° cell (processed from the files above) | Derived, `scripts/process_era5.py` | As above |
| `hazard/stations_2009_sep.csv` | Daily station totals, 7–9 September 2009 (18 stations used) | *HIRLAM Newsletter* 56 (2010), Table 2 (full reference in `docs/paper.md`) | Published values, cited |
| `hazard/station_records_mgm.csv` | All-time daily rainfall records, 5 stations | Turkish State Meteorological Service (MGM), official climate statistics for Istanbul | Public statistics, cited |
| `raw/ayamama_buildings.geojson` | 79,578 building footprints, western Istanbul (attributes reduced to id, type, storeys, height) | OpenStreetMap | © OpenStreetMap contributors, ODbL 1.0 |
| `raw/ayamama_waterways.geojson`, `raw/ayamama_river_systems.geojson` | Streams, drains and the Ayamama, Haramidere and Alibey river systems | OpenStreetMap | © OpenStreetMap contributors, ODbL 1.0 |
| `raw/rasters_COP30.tar.gz` | Copernicus DEM GLO-30, 27.9–29.3E, 40.8–41.5N | ESA, Copernicus DEM (doi:10.5270/ESA-c5d3d65) | Copernicus DEM licence: free use with attribution |
| `exposure/istanbul_portfolio_OED_*.csv` | Illustrative property portfolio, OED format | Synthetic, `src/exposure.py` | MIT |
| `exposure/west_istanbul_buildings.csv.gz` | Processed building table (value, HAND index, 2009 depth and loss) | Derived from OSM and Copernicus DEM | ODbL (derived database) |

No personal data are included. OpenStreetMap address and name tags were removed from the building file.

### Added in v0.3 (22 November 2026)

| Path | Content | Source | Licence / terms |
|---|---|---|---|
| `ibb/ibb_dam_rainfall_daily.xlsx` | Daily rainfall at 10 Istanbul water-supply dams, 2011–2024 | Istanbul Metropolitan Municipality open data portal, data.ibb.gov.tr (dataset "İstanbul Barajlarına Düşen Yağış ve Günlük Tüketim Verileri") | IBB Open Data Licence |
| `ibb/akom_awos_stations.csv` | Names and coordinates of AKOM automatic weather stations | data.ibb.gov.tr (dataset "Meteoroloji Gözlem İstasyon Konumları") | IBB Open Data Licence |
| `raw/ayamama_buildings_ms_gapfill.geojson` | 71,106 building footprints in the Ayamama box that do not overlap OSM (68,159 used after the size filter) | Microsoft Global ML Building Footprints, release 2026-02-03 | ODbL 1.0 |
| `events/era5_tp_2026-10-10_20.nc` | ERA5 hourly precipitation, 10–20 October 2026, same box as `era5_raw` (kept apart: partial year) | Copernicus Climate Data Store, downloaded 22 Nov 2026 | Copernicus licence |
| `events/istanbul_2026-10_stations.csv` | Rainfall at 10 stations, 13–15 October 2026 | İBB statement of 15 Oct 2026 with AKOM Meteoroloji station totals (press copies of the full statement linked in the file); coordinates from the MGM station list, the IBB AWOS list or district centres | Cited facts |
| `external/` (not in the repository) | MGM hourly gauges and Istanbul radar, September 2009 | MGM, supplied for research | Not redistributed; only derived tables are published |
