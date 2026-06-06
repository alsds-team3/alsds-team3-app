# Current System Assessment — Module 8 (June 5–13)

Snapshot of the ALSDS Team 3 app as of June 5 2026, after UI/UX improvements in this branch.

## 1. Does comparison functionality exist?

**Yes — added in this iteration.** The result panel now exposes a "Save scenario for
comparison" button. Each saved run is rendered as a card in the new "Scenario Comparison"
panel ([static/chat.js](static/chat.js) `saveCurrentScenario` / `renderScenarios`).
The card with the highest predicted visits is auto-flagged as "Best".

Before this iteration: no comparison functionality existed — only one result was ever
visible at a time.

## 2. Can the chatbot rerun the model?

**Yes.** When a chat message contains a full input set (NAICS code or recognized
category label, latitude/longitude, and floor area), `extractRerunInputs` in
[static/chat.js](static/chat.js) parses it and calls `/api/run_huff` directly
without re-entering the guided flow. Example:

> "use 42.229212, -71.805525 and rerun the model for coffee shop with area 1000 m²"

The follow-up assistant in `/api/ask` is explicitly instructed **not** to claim it
reran the model when the inputs are incomplete; it asks for the missing fields instead
([app.py](app.py) `answer_question`).

## 3. Does the chatbot remember previous inputs?

**Yes — added in this iteration.**

- `state.history` in [static/chat.js](static/chat.js) keeps the user/assistant turn
  history and sends the last 10 turns with every `/api/ask` call.
- `state.last_inputs` and `state.scenarios` are also passed, so the LLM can reference
  the current inputs and every saved scenario when answering follow-ups.
- `answer_question` in [app.py](app.py) wires history into the OpenAI `messages`
  array and renders saved scenarios into the prompt so the assistant can compare them.

Before this iteration: each `/api/ask` call was stateless — only the current result
was sent, and the LLM had no memory of prior questions.

## 4. Is the map connected to Azure SQL?

**Partially.**

- The CBG polygon overlay on the Leaflet map is loaded from a **static GeoJSON file**
  shipped with the app (`/static/data/worcester_cbgs_map.geojson`, referenced in
  [static/map.js](static/map.js)). It is **not** read from Azure SQL.
- Competitor markers plotted on the map come from the Huff engine response, which
  **does** query Azure SQL via [db.py](db.py) `get_connection()` →
  [huff_engine.py](huff_engine.py). So the markers are Azure-backed even though the
  polygon basemap is not.
- Candidate-location selection is a pure client-side click handler; nothing is
  written back to Azure SQL.

**Recommendation for June 13–18:** if the team wants the map to be fully
Azure-backed, add a `/api/cbg_geojson` endpoint that streams polygon geometry from
the `worcester_cbgs` table (already migrated, see [migrate_to_azure_sql.py](migrate_to_azure_sql.py))
and have `map.js` fetch from that endpoint instead of the static file.

---

## Summary of UI improvements implemented (June 5–13)

| Improvement | Where | Status |
|---|---|---|
| Comparison panel + "Save scenario" button | [static/chat.js](static/chat.js), [templates/index.html](templates/index.html) | Done |
| Clearer result summary cards (predicted visits, market share, competitor count, runtime) | [static/chat.js](static/chat.js) `renderResult`, [static/styles.css](static/styles.css) `.stat-card` | Done |
| Competitor attraction chart (top-10 horizontal bar via Chart.js) | [static/chat.js](static/chat.js) `renderCompetitorChart` | Done |
| Business category → NAICS mapping (client + server) | [static/naics_map.js](static/naics_map.js), [app.py](app.py) `NAICS_CATEGORY_MAP` | Done |
| Chatbot follow-up memory (history + saved scenarios passed to LLM) | [static/chat.js](static/chat.js) `askQuestion`, [app.py](app.py) `answer_question` | Done |

## Remaining technical improvements (June 13–18)

- Stream CBG polygons from Azure SQL instead of the static GeoJSON file (see §4 above).
- Persist saved scenarios server-side so they survive a page reload.
- Add a dropdown of known business categories to remove guesswork from the free-text input.
- Add error-state cards (e.g. "no competitors found in radius") so the cards never go blank silently.
