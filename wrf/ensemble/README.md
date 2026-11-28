# 2009 ensemble (9 September Ayamama storm)

Members re-use the WPS output of `ist2009r` (start 8 Sep 2009 12 UTC, end 10 Sep 00 UTC, 9/3/1 km).
The control member is `ist2009r` itself. Each member changes one thing:

| Member | Change | Why |
|---|---|---|
| e2 | Morrison 2-moment microphysics (mp 10) | cell life cycle, cold pools |
| e3 | MYNN 2.5 PBL + MYNN surface layer (5/5) | where cells are triggered |
| e4 | e2 + e3 | interaction |
| e3b | MYJ PBL + Eta surface layer (2/2), replaces e3 | MYNN-EDMF crashed at the first step on this build (SIGABRT in mynn_bl_driver) |
| e4b | e2 + e3b, replaces e4 | interaction |
| e5 | no convection scheme on the 3 km domain | explicit convection from 3 km |
| e6, e7 | stochastic kinetic-energy backscatter (SKEBS), seeds 11 and 23 | sensitivity to small initial uncertainty |

Planned, not yet included: high-resolution SST (OSTIA, needs a Copernicus Marine account).
Run: `nohup bash ../06_run_ensemble.sh > ensemble.log 2>&1 &` (waits for 05_run_queue.sh to finish).
