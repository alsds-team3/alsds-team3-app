"""
add_missing_tables.py — Adds the tables missing from team_3.db
Run once:  python add_missing_tables.py
"""
import sqlite3, os, json
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "Data")
DB   = os.path.join(DATA, "team_3.db")

conn = sqlite3.connect(DB)
cur  = conn.cursor()

# 1. parameters
print("Adding parameters table...")
params = pd.read_csv(os.path.join(DATA, "calibrated_parameters_filtered.csv"))
params.rename(columns={"NAICS code": "naics_code"}, inplace=True)
cur.execute("DROP TABLE IF EXISTS parameters")
cur.execute("""CREATE TABLE parameters (
    top_category TEXT, naics_code INTEGER PRIMARY KEY,
    alpha REAL, beta REAL, correlation REAL)""")
for _, r in params.iterrows():
    cur.execute("INSERT INTO parameters VALUES (?,?,?,?,?)",
        (r["top_category"], int(r["naics_code"]), r["alpha"], r["beta"], r["correlation"]))
print(f"  {len(params)} rows")

# 2. distances
print("Adding distances table (this takes a minute)...")
dist = pd.read_csv(os.path.join(DATA, "worcester_cbg_poi_distance.csv.zip"), compression="zip")
cur.execute("DROP TABLE IF EXISTS distances")
cur.execute("CREATE TABLE distances (cbg_id TEXT, placekey TEXT, distance_m REAL)")
rows = [(str(r["GEOID10"]), str(r["placekey"]), float(r["distance_m"])) for _, r in dist.iterrows()]
cur.executemany("INSERT INTO distances VALUES (?,?,?)", rows)
cur.execute("CREATE INDEX idx_dist_pk ON distances (placekey)")
cur.execute("CREATE INDEX idx_dist_cbg ON distances (cbg_id)")
print(f"  {len(rows)} rows")

# 3. visits
print("Adding visits table...")
visits = pd.read_csv(os.path.join(DATA, "worcester_cbg_poi_visits.csv"))
cur.execute("DROP TABLE IF EXISTS visits")
cur.execute("CREATE TABLE visits (cbg_id TEXT, placekey TEXT, visit_count INTEGER)")
vrows = [(str(r["visitor_home_cbg"]), str(r["placekey"]), int(r["visit_count"])) for _, r in visits.iterrows()]
cur.executemany("INSERT INTO visits VALUES (?,?,?)", vrows)
cur.execute("CREATE INDEX idx_vis_pk ON visits (placekey)")
cur.execute("CREATE INDEX idx_vis_cbg ON visits (cbg_id)")
print(f"  {len(vrows)} rows")

# 4. cbgs (centroids from geojson)
print("Adding cbgs table with centroids...")
try:
    import geopandas as gpd
    gdf = gpd.read_file(os.path.join(DATA, "worcester_cbgs_map.geojson"))
    gdf["centroid_lat"] = gdf.geometry.centroid.y
    gdf["centroid_lon"] = gdf.geometry.centroid.x
except Exception:
    # Fallback: parse geojson manually
    with open(os.path.join(DATA, "worcester_cbgs_map.geojson"), "r") as f:
        gj = json.load(f)
    records = []
    for feat in gj["features"]:
        geoid = feat["properties"].get("GEOID10", feat["properties"].get("GEOID"))
        coords = feat["geometry"]["coordinates"]
        # Flatten all coordinate rings
        pts = []
        def flatten(c):
            if isinstance(c[0], (int, float)):
                pts.append(c)
            else:
                for item in c:
                    flatten(item)
        flatten(coords)
        avg_lon = sum(p[0] for p in pts) / len(pts)
        avg_lat = sum(p[1] for p in pts) / len(pts)
        records.append({"GEOID10": geoid, "centroid_lat": avg_lat, "centroid_lon": avg_lon})
    gdf = pd.DataFrame(records)

cur.execute("DROP TABLE IF EXISTS cbgs")
cur.execute("CREATE TABLE cbgs (cbg_id TEXT PRIMARY KEY, centroid_lat REAL, centroid_lon REAL)")
if hasattr(gdf, 'iterrows'):
    for _, r in gdf.iterrows():
        geoid = str(r.get("GEOID10", r.get("GEOID")))
        cur.execute("INSERT OR IGNORE INTO cbgs VALUES (?,?,?)",
            (geoid, float(r["centroid_lat"]), float(r["centroid_lon"])))

# 5. Add index on worchester_businesses naics_code
try:
    cur.execute("CREATE INDEX IF NOT EXISTS idx_biz_naics ON worchester_businesses (naics_code)")
except Exception:
    pass

conn.commit()
conn.close()

size_mb = os.path.getsize(DB) / (1024*1024)
print(f"\nDone! team_3.db is now {size_mb:.1f} MB")
if size_mb > 100:
    print("WARNING: exceeds 100 MB GitHub limit!")
