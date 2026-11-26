#!/bin/bash
# Download ERA5 for several cases, remove the CDS key, then run them one after another.
#   nohup bash 05_run_queue.sh ist2009r ist2017 ist2011 ist2015 ist2016 > queue.log 2>&1 &
# A failed case is logged and the queue moves on. Progress: tail queue.log
cd "$(dirname "$0")"
for c in "$@"; do python3 01_download_era5_for_wrf.py "$c" || echo "DOWNLOAD FAILED $c"; done
rm -f ~/.cdsapirc; echo "CDS key removed $(date)"
for c in "$@"; do
  echo "== $c start $(date)"
  df -h ~ | tail -1
  FOREGROUND=1 bash 02_run_case.sh "$c" || echo "RUN FAILED $c"
  echo "== $c end $(date)"
done
echo "QUEUE DONE $(date)"
