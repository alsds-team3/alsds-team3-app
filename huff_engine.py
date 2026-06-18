"""
Huff Model Engine — V4 (Team 3, Azure SQL)

Module 7 upgrade of the V3 SQLite engine. Queries Azure SQL via
db.get_connection() instead of opening Data/team_3.db directly.

Preserves:
  - The exact run_huff_model(...) signature called by app.py
  - The return shape (predicted_visits, market_share, competitors,
    runtime_ms, notes, inputs) read by app.py's generate_explanation()
  - The V3 indexed-query, vectorized-math execution pattern

Differences from V3:
  - sqlite3 -> pyodbc via db.get_connection()
  - SQLite-style "?" placeholders are still used (pyodbc accepts them)
  - sqlite3.Row.fetchone() became a regular pyodbc tuple, so the param
    lookup unpacks by index instead of by key
  - Same SQL schema, same column names, same return values
"""

import math
import time
from typing import Optional

import pandas as pd
import numpy as np
import pyodbc

from db import get_connection


# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0


# -------------------------------------------------------------------
# Haversine distance (unchanged from V3)
# -------------------------------------------------------------------

def _haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = (
        math.radians(lat1),
        math.radians(lon1),
        math.radians(lat2),
        math.radians(lon2),
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _haversine_vectorized(lat1, lon1, lat2_arr, lon2_arr):
    """Vectorized haversine: one point against arrays of points, in meters."""
    lat1_r = np.radians(lat1)
    lon1_r = np.radians(lon1)
    lat2_r = np.radians(lat2_arr.values)
    lon2_r = np.radians(lon2_arr.values)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


# -------------------------------------------------------------------
# Core Huff computation
# -------------------------------------------------------------------

def huff(naics, candidate_lon, candidate_lat, floor_area, conn):
    """
    Run the Huff gravity computation against Azure SQL.

    Returns (total_predicted_visits, market_share_proxy, competitors_list),
    matching the V3 contract exactly.
    """
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Step 1: Calibrated parameters for this NAICS code
    # ------------------------------------------------------------------
    # 3-tier parameter resolution (per Module 9 guidance from Mohsen):
    #   1. Calibrated NAICS  -> use parameters table row
    #   2. Uncalibrated but present in worchester_businesses -> fallback alpha=1, beta=2
    #   3. Not present at all -> raise; the API layer turns this into the
    #      "no historical records" user message.
    cur.execute(
        "SELECT alpha, beta FROM parameters WHERE naics_code = ?",
        (naics,),
    )
    param_row = cur.fetchone()
    if param_row is not None:
        alpha = float(param_row[0])
        beta = float(param_row[1])
        used_fallback_params = False
    else:
        alpha = 1.0
        beta = 2.0
        used_fallback_params = True

    # ------------------------------------------------------------------
    # Step 2: Competing POIs for this NAICS code
    # ------------------------------------------------------------------
    naics_pois = pd.read_sql(
        """SELECT placekey, location_name, latitude, longitude, wkt_area_sq_meters
           FROM worchester_businesses
           WHERE naics_code = ?""",
        conn,
        params=[naics],
    )
    if naics_pois.empty:
        raise ValueError(f"No competing POIs found for NAICS code {naics}.")

    relevant_placekeys = naics_pois["placekey"].dropna().astype(str).unique().tolist()
    if not relevant_placekeys:
        raise ValueError(
            f"NAICS {naics} has POIs but none have a usable placekey to join "
            "against the distance/visits tables."
        )
    placeholders = ",".join("?" for _ in relevant_placekeys)

    # ------------------------------------------------------------------
    # Step 3: Distances for relevant POIs
    # ------------------------------------------------------------------
    dist_df = pd.read_sql(
        f"""SELECT cbg_id, placekey, distance_m
            FROM distances
            WHERE placekey IN ({placeholders})""",
        conn,
        params=relevant_placekeys,
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
    # Step 5: Visit counts
    # ------------------------------------------------------------------
    visits_df = pd.read_sql(
        f"""SELECT cbg_id, placekey, visit_count
            FROM visits
            WHERE placekey IN ({placeholders})""",
        conn,
        params=relevant_placekeys,
    )
    dist_df = dist_df.merge(
        visits_df, on=["cbg_id", "placekey"], how="left"
    )
    dist_df["visit_count"] = dist_df["visit_count"].fillna(0)

    # ------------------------------------------------------------------
    # Step 6: Attraction per CBG-POI pair
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
    cbg_agg = cbg_agg[cbg_agg["sum_visits"] > 0].copy()

    if cbg_agg.empty:
        # No CBGs with observed visits — model can't run.
        return 0.0, 0.0, [], used_fallback_params

    # ------------------------------------------------------------------
    # Step 8: CBG centroids and distance to candidate
    # ------------------------------------------------------------------
    cbg_ids = cbg_agg["cbg_id"].astype(str).tolist()
    cbg_ph = ",".join("?" for _ in cbg_ids)
    cbg_centroids = pd.read_sql(
        f"""SELECT cbg_id, centroid_lat, centroid_lon
            FROM cbgs
            WHERE cbg_id IN ({cbg_ph})""",
        conn,
        params=cbg_ids,
    )
    cbg_agg = cbg_agg.merge(cbg_centroids, on="cbg_id")

    if cbg_agg.empty:
        return 0.0, 0.0, [], used_fallback_params

    cbg_agg["distance"] = _haversine_vectorized(
        candidate_lat, candidate_lon,
        cbg_agg["centroid_lat"], cbg_agg["centroid_lon"],
    )

    # ------------------------------------------------------------------
    # Step 9: Candidate utility and predicted visits
    # ------------------------------------------------------------------
    Aj_alpha = floor_area ** alpha
    cbg_agg["uij"] = Aj_alpha / (cbg_agg["distance"].clip(lower=100) ** beta)

    cbg_agg["predicted_visits"] = (
        cbg_agg["uij"] * cbg_agg["sum_visits"]
    ) / (cbg_agg["uij"] + cbg_agg["sum_uik"])

    total_predicted_visits = float(cbg_agg["predicted_visits"].sum())

    total_market_visits = float(cbg_agg["sum_visits"].sum())
    market_share_proxy = (
        total_predicted_visits / total_market_visits
        if total_market_visits > 0
        else 0.0
    )

    # ------------------------------------------------------------------
    # Step 10: Competitor list for the dashboard
    #
    # For each competing POI we surface:
    #   - distance_miles : great-circle distance from the candidate site
    #                      (was None — caused "N/A" in the UI table)
    #   - attraction     : total Huff utility across all CBGs (sum of uik
    #                      contributions), giving a single comparable score
    # Then we keep the 20 nearest competitors instead of the first 20 in
    # DB order, since proximity is what matters for competitive context.
    # ------------------------------------------------------------------
    METERS_PER_MILE = 1609.344
    attraction_by_placekey = (
        dist_df.groupby("placekey")["uik"].sum().to_dict()
    )

    pois = naics_pois.copy()
    pois["latitude_f"] = pois["latitude"].apply(_safe_float)
    pois["longitude_f"] = pois["longitude"].apply(_safe_float)

    has_coords = pois["latitude_f"].notna() & pois["longitude_f"].notna()
    pois.loc[has_coords, "distance_m_from_site"] = _haversine_vectorized(
        candidate_lat,
        candidate_lon,
        pois.loc[has_coords, "latitude_f"],
        pois.loc[has_coords, "longitude_f"],
    )

    pois = pois.sort_values("distance_m_from_site", na_position="last")

    competitors = []
    for _, comp in pois.head(20).iterrows():
        dist_m = comp.get("distance_m_from_site")
        attraction = attraction_by_placekey.get(str(comp.get("placekey") or ""))
        competitors.append({
            "name": str(comp.get("location_name", "Unknown") or "Unknown"),
            "placekey": str(comp.get("placekey", "")),
            "lat": _safe_float(comp.get("latitude")),
            "lon": _safe_float(comp.get("longitude")),
            "size": _safe_float(comp.get("wkt_area_sq_meters")),
            "distance_miles": (
                round(float(dist_m) / METERS_PER_MILE, 3)
                if dist_m is not None and pd.notna(dist_m) else None
            ),
            "attraction": (
                round(float(attraction), 6)
                if attraction is not None and pd.notna(attraction) else None
            ),
        })

    return total_predicted_visits, market_share_proxy, competitors, used_fallback_params


# -------------------------------------------------------------------
# App-facing wrapper — REQUIRED SIGNATURE, do not change
# -------------------------------------------------------------------

def run_huff_model(
    candidate_lat,
    candidate_lon,
    business_category,
    floor_area,
    db_connection: Optional[pyodbc.Connection] = None,
):
    """
    Required app-facing function called by app.py.

    Parameters
    ----------
    candidate_lat : float
    candidate_lon : float
    business_category : str or int
        NAICS code (e.g. 4441 or "4441").
    floor_area : float
        Floor area in square meters.
    db_connection : pyodbc.Connection, optional
        Reuse an existing connection. If None, a new Azure SQL connection
        is opened from db.get_connection() and closed before returning.
    """
    start_time = time.perf_counter()

    try:
        naics = int(str(business_category).strip())
    except Exception as exc:
        raise ValueError(
            "business_category must be a NAICS code, for example: 4441."
        ) from exc

    candidate_lat = float(candidate_lat)
    candidate_lon = float(candidate_lon)
    floor_area = float(floor_area)

    own_conn = False
    conn = db_connection
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        total_predicted_visits, market_share, competitors, used_fallback_params = huff(
            naics=naics,
            candidate_lon=candidate_lon,
            candidate_lat=candidate_lat,
            floor_area=floor_area,
            conn=conn,
        )
    finally:
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass

    runtime_ms = round((time.perf_counter() - start_time) * 1000, 2)

    parameter_source = "fallback_default" if used_fallback_params else "calibrated"
    notes = (
        "V4 Huff model (Team 3) — Azure SQL backed, indexed queries, "
        "precomputed CBG centroids, haversine distance, NAICS-level "
        "filtering server-side. Data source: alsds_team3_db (Azure SQL)."
    )
    if used_fallback_params:
        notes += (
            f" NAICS {naics} is not calibrated in the parameters table; "
            "the engine used default alpha=1, beta=2 — results are indicative only."
        )

    return {
        "predicted_visits": round(total_predicted_visits, 2),
        "market_share": round(market_share, 6),
        "competitors": competitors,
        "runtime_ms": runtime_ms,
        "parameter_source": parameter_source,
        "notes": notes,
        "inputs": {
            "candidate_lat": candidate_lat,
            "candidate_lon": candidate_lon,
            "business_category": naics,
            "floor_area": floor_area,
        },
    }


def _safe_float(value):
    """Convert to float, returning None on failure."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


# -------------------------------------------------------------------
# Local quick test (only runs if SQL_CONNECTION_STRING is set)
# -------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys

    if not os.getenv("SQL_CONNECTION_STRING"):
        sys.stderr.write(
            "SQL_CONNECTION_STRING is not set, so the Huff engine cannot reach "
            "Azure SQL. Set it (e.g. `$env:SQL_CONNECTION_STRING = '...'` in "
            "PowerShell, or `export SQL_CONNECTION_STRING=...` in bash) before "
            "running this script directly.\n"
        )
        sys.exit(1)

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
