# Module 7 Technical Summary — ALSDS Team 3

## Migration overview

We migrated the local SQLite database (`Data/team_3.db`) into our assigned
Azure SQL database (`alsds_team3_db`) on the shared server `cpl-sql-prod-shared`.
The application no longer reads any local `.db` file at runtime; all
production data lives in Azure SQL and is reached over the network through
a `SQL_CONNECTION_STRING` injected by Azure App Service.

### Tables migrated

| Table                   | Purpose                                       | Approx. rows |
|-------------------------|-----------------------------------------------|--------------|
| `parameters`            | Calibrated alpha / beta per NAICS code        | 23           |
| `cbgs`                  | CBG IDs with precomputed centroid lat/lon     | 149          |
| `worchester_businesses` | POIs with location, floor area, NAICS code    | 4,069        |
| `visits`                | Observed CBG-to-POI visit counts              | 26,924       |
| `distances`             | Precomputed POI-to-CBG distances in meters    | 606,281      |

Verified via `/db_structure`.

## How the migration script works

`migrate_to_azure_sql.py` runs inside a daemon thread spawned by
`/admin/migrate`. Running it synchronously inside a Flask request would fail
two ways: Gunicorn kills any worker holding a request longer than 30
seconds, and the Azure edge proxy severs the client socket on its own
timeout. By moving the work to a thread we return `202 Accepted` to the
browser in milliseconds and stream the work safely in the container's memory.

The script does five things per table:

1. **Reads** the SQLite table into a pandas DataFrame, skipping any table
   that doesn't exist locally so a missing optional table doesn't abort the
   whole migration.
2. **Sanitizes** every cell into a clean Python primitive (`str`, `int`,
   `float`, or `None`). This is the fix for the `fast_executemany` memory
   alignment bug — leaving NumPy `NaN` mixed into a string column causes the
   underlying C buffer to misalign and crash the thread.
3. **Builds the schema** with explicit `VARCHAR(50)` casting on every column
   that will later be indexed (`placekey`, `cbg_id`, `top_category`,
   `location_name`, address fields). Without this, pandas defaults text
   columns to `NVARCHAR(MAX)`, which can't be B-tree indexed (T-SQL error 1919).
4. **Drops and recreates** the table so the endpoint is idempotent — the
   team can re-run after a partial failure without duplicate-row errors.
5. **Bulk inserts** in 25,000-row batches via `cursor.fast_executemany = True`,
   committing per batch and updating a shared `migration_status` dict the
   browser polls via `/admin/migrate/status`.

After all tables load, eight B-tree indices are applied (`naics_code` on
parameters and businesses, `placekey` and `cbg_id` on distances and visits,
etc.). Each runs in its own try/except so a single failure doesn't lose the
others.

The connection string is never in code — it's read from `SQL_CONNECTION_STRING`,
which Azure App Service injects at runtime. The repo contains no credentials.

## How the Huff engine queries Azure SQL

`huff_engine.py` preserves the exact `run_huff_model(candidate_lat,
candidate_lon, business_category, floor_area, db_connection=None)` signature
and the exact return shape (`predicted_visits`, `market_share`, `competitors`,
`runtime_ms`, `notes`, `inputs`) that `app.py` already calls and parses. The
only difference from V3 (Module 6) is the connection layer:

| V3 (SQLite)                             | V4 (Azure SQL)                          |
|-----------------------------------------|-----------------------------------------|
| `sqlite3.connect("Data/team_3.db")`     | `db.get_connection()` -> `pyodbc`       |
| `sqlite3.Row` (dict-style)              | positional tuple from `pyodbc`          |
| All other logic identical               | All other logic identical               |

The model runs in the same ten steps as V3:

1. Look up `(alpha, beta)` for the NAICS code in `parameters`.
2. Pull every POI in `worchester_businesses` matching that NAICS code.
3. Pull `distances` rows for those competitor placekeys (server-side filter,
   not the whole 606k-row table).
4. Merge competitor floor area onto each distance row.
5. Merge observed `visits` onto each `(cbg_id, placekey)` pair.
6. Compute competitor utility `u_ik = area^alpha / max(distance, 100)^beta`.
7. Aggregate per CBG: sum of competitor utilities and sum of observed visits.
8. Pull centroid lat/lon from `cbgs` for the relevant CBGs and compute
   haversine distance from the candidate to each centroid (vectorized
   NumPy).
9. Compute candidate utility `u_ij = floor_area^alpha / max(distance, 100)^beta`
   and predicted visits `(u_ij / (u_ij + sum_u_ik)) * sum_visits`.
10. Return total predicted visits, market share (predicted / total observed
    visits), and a competitor sample for the dashboard.

## Optimization and precomputation

- **Server-side filtering**: distance and visit queries pull only rows
  matching the competitor placekey set, not full tables. Saves transferring
  ~600k rows over the network per model run.
- **Parameterized queries** (`?` placeholders) throughout — prevents SQL
  injection, lets the ODBC driver cache plans, and matches the SQLite
  syntax so the V3 -> V4 port was mechanical.
- **VARCHAR(50) on indexed columns** at table-creation time, enabling the
  eight B-tree indices that make per-NAICS POI lookups run in milliseconds.
- **Precomputed CBG centroids** in the `cbgs` table (set up in Module 5 by
  `add_missing_tables.py`) — the runtime engine never touches GeoJSON or
  GeoPandas; haversine math runs in pure NumPy.
- **Batched inserts** at 25k rows per `executemany`, balancing memory
  pressure against round-trip count.
- **Vectorized haversine** via NumPy applied to all relevant CBG centroids
  at once, instead of looping per CBG.

## Problems encountered and how we solved them

**Schema mismatch between Module 7 spec and our actual SQLite database.**
The Module 7.10 example assumed table names like `pois` and
`distance_matrix`; our Module 5 work produced `worchester_businesses` (note
the typo, kept for compatibility with V3) and `distances`. Fix: read the
real schema out of `team_3.db` first, then write the migration `TABLES`
list and `huff_engine.py` SQL to match exactly.

**fast_executemany memory alignment crashes.** Mixing `np.nan`, `np.int64`,
and native Python strings in the same row crashes pyodbc with an opaque
C-buffer error. Fix: row-by-row sanitization that explicitly casts every
value to `str` / `int` / `float` / `None` before the driver sees it.

**T-SQL error 1919 on CREATE INDEX.** Pandas writes text columns as
`NVARCHAR(MAX)` by default, which can't be indexed. Fix: a `KEY_COLUMNS` set
in the migration script forces those columns to `VARCHAR(50)` at
table-creation time.

**Gunicorn 30-second worker timeout.** The 606k-row distances migration
takes 2-4 minutes — synchronous execution gets killed mid-load. Fix: spawn
a daemon thread from `/admin/migrate`, return `202 Accepted` immediately,
expose `/admin/migrate/status` for the browser to poll.

**Preserving the V3 return shape.** `app.py` reads specific fields
(`predicted_visits`, `market_share`, `runtime_ms`) when generating the GPT
explanation. Fix: ported only the connection layer; left the math and
return structure identical to V3, with notes updated to say "V4 / Azure SQL".

## Submission

- GitHub repository: <fill in>
- Deployed Azure Web App: <fill in>
- `/db_structure` endpoint: `<deployed-url>/db_structure`
