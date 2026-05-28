# Module 7 Deployment Runbook — ALSDS Team 3

What to do, in order. Assumes the Module 6 deployment already works
(Flask app + Azure Web App + GitHub Actions) and that the Azure App Service
environment variable `SQL_CONNECTION_STRING` is already set pointing at
`alsds_team3_db`.

## Files changed in this Module 7 update

- `huff_engine.py` — REPLACED. V4 (Azure SQL via `db.get_connection()`).
- `migrate_to_azure_sql.py` — NEW.
- `app.py` — three new routes added after `/dbcheck`:
  `/admin/migrate`, `/admin/migrate/status`, `/db_structure`.
- `db.py` — UNCHANGED. Already had `get_connection()` and `test_connection()`.
- `requirements.txt` — UNCHANGED. `pyodbc==5.1.0` is already present.

## Step-by-step

1. **Commit on dev branch.** Push to GitHub.
2. **Open PR `dev` -> `main`.** Review the diff (especially `app.py` and
   `huff_engine.py`), then merge.
3. **Watch GitHub Actions** at github.com -> Actions tab. Wait for the
   deploy job to go green. If it fails, read the red error before pushing
   anything else.
4. **Visit `/health`.** Expect `{"status": "ok"}`. If not, the app didn't
   start — check Azure Log Stream.
5. **Visit `/dbcheck`.** Expect `{"ok": true}`. `{"ok": false}` here usually
   means `SQL_CONNECTION_STRING` is missing or pointing at the wrong DB.
6. **Trigger the migration once:** GET `/admin/migrate`. Expect a 202 with
   `progress_url`.
7. **Poll `/admin/migrate/status` until status is `completed`.** The 606k-row
   `distances` table takes a couple of minutes; you'll see progress like
   `"Inserting... 525,000/606,281"` per table.
8. **Visit `/db_structure`.** Expect (approximately):
   ```json
   [
     {"TABLE_NAME": "cbgs",                  "row_count": 149},
     {"TABLE_NAME": "distances",             "row_count": 606281},
     {"TABLE_NAME": "parameters",            "row_count": 23},
     {"TABLE_NAME": "visits",                "row_count": 26924},
     {"TABLE_NAME": "worchester_businesses", "row_count": 4069}
   ]
   ```
   Compare against `team_3.db` row counts — they should match exactly.
9. **Test the model from the deployed UI.** Pick a location on the map,
   enter NAICS 4441 (Building Material and Supplies) or 447110 (Gas Stations),
   floor area 1000, and run. You should get back `predicted_visits`,
   `market_share`, a `competitors` list, and a GPT explanation.

## Don't forget

- **Don't re-run `/admin/migrate` while it's still running** — the endpoint
  returns 202 with the current status if a previous run is active. Re-running
  after completion is safe; the script drops and recreates each table.
- **Don't push directly to `main`** while testing — every push triggers a
  full Azure redeploy that interrupts whatever's running.
- **Keep `Data/team_3.db` in the repo** until the deployed app passes step 8.
  Only delete it after `/db_structure` confirms migration worked, then push
  the deletion as a separate commit so you can revert if needed.

## Debugging order if something breaks

Fix layer N before moving to layer N+1:

1. GitHub Actions deploy job → check workflow logs in GitHub.
2. `/health` returns 200 → check Azure Log Stream for Python crash on startup.
3. `/dbcheck` returns `{"ok": true}` → check `SQL_CONNECTION_STRING` env var.
4. `/admin/migrate/status` shows `status: completed` → if a table reads
   `Failed: ...`, the message tells you what to fix.
5. `/db_structure` row counts match SQLite → if a table is missing, check
   that it exists in `team_3.db` (run `sqlite3 Data/team_3.db ".tables"`
   locally).
6. `/api/run_huff` returns sensible numbers → if `predicted_visits` is 0,
   probably no overlap between the candidate-relevant CBGs and observed
   visits in the database.

## NAICS codes that have calibrated parameters

The 23 categories in `parameters` (use these to test the model — others
will raise `ValueError: No calibrated alpha/beta`):

| NAICS  | Category                                       |
|--------|------------------------------------------------|
| 4441   | Building Material and Supplies Dealers         |
| 311811 | Bakeries and Tortilla Manufacturing            |
| 3399   | Other Miscellaneous Manufacturing              |
| 447110 | Gasoline Stations                              |
| 621210 | Offices of Dentists                            |
| 522310 | Activities Related to Credit Intermediation    |
| 922110 | Justice, Public Order, and Safety Activities   |
| 453991 | Other Miscellaneous Store Retailers            |
| 441310 | Automotive Parts, Accessories, and Tire Stores |
| 445310 | Beer, Wine, and Liquor Stores                  |
| ...    | (13 more — see `parameters` table for full list) |
