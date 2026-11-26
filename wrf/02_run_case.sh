#!/bin/bash
# Run WPS + WRF for one case from events.csv.
#   bash 02_run_case.sh ist2009            # 3 domains (9, 3, 1 km)
#   MAX_DOM=4 NP=32 bash 02_run_case.sh ist2009   # add 333 m over Ayamama
# Uses your own WPS/WRF builds; set paths if they differ:
#   WPS_DIR (default ~/WPS-4.6.0.11), WRF_DIR (default ~/WRF-4.6.0-ARW), GEOG (default /home/havakalite/WPS_GEOG)
# Runs in the background with nohup; progress: tail -f cases/<case>/run.log
set -euo pipefail
CASE=$1
HERE=$(cd "$(dirname "$0")" && pwd)
MAX_DOM=${MAX_DOM:-3}; NP=${NP:-24}
WPS_DIR=${WPS_DIR:-$HOME/WPS-4.6.0.11}
WRF_DIR=${WRF_DIR:-$HOME/WRF-4.6.0-ARW}
GEOG=${GEOG:-/home/havakalite/WPS_GEOG}
for f in "$WPS_DIR/geogrid.exe" "$WPS_DIR/ungrib.exe" "$WPS_DIR/metgrid.exe" "$WRF_DIR/run/real.exe" "$WRF_DIR/run/wrf.exe"; do
  [ -x "$f" ] || { echo "missing: $f  (set WPS_DIR / WRF_DIR)"; exit 1; }; done
[ -d "$GEOG" ] || { echo "missing static data: $GEOG  (set GEOG=...)"; exit 1; }
LINE=$(grep "^$CASE," "$HERE/events.csv") || { echo "unknown case $CASE"; exit 1; }
START=$(echo "$LINE" | cut -d, -f2); END=$(echo "$LINE" | cut -d, -f3)
D=$HERE/cases/$CASE; mkdir -p "$D/wps" "$D/wrf"
ERA=$HERE/era5/$CASE; ls "$ERA"/*.grib >/dev/null 2>&1 || { echo "no ERA5 GRIB in $ERA: run python 01_download_era5_for_wrf.py $CASE"; exit 1; }

run() {
set -euxo pipefail
# ---------- WPS ----------
cd "$D/wps"
if ls met_em.d0${MAX_DOM}.* >/dev/null 2>&1 && grep -q "Successful completion" metgrid.log 2>/dev/null; then
  echo "WPS already done for $CASE, skipping"; else
sed -e "s|@MAX_DOM@|$MAX_DOM|" -e "s|@START@|$START|g" -e "s|@END@|$END|g" -e "s|@GEOG@|$GEOG|" \
    "$HERE/namelist.wps.template" > namelist.wps
ln -sf "$WPS_DIR"/geogrid.exe "$WPS_DIR"/ungrib.exe "$WPS_DIR"/metgrid.exe .
ln -sfn "$WPS_DIR/geogrid" geogrid; ln -sfn "$WPS_DIR/metgrid" metgrid
rm -f Vtable; cp "$HERE/Vtable.ECMWF.ERA5" Vtable   # own copy: the shared WPS Vtable.ECMWF on this server holds GFS codes
./geogrid.exe > geogrid.out 2>&1; grep -q "Successful completion" geogrid.log
"$WPS_DIR/link_grib.csh" "$ERA"/*.grib
./ungrib.exe > ungrib.out 2>&1; grep -q "Successful completion" ungrib.log
./metgrid.exe > metgrid.out 2>&1; grep -q "Successful completion" metgrid.log
fi
# ---------- WRF ----------
cd "$D/wrf"
# link only the model's tables and executables, never other users' inputs or outputs
find . -maxdepth 1 -type l -delete
for f in "$WRF_DIR"/run/*; do
  case "$(basename "$f")" in wrfout*|wrfinput*|wrfbdy*|wrfrst*|wrflow*|namelist*|rsl.*|met_em*|*.log|*.nc|*.out|nohup*) ;; *) ln -sf "$f" . ;; esac
done
rm -f namelist.input; ln -sf "$D"/wps/met_em.d0* .
cp "$HERE/rain_fields.txt" .
SY=${START:0:4}; SM=${START:5:2}; SD=${START:8:2}; SH=${START:11:2}
EY=${END:0:4};   EM=${END:5:2};   ED=${END:8:2};   EH=${END:11:2}
H=$(( ( $(date -ud "${END:0:10} ${END:11:8}" +%s) - $(date -ud "${START:0:10} ${START:11:8}" +%s) ) / 3600 ))
sed -e "s|@MAX_DOM@|$MAX_DOM|" -e "s|@RUN_HOURS@|$H|" \
    -e "s|@SY@|$SY|g" -e "s|@SM@|$SM|g" -e "s|@SD@|$SD|g" -e "s|@SH@|$SH|g" \
    -e "s|@EY@|$EY|g" -e "s|@EM@|$EM|g" -e "s|@ED@|$ED|g" -e "s|@EH@|$EH|g" \
    "$HERE/namelist.input.template" > namelist.input
mpirun -np "$NP" ./real.exe; grep -q "SUCCESS COMPLETE REAL" rsl.error.0000
mpirun -np "$NP" ./wrf.exe;  grep -q "SUCCESS COMPLETE WRF"  rsl.error.0000
du -sh "$D/wrf"/wrfout_* "$D/wrf"/rain10min_* 2>/dev/null | tail -3 || true
echo "DONE $CASE $(date)"
}
export -f run; export CASE HERE D ERA START END MAX_DOM NP WPS_DIR WRF_DIR GEOG
if [ "${FOREGROUND:-0}" = "1" ]; then bash -c run > "$D/run.log" 2>&1; echo "finished $CASE: $(tail -n 1 "$D/run.log")"; exit 0; fi
nohup bash -c run > "$D/run.log" 2>&1 &
echo "started $CASE in background (pid $!). Follow: tail -f $D/run.log"
