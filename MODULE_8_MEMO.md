# Module 8 — UI Improvement Memo
**Team 3 — AI-Assisted Location Decision Support System (Worcester, MA)**

---

## 1. Current UI Diagnosis

The Module 7 baseline dashboard worked technically but failed several usability tests. Three concrete issues we identified before this iteration:

**Issue A — Input clarity (chatbot).** The category step accepted any digit string and any free-text label. Users typed plausible-sounding categories ("coffee shop", "gym", "pharmacy") and got back a red error — *No calibrated alpha/beta parameters found for NAICS code XXXX* — with no way to discover which categories actually work. The interface implied the model supported anything; the data backed only 23 calibrated NAICS codes.

**Issue B — Model output interpretation.** The single result was rendered as a wall of `key: value` text inside one box (`Predicted Visits: 1234`, `Market Share: 0.0731`, `Runtime: 42 ms`, `Notes: ...`). The Competitor table further showed *Distance = N/A* and *Attraction = N/A* on every row because the engine was returning `None` for both fields even though they had been computed internally. A user couldn't tell whether the model had failed silently or whether those values genuinely didn't exist.

**Issue C — Scenario comparison.** There was no way to compare two candidate sites. Running the model a second time overwrote the first result. The user had to remember the previous predicted-visits number, switch back to the map, run a new scenario, and mentally compare — exactly the cognitive load that decision support is supposed to remove.

Additional issues we addressed: map clicks after the first run were silently ignored, the chatbot couldn't remember earlier turns, and users were free to drop a pin in Boston (or anywhere on Earth) which then failed at the engine layer with a generic 500.

---

## 2. Design Principles Applied

**P1 — Recognition is easier than recall.** Users should not have to recall which of the 23 calibrated NAICS codes exist; the interface should show them. We added a dropdown of valid categories populated from `/api/categories`, and the welcome message names the input shape explicitly instead of leaving it to guesswork.

**P2 — Visual design should support comparison.** Decision support means weighing options against each other. The new "Scenario Comparison" panel renders each saved run as a card in a horizontal row with the same fields in the same positions, and the best-predicted-visits card is auto-flagged with a green badge so the eye lands on it first.

**P3 — Good UI reduces cognitive load (scan before read).** We replaced the dense `key: value` text block with four colored stat cards (Predicted Visits, Market Share, Competitor Count, Runtime). A user scanning the page sees the headline numbers in under a second; the table below is for users who want detail. The competitor chart (top-10 horizontal bars by attraction score) does the same job for the competitor breakdown.

**P4 — Trust requires clarity and explanation.** Errors now say *which* categories are calibrated and *which* coordinates fall inside Worcester, instead of failing with `No calibrated alpha/beta parameters found`. The Worcester service area is drawn as a green dashed rectangle on the map so the constraint is visible before the user picks a point.

---

## 3. UI Improvements Made

### Improvement 1 — Calibrated-category dropdown + plain-language aliases
- **Original issue:** Users typed labels like "coffee shop" or NAICS codes like 7225 and got a generic engine error. (Issue A above; documented in user screenshots.)
- **Design change:** New `/api/categories` endpoint returns the 23 calibrated codes plus a dictionary of plain-language aliases (`bakery → 311811`, `liquor store → 445310`, `dentist → 621210`, `hardware → 4441`, …). The chat panel renders these as a dropdown above the input. `/api/run_huff` now rejects uncalibrated codes server-side before hitting the engine, and the 400 response includes the `available` list so the UI can guide the user.
- **Why it improves decision support:** Users discover what they *can* analyze instead of guessing what the dataset supports. No more dead-end "red error" experiences.
- **Principle:** P1 (recognition over recall) and P4 (trust requires clarity).

### Improvement 2 — Stat cards, attraction chart, populated competitor table
- **Original issue:** Single result text blob; competitor distance and attraction always showed N/A. (Issue B.)
- **Design change:** Four colored stat cards summarize the headline numbers. The engine was fixed so `competitors[i].distance_miles` is computed from the candidate site via haversine (was hard-coded to `None`) and `competitors[i].attraction` is the per-POI Huff utility sum (was hard-coded to `None`). The top 20 nearest competitors — not the first 20 in DB order — are returned. A Chart.js horizontal bar chart renders the top 10 by attraction.
- **Why it improves decision support:** A user can now see at a glance which competitor is most directly threatening the proposed site, and how close it is. The data layer was always there — the UI just wasn't showing it.
- **Principle:** P3 (scan before read).

### Improvement 3 — Scenario comparison panel
- **Original issue:** No way to compare alternative locations or store sizes. (Issue C.)
- **Design change:** A "Save scenario for comparison" button captures the current inputs + result; a separate panel renders saved scenarios side-by-side in cards with consistent fields (NAICS, lat/lon, floor area, predicted visits, market share, competitors). The card with the highest predicted visits is highlighted as "Best". Saved scenarios are also forwarded into `/api/ask`'s prompt, so the chatbot can answer "why did scenario 2 beat scenario 1?" with grounded data.
- **Why it improves decision support:** Side-by-side comparison is the central use case for site selection. Mental comparison from memory is where small business owners make bad calls.
- **Principle:** P2 (visual design should support comparison).

### Bonus improvements
- **Worcester service-area gate.** `/api/bounds` exposes the bounding box, drawn on the map as a green dashed rectangle. Clicks outside the box are rejected client-side with a clear message; typed coordinates outside the box are rejected server-side with the actual bounds. (Principle P4.)
- **Partial input updates after a run.** Once the model has run, the user can click a new spot on the map, type just `bakery`, just `1500 sqm`, or just `42.27, -71.81` and the model reruns with the other inputs kept. Previously the chatbot locked into "follow-up question" mode and dropped every input change. (Principle P3 — lower cognitive load: don't make the user retype what hasn't changed.)
- **Chatbot memory.** `/api/ask` now receives the last 10 turns and all saved scenarios, so follow-up questions like "why is scenario 2 better" actually work. The system prompt also forbids the LLM from claiming it reran the model.
- **Test suite.** 40 automated tests cover input validation, calibrated-code parity with the CSV, alias correctness, Worcester bounds, and the chatbot-history pipeline. The CSV-vs-CATEGORIES parity test specifically prevents the original "label points to uncalibrated code" bug from regressing.

---

## 4. Before-and-After Evidence

User-captured screenshots in this branch (in order from the conversation log):

- **Before — uncalibrated NAICS:** User typed "dunkin", then `'gym'`, then `restaurant`. All resolved to NAICS the dataset doesn't have (7139, 7225). The chat ended in a red error: *No calibrated alpha/beta parameters found for NAICS code 7139.* No path forward visible.
- **After — calibrated NAICS:** Same screen shape, but the user now enters NAICS 4441 (Building Material). The model runs end-to-end:
  - Stat cards show *Predicted Visits 14.31*, *Market Share 1.80%*, *Competitors 20*, *Runtime 15,200 ms*.
  - Competitor Attraction bar chart shows Wallboard Supply Co., Abrasives & Tools, Plywood Plus, Worcester Scale, Lavigne's Carpet & Rugs ranked by attraction.
  - The chatbot's explanation references *Lavigne's Carpet & Rugs* by name — i.e. the LLM is grounded in the actual competitor data.
  - Post-run hint tells the user the four ways to iterate: ask a question, click the map, type a partial update, or click "Start over".
- **Map overlay:** the Worcester service-area bounding rectangle (added in this iteration) is now visible as a green dashed boundary; the proposed-store marker is inside it.

---

## 5. Reflection

**How does the improved interface help a non-technical user make a better location decision?**

The Module 7 dashboard left a non-technical user three ways to fail: (1) typing a category the dataset doesn't support, (2) picking a location outside Worcester's calibrated footprint, and (3) running a single scenario in isolation with no way to compare it against alternatives. Every one of those failure modes either produced a cryptic error or, worse, a number that looked authoritative but had no point of reference.

The redesigned interface removes those traps before the user can fall into them. The category dropdown replaces guesswork with a menu of options the model actually supports. The Worcester bounding box turns an invisible constraint into a visible one. The scenario comparison panel turns site selection from a "remember the previous number" task into a side-by-side card layout where the better option is literally highlighted. The stat cards and competitor chart let a user grasp the answer in two seconds without parsing a wall of `key: value` text, and the chatbot's memory of saved scenarios means follow-up questions like *"why is scenario 2 better?"* get grounded, comparative answers rather than generic platitudes.

The net result: an entrepreneur who has never heard of the Huff Gravity Model can pick a calibrated category, drop a pin inside the visible service area, see four headline numbers and a chart, save the scenario, try a second location, and read off which one wins — well under the three-minute UX target from Module 1.
