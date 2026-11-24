"""
Download ERA5 initial and boundary data for one WRF case (GRIB, 3-hourly).

    python 01_download_era5_for_wrf.py ist2009        # case name from events.csv

Needs the cdsapi package and the user's own ~/.cdsapirc (never put the key in
this repository). Output: era5/<case>/era5_pl_*.grib, era5_sl_*.grib
Domain box (N/W/S/E): 47/19/35/39, wider than WRF domain 1.
"""
import csv, os, sys, datetime as dt
import cdsapi

case = sys.argv[1]
ev = {r["case"]: r for r in csv.DictReader(open(os.path.join(os.path.dirname(__file__), "events.csv")))}[case]
t0 = dt.datetime.strptime(ev["start_utc"], "%Y-%m-%d_%H:%M:%S")
t1 = dt.datetime.strptime(ev["end_utc"], "%Y-%m-%d_%H:%M:%S")
days = sorted({(t0 + dt.timedelta(hours=h)).strftime("%Y-%m-%d") for h in range(0, int((t1 - t0).total_seconds() // 3600) + 1, 3)})
out = os.path.join("era5", case); os.makedirs(out, exist_ok=True)
area = [47, 19, 35, 39]
hours = [f"{h:02d}:00" for h in range(0, 24, 3)]
c = cdsapi.Client()
levels = ["1", "2", "3", "5", "7", "10", "20", "30", "50", "70", "100", "125", "150", "175", "200", "225", "250",
          "300", "350", "400", "450", "500", "550", "600", "650", "700", "750", "775", "800", "825", "850", "875",
          "900", "925", "950", "975", "1000"]
for d in days:
    y, m, dd = d.split("-")
    pl = os.path.join(out, f"era5_pl_{d}.grib"); sl = os.path.join(out, f"era5_sl_{d}.grib")
    if not os.path.exists(pl):
        c.retrieve("reanalysis-era5-pressure-levels", {
            "product_type": ["reanalysis"], "data_format": "grib", "download_format": "unarchived",
            "variable": ["geopotential", "temperature", "u_component_of_wind", "v_component_of_wind",
                         "relative_humidity", "specific_humidity"],
            "pressure_level": levels, "year": [y], "month": [m], "day": [dd], "time": hours, "area": area}, pl)
    if not os.path.exists(sl):
        c.retrieve("reanalysis-era5-single-levels", {
            "product_type": ["reanalysis"], "data_format": "grib", "download_format": "unarchived",
            "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind", "2m_temperature",
                         "2m_dewpoint_temperature", "surface_pressure", "mean_sea_level_pressure",
                         "skin_temperature", "sea_surface_temperature", "land_sea_mask", "geopotential",
                         "soil_temperature_level_1", "soil_temperature_level_2", "soil_temperature_level_3",
                         "soil_temperature_level_4", "volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
                         "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4", "snow_depth",
                         "sea_ice_cover"],
            "year": [y], "month": [m], "day": [dd], "time": hours, "area": area}, sl)
    print("ok", d)
