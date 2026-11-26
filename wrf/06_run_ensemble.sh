#!/bin/bash
# 2009 physics / stochastic ensemble. Waits until 05_run_queue.sh has finished, then runs the
# members in ensemble/ one after another, re-using the WPS output (met_em) of cases/ist2009r.
#   nohup bash 06_run_ensemble.sh > ensemble.log 2>&1 &
# Self-contained on purpose: it does not touch 02_run_case.sh / 05_run_queue.sh while they run.
HERE=$(cd "$(dirname "$0")" && pwd); cd "$HERE"
WRF_DIR=${WRF_DIR:-$HOME/WRF-4.6.0-ARW}; NP=${NP:-24}; MAX_DOM=3
BASE=$HERE/cases/ist2009r/wps
START=2009-09-08_12:00:00; END=2009-09-10_00:00:00
while pgrep -f "05_run_queue.sh" >/dev/null; do sleep 600; done
echo "queue finished, ensemble starts $(date)"
ls "$BASE"/met_em.d03.* >/dev/null 2>&1 || { echo "missing $BASE/met_em (do not delete ist2009r WPS output)"; exit 1; }
for m in ${MEMBERS:-e2 e3 e4 e5 e6 e7}; do
  C=ist2009r_$m; D=$HERE/cases/$C/wrf; mkdir -p "$D"; cd "$D"
  echo "== $C start $(date)"; df -h ~ | tail -1
  avail=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9); [ "$avail" -lt 4 ] && { echo "disk below 4 GB, stopping"; exit 1; }
  find . -maxdepth 1 -type l -delete
  for f in "$WRF_DIR"/run/*; do
    case "$(basename "$f")" in wrfout*|wrfinput*|wrfbdy*|wrfrst*|wrflow*|namelist*|rsl.*|met_em*|*.log|*.nc|*.out|nohup*) ;; *) ln -sf "$f" . ;; esac
  done
  ln -sf "$BASE"/met_em.d0* .; cp "$HERE/rain_fields.txt" .
  sed -e "s|@MAX_DOM@|$MAX_DOM|" -e "s|@RUN_HOURS@|36|" \
      -e "s|@SY@|2009|g" -e "s|@SM@|09|g" -e "s|@SD@|08|g" -e "s|@SH@|12|g" \
      -e "s|@EY@|2009|g" -e "s|@EM@|09|g" -e "s|@ED@|10|g" -e "s|@EH@|00|g" \
      "$HERE/namelist.input.template" > namelist.input
  [ -f "$HERE/ensemble/$m.sed" ] && sed -i -f "$HERE/ensemble/$m.sed" namelist.input
  [ -f "$HERE/ensemble/$m.nml" ] && cat "$HERE/ensemble/$m.nml" >> namelist.input
  grep -E "^ (mp_physics|bl_pbl_physics|sf_sfclay_physics|cu_physics)|skebs|nens" namelist.input
  if mpirun -np "$NP" ./real.exe >/dev/null 2>&1 && grep -q "SUCCESS COMPLETE REAL" rsl.error.0000 \
     && mpirun -np "$NP" ./wrf.exe >/dev/null 2>&1 && grep -q "SUCCESS COMPLETE WRF" rsl.error.0000; then
    cp rain10min_d03_${START} ~/cansu/rain10min_d03_${C}.nc
    rm -f wrfout_d01_* wrfout_d02_* wrfinput_d0* wrfbdy_d01     # keep d03 history and the rain file
    echo "== $C OK $(date)"
  else
    echo "== $C FAILED $(date)"; tail -n 5 rsl.error.0000
  fi
  cd "$HERE"
done
echo "ENSEMBLE DONE $(date)"
