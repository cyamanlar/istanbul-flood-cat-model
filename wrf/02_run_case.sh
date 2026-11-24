#!/bin/bash
# Run WPS + WRF for one case from events.csv.
#   bash 02_run_case.sh ist2009            # 3 domains (9, 3, 1 km)
#   MAX_DOM=4 NP=32 bash 02_run_case.sh ist2009   # add 333 m over Ayamama
# Uses your own WPS/WRF builds; set paths if they differ:
#   WPS_DIR (default ~/WPS-4.6.0.11), WRF_DIR (default: first ~/WRF*/ with run/real.exe), GEOG (default $WPS_DIR/../WPS_GEOG)
# Runs in the background with nohup; progress: tail -f cases/<case>/run.log
set -euo pipefail
CASE=$1
HERE=$(cd "$(dirname "$0")" && pwd)
MAX_DOM=${MAX_DOM:-3}; NP=${NP:-16}
WPS_DIR=${WPS_DIR:-$HOME/WPS-4.6.0.11}
WRF_DIR=${WRF_DIR:-$(dirname "$(ls -d $HOME/WRF*/run/real.exe 2>/dev/null | head -1)" 2>/dev/null)}
WRF_DIR=${WRF_DIR%/run}
GEOG=${GEOG:-$(cd "$WPS_DIR/.." && pwd)/WPS_GEOG}
for f in "$WPS_DIR/geogrid.exe" "$WPS_DIR/ungrib.exe" "$WPS_DIR/metgrid.exe" "$WRF_DIR/run/real.exe" "$WRF_DIR/run/wrf.exe"; do
  [ -x "$f" ] || { echo "missing: $f  (set WPS_DIR / WRF_DIR)"; exit 1; }; done
[ -d "$GEOG" ] || { echo "missing static data: $GEOG  (set GEOG=...)"; exit 1; }
LINE=$(grep "^$CASE," "$HERE/events.csv") || { echo "unknown case $CASE"; exit 1; }
START=$(echo "$LINE" | cut -d, -f2); END=$(echo "$LINE" | cut -d, -f3)
D=$HERE/cases/$CASE; mkdir -p "$D/wps" "$D/wrf"
ERA=$HERE/era5/$CASE; ls "$ERA"/*.grib >/dev/null 2>&1 || { echo "no ERA5 GRIB in $ERA: run python 01_download_era5_for_wrf.py $CASE"; exit 1; }

run() {
set -x
# ---------- WPS ----------
cd "$D/wps"
sed -e "s|@MAX_DOM@|$MAX_DOM|" -e "s|@START@|$START|g" -e "s|@END@|$END|g" -e "s|@GEOG@|$GEOG|" \
    "$HERE/namelist.wps.template" > namelist.wps
ln -sf "$WPS_DIR"/geogrid.exe "$WPS_DIR"/ungrib.exe "$WPS_DIR"/metgrid.exe .
ln -sfn "$WPS_DIR/geogrid" geogrid; ln -sfn "$WPS_DIR/metgrid" metgrid
ln -sf "$WPS_DIR/ungrib/Variable_Tables/Vtable.ECMWF" Vtable
./geogrid.exe > geogrid.out 2>&1; grep -q "Successful completion" geogrid.log
"$WPS_DIR/link_grib.csh" "$ERA"/*.grib
./ungrib.exe > ungrib.out 2>&1; grep -q "Successful completion" ungrib.log
./metgrid.exe > metgrid.out 2>&1; grep -q "Successful completion" metgrid.log
# ---------- WRF ----------
cd "$D/wrf"
for f in "$WRF_DIR"/run/*; do ln -sf "$f" .; done
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
echo "DONE $CASE $(date)"
}
export -f run; export HERE D ERA START END MAX_DOM NP WPS_DIR WRF_DIR GEOG
nohup bash -c run > "$D/run.log" 2>&1 &
echo "started $CASE in background (pid $!). Follow: tail -f $D/run.log"
