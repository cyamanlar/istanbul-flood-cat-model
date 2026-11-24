"""
Replay a WRF case through the building-level module (Ayamama box) instead of
station interpolation. Compares with the 2009 observed depths (Gulbaz et al.).

    python wrf/04_wrf_building_replay.py ist2009
Needs outputs/wrf/<case>/points.csv from 03_wrf_rain_check.py and the
building-level inputs (see run_building_level.py).
Output: outputs/wrf/<case>/building_replay.json, building_pointwise.csv
"""
import json, os, sys
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import run_building_level as rbl
from src import building_level as bl

case = sys.argv[1]; out = f"outputs/wrf/{case}"
pts = pd.read_csv(f"{out}/points.csv")
cfg = json.load(open("config.json", encoding="utf-8")); cb = cfg["building_level"]
dem, s, b = rbl.prepare(cb, os.path.normpath(os.path.join(ROOT, cb["data_dir"])))
box = pts[(pts.lon.between(s.lon.min() - 0.1, s.lon.max() + 0.1)) & (pts.lat.between(s.lat.min() - 0.1, s.lat.max() + 0.1))]
p_stream = bl.idw_rainfall(box, s.lon, s.lat)[None, :]
d = bl.building_depth(bl.driving_rainfall(p_stream, s, b), b, cb["hazard"])[0]
loss = bl.building_loss(d[None, :], b)[0]
on_ay = (s.system.to_numpy()[b.stream_idx.clip(0)] == "Ayamama Deresi") & (b.stream_idx.to_numpy() >= 0)
rows = []
for _, p in rbl.GULBAZ_2018.iterrows():
    dk = np.hypot((b.lat.to_numpy() - p.lat) * 111.0, (b.lon.to_numpy() - p.lon) * 111.0 * np.cos(np.radians(41.0)))
    sel = on_ay & (dk <= 1.0) & (d > 0); dd = d[sel]
    rows.append(dict(location=p.location, observed_depth_m=p.observed_depth_m, n_flooded=int(sel.sum()),
                     model_median_m=round(float(np.median(dd)), 2) if len(dd) else 0.0))
pv = pd.DataFrame(rows); pv.to_csv(f"{out}/building_pointwise.csv", index=False)
m = pv[pv.location != "Cobancesme"]
res = dict(case=case, ayamama_rain_mm=round(float(p_stream[0][(s.system == "Ayamama Deresi").to_numpy()].mean()), 1),
           flooded_buildings=int((d > 0).sum()), event_loss_eur_m=round(float(loss.sum()) / 1e6, 1),
           pointwise_MAE_m=round(float((m.model_median_m - m.observed_depth_m).abs().mean()), 2) if case == "ist2009" else None)
json.dump(res, open(f"{out}/building_replay.json", "w"), indent=2); print(json.dumps(res, indent=2)); print(pv.to_string(index=False))
