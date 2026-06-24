# ALSDS · Team 3 — Worcester Venture Map

**AI-Assisted Location Decision Support System** for evaluating retail/business
sites in Worcester, MA. Built by Team 3 for the Urban Analytics AI Consultancy
capstone (Modules 1–10).

A small-business owner drops a candidate pin on the Worcester map, picks a
business category (or types a plain label like "bakery"), and our chatbot
runs a Huff gravity model against the Azure SQL backend to predict monthly
visits, market share, and competitive pressure — with plain-language
explanations from Atlas AI (Azure OpenAI / GPT-4o).

Live deployment: [see Azure App Service URL in the team submission](https://alsds-team3-app-cye8dsgtfbckdxhd.eastus-01.azurewebsites.net/)

---

## What the system does

- **Predicts** monthly visits and market share for a proposed location.
- **Surfaces competitors** within the same NAICS category — name, distance,
  size, and current market share so the owner knows what they are walking
  into.
- **Compares scenarios** side-by-side (same NAICS only; can vary location,
  size, or both).
- **Maps** demand-point CBGs, existing POIs, and the candidate pin on a
  full-bleed Leaflet canvas.
- **Explains results** in non-technical language. Topic control keeps the
  chatbot focused on Worcester store-location decisions and refuses
  unrelated questions politely.

## Architecture

| Layer        | Stack                                                   |
| ------------ | ------------------------------------------------------- |
| Frontend     | Vanilla JS + Leaflet 1.9 + Chart.js 4.4                 |
| Backend      | Flask (Python 3.11) on Azure App Service                |
| Database     | Azure SQL (`alsds_team3_db` on `cpl-sql-prod-shared`)   |
| AI           | Azure OpenAI (GPT-4o) for explanations + Q&A           |
| Model        | Custom Huff gravity engine, vectorized via NumPy/pandas |
| Deployment   | GitHub Actions → Azure Web App                          |

## Key endpoints

| Path                | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `/`                 | Dashboard (map + chat advisor)                       |
| `/health`           | Liveness probe                                       |
| `/dbcheck`          | Azure SQL connectivity check                         |
| `/db_structure`     | Lists Azure SQL tables and row counts                |
| `/api/run_huff`     | Runs the Huff model and returns the explanation     |
| `/api/ask`          | Follow-up Q&A grounded in the latest run + scenarios |
| `/api/cbgs`         | CBG centroids (demand grid overlay)                  |
| `/api/pois`         | Competitors for a given NAICS                        |
| `/api/categories`   | Calibrated + known NAICS, plain-language aliases     |

> **`/admin/migrate` is intentionally disabled in `app.py`.** Leaving a
> one-click data migration trigger live on a production app is unsafe — if
> the migration ever needs to be re-run, uncomment the route, deploy, run it,
> then comment it back out and redeploy.

## NAICS handling (three tiers)

Per Module 9 guidance:

1. **Calibrated NAICS** (23 codes with α/β in the parameters table)
   → engine uses the calibrated row.
2. **Known POI NAICS** (~130 codes present in `worchester_businesses` but
   not calibrated) → engine falls back to **α = 1, β = 2**; UI shows a warning.
3. **Unknown NAICS** (no historical records in Worcester) → API rejects with
   a clear "no historical records" message.

## Model interface (preserved)

```python
def run_huff_model(candidate_lat, candidate_lon, business_category,
                   floor_area, db_connection=None) -> dict
```

Returns:
```python
{
  "predicted_visits": float,
  "market_share": float,
  "competitors": [...],   # top 10 nearest, each with market_share + distance
  "runtime_ms": float,
  "notes": str,
  "parameter_source": "calibrated" | "fallback_default",
  "inputs": {...}
}
```

## Local development

```bash
# 1. set Azure SQL + Azure OpenAI env vars (see DEPLOYMENT_NOTES.md)
$env:SQL_CONNECTION_STRING = "..."
$env:AZURE_OPENAI_API_KEY = "..."
$env:AZURE_OPENAI_ENDPOINT = "..."
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
$env:AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

# 2. install
pip install -r requirements.txt

# 3. run
python run_local.py
# → http://localhost:8000
```

## Module 8 UI improvements

- Bold team-branded title (Team 3 · ALSDS) in the top dock.
- About Us modal (ⓘ button) with team identity, stack, and capabilities.
- Bottom-left mini-cards now carry predicted visits, market share,
  competitor count, and runtime — pulled out of the chat pane to reduce
  clutter.
- "Results ready ▸" pulse on the details button so users discover the
  competitor chart + scenario comparison drawer.
- Competitor table now shows **current market share** instead of raw
  attraction, and is capped at 10 nearest entries.

## Module 9 system improvements

- All map and POI data flows through Azure SQL (no static GeoJSON
  dependency for runtime).
- Chatbot handles multiple model runs, partial updates ("change to 1500
  sqm", "use NAICS 5121", "42.27, -71.81"), and follow-up scenarios.
- Scenario comparison enforces the validity rules (same NAICS required;
  can share location OR size but not both).
- Plain-language tone, topic control, and protection against invented
  results are encoded in the system prompts in `app.py`.

## Limitations

- Model ignores rent, parking, visibility, zoning, and demographics —
  always surfaced in the chatbot's explanation.
- Only 23 NAICS codes have calibrated α/β; the other ~130 use a fallback
  flagged in the UI.
- POI/visit data is a Worcester snapshot — not real-time.

## Team

Team 3 — Northeastern University, Urban Analytics AI Consultancy (Spring 2026).
