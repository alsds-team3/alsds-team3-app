"""
Huff Model Engine — V3 (Team 3 Optimized)

Replaces the baseline CSV-based engine with a SQLite-backed implementation.

Key optimizations over baseline:
  1. SQL-level filtering — only rows matching the requested NAICS code are
     retrieved, instead of loading entire CSV files into memory.
  2. Precomputed UTM centroids — CBG centroids are stored in the database,
     eliminating the need to load and project the full GeoJSON at runtime.
  3. Indexed queries — the database uses indexes on naics_code, placekey,
     and cbg_id for fast lookups.
  4. Lightweight distance calculation — candidate point is projected to UTM
     using pyproj and Euclidean distance is computed via math, avoiding
     heavy geopandas geometry operations at query time.
  5. Vectorized computation — pandas is used for the Huff probability
     math after data retrieval, keeping the computation efficient.

Function signature and return structure match the baseline exactly so that
app.py requires no changes.
"""

import math
import sqlite3
import time
from pathlib import Path

import pandas as pd
from pyproj import Transformer

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "Data" / "your_team.db"

# Reusable transformer: WGS84 (lon/lat) → UTM Zone 19N (meters)
_transformer = Transformer.from_crs("EPSG:4326", "EPSG:26919", always_xy=True)


# -------------------------------------------------------------------
# Database helper
# -------------------------------------------------------------------

def _get_connection():
    """Return a SQLite connection to the team database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------------------------------------------
# Core Huff computation
# -------------------------------------------------------------------

def huff(naics, candidate_lon, candidate_lat, floor_area, conn):
    """
    Compute predicted visits and market share for a candidate store.

    All data is retrieved from the SQLite database using indexed queries
    filtered to the requested NAICS code.

    Parameters
    ----------
    naics : int
        NAICS code identifying the retail category.
    candidate_lon : float
        Longitude of the candidate store (WGS84).
    candidate_lat : float
        Latitude of the candidate store (WGS84).
    floor_area : float
        Floor area of the candidate store in square meters.
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    tuple
        (total_predicted_visits, market_share_proxy, competitors_list)
    """

    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Step 1: Retrieve calibrated parameters for the NAICS code
    # ------------------------------------------------------------------
    cur.execute(
        "SELECT alpha, beta FROM parameters WHERE naics_code = ?",
        (naics,),
    )
    param_row = cur.fetchone()
    if param_row is None:
        raise ValueError(
            f"No calibrated alpha/beta parameters found for NAICS code {naics}."
        )
    alpha = param_row["alpha"]
    beta = param_row["beta"]

    # ------------------------------------------------------------------
    # Step 2: Retrieve competing POIs for this NAICS code
    # ------------------------------------------------------------------
    cur.execute(
        """SELECT placekey, location_name, latitude, longitude, wkt_area_sq_meters
           FROM pois WHERE naics_code = ?""",
        (naics,),
    )
    poi_rows = cur.fetchall()
    if not poi_rows:
        raise ValueError(f"No competing POIs found for NAICS code {naics}.")

    naics_pois = pd.DataFrame(
        [dict(r) for r in poi_rows],
        columns=["placekey", "location_name", "latitude", "longitude", "wkt_area_sq_meters"],
    )
    relevant_placekeys = set(naics_pois["placekey"])
    placeholders = ",".join("?" for _ in relevant_placekeys)
    pk_list = list(relevant_placekeys)

    # ------------------------------------------------------------------
    # Step 3: Retrieve distances for relevant POIs
    # ------------------------------------------------------------------
    dist_df = pd.read_sql_query(
        f"SELECT cbg_id, placekey, distance_m FROM distances WHERE placekey IN ({placeholders})",
        conn,
        params=pk_list,
    )

    # ------------------------------------------------------------------
    # Step 4: Merge floor area onto distance rows
    # ------------------------------------------------------------------
    area_map = naics_pois.set_index("placekey")["wkt_area_sq_meters"]
    dist_df = dist_df.merge(
        area_map.rename("wkt_area_sq_meters"),
        left_on="placekey",
        right_index=True,
    )

    # ------------------------------------------------------------------
    # Step 5: Retrieve and merge visit counts
    # ------------------------------------------------------------------
    visits_df = pd.read_sql_query(
        f"SELECT cbg_id, placekey, visit_count FROM visits WHERE placekey IN ({placeholders})",
        conn,
        params=pk_list,
    )
    dist_df = dist_df.merge(
        visits_df, on=["cbg_id", "placekey"], how="left"
    )
    dist_df["visit_count"] = dist_df["visit_count"].fillna(0)

    # ------------------------------------------------------------------
    # Step 6: Compute attraction for each existing CBG-POI pair
    # ------------------------------------------------------------------
    dist_df["uik"] = (
        dist_df["wkt_area_sq_meters"] ** alpha
    ) / (dist_df["distance_m"].clip(lower=100) ** beta)

    # ------------------------------------------------------------------
    # Step 7: Aggregate to CBG level
    # ------------------------------------------------------------------
    cbg_agg = (
        dist_df.groupby("cbg_id")[["uik", "visit_count"]]
        .sum()
        .reset_index()
        .rename(columns={"uik": "sum_uik", "visit_count": "sum_visits"})
    )
    # Exclude CBGs with zero observed visits for this category
    cbg_agg = cbg_agg[cbg_agg["sum_visits"] > 0].copy()

    # ------------------------------------------------------------------
    # Step 8: Retrieve CBG centroids and compute distance to candidate
    # ------------------------------------------------------------------
    cbg_ids = list(cbg_agg["cbg_id"])
    cbg_ph = ",".join("?" for _ in cbg_ids)
    cbg_centroids = pd.read_sql_query(
        f"SELECT cbg_id, centroid_utm_x, centroid_utm_y FROM cbgs WHERE cbg_id IN ({cbg_ph})",
        conn,
        params=cbg_ids,
    )
    cbg_agg = cbg_agg.merge(cbg_centroids, on="cbg_id")

    # Project candidate point to UTM Zone 19N
    cand_utm_x, cand_utm_y = _transformer.transform(candidate_lon, candidate_lat)

    # Euclidean distance in meters (UTM coordinates)
    cbg_agg["distance"] = (
        ((cbg_agg["centroid_utm_x"] - cand_utm_x) ** 2
         + (cbg_agg["centroid_utm_y"] - cand_utm_y) ** 2)
        ** 0.5
    )

    # ------------------------------------------------------------------
    # Step 9: Compute candidate store utility and predicted visits
    # ------------------------------------------------------------------
    Aj_alpha = floor_area ** alpha
    cbg_agg["uij"] = Aj_alpha / (cbg_agg["distance"].clip(lower=100) ** beta)

    cbg_agg["predicted_visits"] = (
        cbg_agg["uij"] * cbg_agg["sum_visits"]
    ) / (cbg_agg["uij"] + cbg_agg["sum_uik"])

    total_predicted_visits = float(cbg_agg["predicted_visits"].sum())

    # Market share proxy
    total_market_visits = float(cbg_agg["sum_visits"].sum())
    market_share_proxy = (
        total_predicted_visits / total_market_visits
        if total_market_visits > 0
        else 0.0
    )

    # ------------------------------------------------------------------
    # Step 10: Build competitor list for the dashboard
    # ------------------------------------------------------------------
    competitors = []
    for _, comp in naics_pois.head(20).iterrows():
        competitors.append({
            "name": str(comp.get("location_name", "Unknown") or "Unknown"),
            "placekey": str(comp.get("placekey", "")),
            "lat": _safe_float(comp.get("latitude")),
            "lon": _safe_float(comp.get("longitude")),
            "size": _safe_float(comp.get("wkt_area_sq_meters")),
            "distance_miles": None,
            "attraction": None,
        })

    return total_predicted_visits, market_share_proxy, competitors


# -------------------------------------------------------------------
# App-facing wrapper (REQUIRED SIGNATURE — do not change)
# -------------------------------------------------------------------

def run_huff_model(
    candidate_lat,
    candidate_lon,
    business_category,
    floor_area,
    db_connection=None,
):
    """
    Required app-facing function called by app.py.

    Parameters
    ----------
    candidate_lat : float
        Candidate store latitude (WGS84).
    candidate_lon : float
        Candidate store longitude (WGS84).
    business_category : str or int
        NAICS code (e.g. 4441).
    floor_area : float
        Candidate store floor area in square meters.
    db_connection : optional
        If provided, used as the database connection. Otherwise a new
        SQLite connection is opened to Data/your_team.db.

    Returns
    -------
    dict
        Structured result for the dashboard and chatbot.
    """

    start_time = time.perf_counter()

    # Validate inputs
    try:
        naics = int(str(business_category).strip())
    except Exception as exc:
        raise ValueError(
            "business_category must be a NAICS code, for example: 4441."
        ) from exc

    candidate_lat = float(candidate_lat)
    candidate_lon = float(candidate_lon)
    floor_area = float(floor_area)

    # Use provided connection or open a new one
    own_conn = False
    conn = db_connection
    if conn is None:
        conn = _get_connection()
        own_conn = True

    try:
        total_predicted_visits, market_share, competitors = huff(
            naics=naics,
            candidate_lon=candidate_lon,
            candidate_lat=candidate_lat,
            floor_area=floor_area,
            conn=conn,
        )
    finally:
        if own_conn:
            conn.close()

    runtime_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return {
        "predicted_visits": round(total_predicted_visits, 2),
        "market_share": round(market_share, 6),
        "competitors": competitors,
        "runtime_ms": runtime_ms,
        "notes": (
            "V3 Huff model (Team 3) — SQLite-backed with indexed queries, "
            "precomputed UTM centroids, and SQL-level NAICS filtering. "
            "Data source: Data/your_team.db"
        ),
        "inputs": {
            "candidate_lat": candidate_lat,
            "candidate_lon": candidate_lon,
            "business_category": naics,
            "floor_area": floor_area,
        },
    }


def _safe_float(value):
    """Convert a value to float, returning None on failure."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


# -------------------------------------------------------------------
# Local quick test
# -------------------------------------------------------------------
if __name__ == "__main__":
    result = run_huff_model(
        candidate_lat=42.24,
        candidate_lon=-71.78,
        business_category=4441,
        floor_area=1000,
    )
    print(f"Predicted visits : {result['predicted_visits']}")
    print(f"Market share     : {result['market_share']}")
    print(f"Competitors      : {len(result['competitors'])}")
    print(f"Runtime (ms)     : {result['runtime_ms']}")
    print(f"Notes            : {result['notes']}")
