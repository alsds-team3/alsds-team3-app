"""
migrate_to_azure_sql.py
-----------------------
ALSDS Team 3 — Module 7 migration script.

Streams Data/team_3.db into alsds_team3_db on cpl-sql-prod-shared, via the
deployed Azure Web App. Runs inside a daemon thread so it bypasses the
Gunicorn 30-second worker timeout and the Azure edge proxy timeout.

Triggered from the browser:
    GET /admin/migrate              -> spawns background thread, returns 202
    GET /admin/migrate/status       -> polls live progress
    GET /db_structure               -> verifies row counts after completion

Table schema mirrors team_3.db exactly (see add_missing_tables.py):
    parameters             top_category, naics_code (PK), alpha, beta, correlation
    worchester_businesses  placekey, location_name, latitude, longitude,
                           wkt_area_sq_meters, naics_code, plus extra columns
    distances              cbg_id, placekey, distance_m
    visits                 cbg_id, placekey, visit_count
    cbgs                   cbg_id (PK), centroid_lat, centroid_lon

fast_executemany safety patterns (Module 7.10):
1. Every cell is cast to str / int / float / None before the driver sees it,
   to avoid the C-buffer memory-alignment crash on mixed-width string columns.
2. KEY_COLUMNS get VARCHAR(50) instead of NVARCHAR(MAX), so the post-load
   CREATE INDEX calls don't hit T-SQL error 1919.
"""

import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"
SQLITE_PATH = DATA_DIR / "team_3.db"

# Tables to migrate, in order (smaller ones first so feedback is faster).
TABLES = [
    "parameters",
    "cbgs",
    "worchester_businesses",
    "visits",
    "distances",
]

# Columns where we want an index after load. They MUST be bounded (not
# NVARCHAR(MAX)) or CREATE INDEX hits T-SQL error 1919. The exact width is
# computed from the data in _column_widths().
KEY_COLUMNS = {
    "placekey",
    "cbg_id",
    "top_category",
    "location_name",
    "city",
    "region",
    "street_address",
    "postal_code",
    "naics_code",   # only relevant when naics_code is stored as text
}

# Batch size for fast_executemany. The 606k-row distances table is the heavy
# one; 25k gives a reasonable progress cadence.
BATCH_SIZE = 25_000

# B-tree indices applied after data load. Each runs in its own try/except so
# one failure doesn't abort the rest.
INDEX_STATEMENTS = [
    ("idx_param_naics",   "CREATE INDEX idx_param_naics ON parameters (naics_code);"),
    ("idx_biz_naics",     "CREATE INDEX idx_biz_naics ON worchester_businesses (naics_code);"),
    ("idx_biz_placekey",  "CREATE INDEX idx_biz_placekey ON worchester_businesses (placekey);"),
    ("idx_dist_pk",       "CREATE INDEX idx_dist_pk ON distances (placekey);"),
    ("idx_dist_cbg",      "CREATE INDEX idx_dist_cbg ON distances (cbg_id);"),
    ("idx_vis_pk",        "CREATE INDEX idx_vis_pk ON visits (placekey);"),
    ("idx_vis_cbg",       "CREATE INDEX idx_vis_cbg ON visits (cbg_id);"),
    ("idx_cbgs_id",       "CREATE INDEX idx_cbgs_id ON cbgs (cbg_id);"),
]


# ---------------------------------------------------------------------------
# Shared status — polled by /admin/migrate/status
# ---------------------------------------------------------------------------

migration_status = {
    "status": "idle",        # idle | running | completed | failed
    "migrated_tables": {},   # per-table progress string
    "indexing": "Pending",
    "error": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _column_widths(df: pd.DataFrame) -> dict:
    """
    Measure the longest string value per text column. Used to size VARCHAR
    columns correctly under fast_executemany, which allocates a fixed-width
    buffer per column based on the declared type. If we declare too small,
    pyodbc throws 'String data, right truncation' on the first oversized row.
    """
    widths = {}
    for col in df.columns:
        if df[col].dtype == object:
            # Coerce everything to str so None / NaN / numbers don't crash len()
            try:
                longest = df[col].astype(str).str.len().max()
                widths[col] = int(longest) if longest and longest > 0 else 1
            except Exception:
                widths[col] = 4000
    return widths


def _round_up_width(n: int) -> int:
    """
    Round a measured string width up to a sensible VARCHAR size, with
    generous headroom in case a re-migration sees slightly different data.
    """
    n = max(n, 1)
    for cap in (50, 100, 200, 500, 1000, 2000, 4000):
        if n <= cap:
            return cap
    return 8000   # max for non-MAX VARCHAR


def _sql_type_for(col_name: str, dtype, measured_width: int = None) -> str:
    """
    Pick a T-SQL column type.

    Text columns get a bounded VARCHAR(N) sized to the measured longest
    value (rounded up), with one exception: very long values (> 4000 chars,
    e.g. polygon_wkt) fall back to NVARCHAR(MAX). Those columns will NOT be
    indexable, which is fine since we don't index them.
    """
    dtype_str = str(dtype).lower()
    if "int" in dtype_str:
        return "BIGINT"
    if "float" in dtype_str:
        return "FLOAT"
    if "bool" in dtype_str:
        return "BIT"

    # Text column. Use the measured width if we have it.
    if measured_width is not None and measured_width > 4000:
        return "NVARCHAR(MAX)"
    if measured_width is not None:
        width = _round_up_width(measured_width)
        return f"VARCHAR({width})"

    # Fallback when we couldn't measure (shouldn't happen for normal DataFrames).
    return "NVARCHAR(MAX)"


def _sanitize_row(row) -> tuple:
    """
    Cast every value in a row to a clean Python primitive before pyodbc sees
    it. Skipping this step is what causes the cryptic memory-alignment crash
    described in Module 7.10.
    """
    cleaned = []
    for v in row:
        if v is None:
            cleaned.append(None)
        elif isinstance(v, float) and np.isnan(v):
            cleaned.append(None)
        elif isinstance(v, (int, np.integer)):
            cleaned.append(int(v))
        elif isinstance(v, (float, np.floating)):
            cleaned.append(float(v))
        else:
            cleaned.append(str(v))
    return tuple(cleaned)


def _migrate_one_table(table: str, sqlite_conn, azure_conn) -> None:
    """Drop, create, bulk-insert one table."""
    migration_status["migrated_tables"][table] = "Reading SQLite..."

    # Skip gracefully if the table doesn't exist locally.
    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    if cur.fetchone() is None:
        migration_status["migrated_tables"][table] = "Skipped (not in SQLite)"
        return

    df = pd.read_sql_query(f"SELECT * FROM {table};", sqlite_conn)
    if df.empty:
        migration_status["migrated_tables"][table] = "Skipped (0 rows)"
        return

    df = df.replace({np.nan: None})

    # Measure string column widths before building the schema. This is the
    # fix for the 'String data, right truncation' error under fast_executemany.
    widths = _column_widths(df)

    # Schema
    col_defs = []
    for col_name, dtype in df.dtypes.items():
        sql_type = _sql_type_for(col_name, dtype, widths.get(col_name))
        col_defs.append(f"[{col_name}] {sql_type}")
    create_sql = f"CREATE TABLE [{table}] ({', '.join(col_defs)});"

    azure_cur = azure_conn.cursor()
    azure_cur.execute(f"DROP TABLE IF EXISTS [{table}];")
    azure_cur.execute(create_sql)
    azure_conn.commit()

    # Insert
    columns = [f"[{c}]" for c in df.columns]
    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = (
        f"INSERT INTO [{table}] ({', '.join(columns)}) VALUES ({placeholders})"
    )

    migration_status["migrated_tables"][table] = "Sanitizing rows..."
    records = [
        _sanitize_row(row) for row in df.itertuples(index=False, name=None)
    ]
    total = len(records)

    azure_cur.fast_executemany = True

    inserted = 0
    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        azure_cur.executemany(insert_sql, batch)
        azure_conn.commit()
        inserted += len(batch)
        migration_status["migrated_tables"][table] = (
            f"Inserting... {inserted:,}/{total:,}"
        )

    migration_status["migrated_tables"][table] = f"Success ({total:,} rows)"


def _build_indices(azure_conn) -> None:
    """Apply B-tree indices, tolerating individual failures."""
    cur = azure_conn.cursor()
    applied, skipped = [], []
    for name, stmt in INDEX_STATEMENTS:
        try:
            cur.execute(stmt)
            azure_conn.commit()
            applied.append(name)
        except Exception as exc:
            skipped.append(f"{name}: {exc}")

    summary = f"Applied {len(applied)} indices."
    if skipped:
        summary += f" Skipped: {'; '.join(skipped)}"
    migration_status["indexing"] = summary


# ---------------------------------------------------------------------------
# Entry point — called by /admin/migrate in a background thread
# ---------------------------------------------------------------------------

def execute_migration_task() -> None:
    """Background worker. Updates migration_status throughout."""
    global migration_status
    migration_status.update({
        "status": "running",
        "migrated_tables": {t: "Pending" for t in TABLES},
        "indexing": "Pending",
        "error": None,
    })

    if not SQLITE_PATH.exists():
        migration_status["status"] = "failed"
        migration_status["error"] = f"SQLite database not found at {SQLITE_PATH}"
        return

    azure_conn_str = os.getenv("SQL_CONNECTION_STRING")
    if not azure_conn_str:
        migration_status["status"] = "failed"
        migration_status["error"] = "SQL_CONNECTION_STRING is not set."
        return

    sqlite_conn = None
    azure_conn = None
    try:
        sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
        azure_conn = pyodbc.connect(azure_conn_str, timeout=60)

        for table in TABLES:
            try:
                _migrate_one_table(table, sqlite_conn, azure_conn)
            except Exception as exc:
                migration_status["migrated_tables"][table] = f"Failed: {exc}"

        _build_indices(azure_conn)
        migration_status["status"] = "completed"

    except Exception as exc:
        migration_status["status"] = "failed"
        migration_status["error"] = str(exc)
    finally:
        if sqlite_conn is not None:
            try:
                sqlite_conn.close()
            except Exception:
                pass
        if azure_conn is not None:
            try:
                azure_conn.close()
            except Exception:
                pass
