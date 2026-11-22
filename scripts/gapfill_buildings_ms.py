"""
Fill OpenStreetMap building gaps in the Ayamama validation basin with
Microsoft Global ML Building Footprints (ODbL, release 2026-02-03).

Only footprints that do not intersect an OSM building are kept, inside the
box lon 28.72-28.88, lat 40.96-41.13 (Ayamama basin and the 2009 survey
points). Heights > 0 give levels = round(height / 3); otherwise 3 levels.
    python scripts/gapfill_buildings_ms.py <dir with MS quadkey .csv.gz files>
Output: data/raw/ayamama_buildings_ms_gapfill.geojson
"""
import sys, glob, gzip, json, os
from shapely.geometry import shape
from shapely.strtree import STRtree
BOX = (28.72, 40.96, 28.88, 41.13)
inb = lambda x, y: BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]
osm = json.load(open("data/raw/ayamama_buildings.geojson", encoding="utf-8"))["features"]
og = []
for f in osm:
    try:
        g = shape(f["geometry"])
        c = g.centroid
        if inb(c.x, c.y): og.append(g)
    except Exception:
        pass
tree = STRtree(og)
keep, seen = [], 0
for fn in glob.glob(os.path.join(sys.argv[1], "*.csv.gz")):
    for line in gzip.open(fn, "rt"):
        f = json.loads(line); g = shape(f["geometry"]); c = g.centroid
        if not inb(c.x, c.y): continue
        seen += 1
        if len(tree.query(g, predicate="intersects")): continue
        h = f["properties"].get("height", -1)
        lv = max(1, round(h / 3)) if h and h > 0 else 3
        keep.append({"type": "Feature", "properties": {"building": "yes", "building:levels": str(lv), "source": "Microsoft GlobalMLBuildingFootprints 2026-02-03 (ODbL)"},
                     "geometry": f["geometry"]})
json.dump({"type": "FeatureCollection", "features": keep}, open("data/raw/ayamama_buildings_ms_gapfill.geojson", "w"))
print(f"OSM buildings in box: {len(og):,} | MS footprints in box: {seen:,} | added (no OSM overlap): {len(keep):,}")
