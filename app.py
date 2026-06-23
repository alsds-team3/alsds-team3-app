import os
import re
import logging
import traceback
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template
from openai import AzureOpenAI

from db import test_connection

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app.logger.setLevel(logging.INFO)

# Last unsanitised error, surfaced via /api/debug/last_error for diagnosis
# without needing to scroll Azure Log Stream.
_LAST_ERROR = {"ts": None, "endpoint": None, "error": None, "traceback": None}


def _record_error(endpoint, exc):
    _LAST_ERROR["ts"] = datetime.now(timezone.utc).isoformat()
    _LAST_ERROR["endpoint"] = endpoint
    _LAST_ERROR["error"] = f"{type(exc).__name__}: {exc}"
    _LAST_ERROR["traceback"] = traceback.format_exc()
    app.logger.exception("Error in %s", endpoint)


# -------------------------
# Azure OpenAI Setup
# -------------------------

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")


# -------------------------
# Geographic bounds — Worcester, MA
# -------------------------
# Padded bounding box covering the City of Worcester plus the immediate
# surrounding towns served by the calibrated CBG dataset. The Huff model is
# only meaningful inside this footprint, so candidate locations outside it
# are rejected by /api/run_huff with a clear error.
WORCESTER_BOUNDS = {
    "lat_min": 42.18,
    "lat_max": 42.36,
    "lon_min": -71.92,
    "lon_max": -71.68,
}


def is_in_worcester(lat, lon):
    return (
        WORCESTER_BOUNDS["lat_min"] <= lat <= WORCESTER_BOUNDS["lat_max"]
        and WORCESTER_BOUNDS["lon_min"] <= lon <= WORCESTER_BOUNDS["lon_max"]
    )


# -------------------------
# Routes
# -------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    """Inline SVG favicon — azure diamond matching the in-app brand mark."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="8" fill="#101418"/>'
        '<path d="M16 5l11 11-11 11L5 16z" fill="none" stroke="#a1c9ff" '
        'stroke-width="2.5" stroke-linejoin="round"/>'
        '</svg>'
    )
    return svg, 200, {"Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=86400"}


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/bounds")
def api_bounds():
    """Worcester service-area bounding box; consumed by the frontend."""
    return jsonify(WORCESTER_BOUNDS)


@app.route("/api/categories")
def api_categories():
    """
    Three NAICS tiers (per Mohsen's Module 9 guidance):
      - calibrated: 23 codes with measured alpha/beta in the parameters table.
      - known:      ~130 codes present in worchester_businesses; uncalibrated
                    runs use fallback alpha=1, beta=2.
      - aliases:    plain-language label -> NAICS code map.

    The frontend uses `calibrated` for "trusted" picker chips and `known` to
    permit fallback runs while still rejecting NAICS codes that have zero
    historical records in our dataset.
    """
    return jsonify({
        "categories": CATEGORIES,                # tier 1 — calibrated
        "known_naics": _known_naics_list(),      # tier 1 + tier 2
        "aliases": NAICS_CATEGORY_MAP,
    })


# In-process cache of the ~130 NAICS codes that exist in worchester_businesses.
# Populated on first hit, refreshed only on process restart.
_KNOWN_NAICS_CACHE = None


def _known_naics_list():
    """Return the deduped sorted list of NAICS codes present in POI data."""
    global _KNOWN_NAICS_CACHE
    if _KNOWN_NAICS_CACHE is not None:
        return _KNOWN_NAICS_CACHE

    from db import get_connection
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT naics_code FROM worchester_businesses "
                "WHERE naics_code IS NOT NULL"
            )
            codes = sorted({str(r[0]) for r in cur.fetchall() if r[0] is not None})
        _KNOWN_NAICS_CACHE = codes
        return codes
    except Exception:
        # If Azure SQL is unreachable, fall back to the calibrated 23 so the
        # UI still works — callers will see strict-mode behavior.
        return [c["naics"] for c in CATEGORIES]


@app.route("/api/cbgs")
def api_cbgs():
    """
    CBG centroids from Azure SQL. Replaces the static GeoJSON fetch for the
    demand-point overlay; the frontend draws a small dot per CBG so users
    can see the demand grid the Huff model sums over.
    """
    from db import get_connection
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT cbg_id, centroid_lat, centroid_lon FROM cbgs "
                "WHERE centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL"
            )
            rows = cur.fetchall()
        cbgs = [
            {"cbg_id": str(r[0]), "lat": float(r[1]), "lon": float(r[2])}
            for r in rows
        ]
        return jsonify({"ok": True, "cbgs": cbgs, "count": len(cbgs)})
    except Exception as exc:
        _record_error("/api/cbgs", exc)
        return jsonify({"ok": False, "error": _sanitize_exception(exc)}), 500


@app.route("/api/pois")
def api_pois():
    """
    POIs (existing competitors) for a given NAICS code, from Azure SQL.
    Filters to Worcester bounds and caps at 500 to keep the response small.
    The frontend uses this to show what competitive landscape the user is
    walking into BEFORE they run the model.
    """
    from db import get_connection

    naics = (request.args.get("naics") or "").strip()
    if not naics:
        return jsonify({"ok": False, "error": "Missing required query param: naics"}), 400

    # naics_code is BIGINT in Azure SQL (the migration maps SQLite INTEGER -> BIGINT).
    # Pass an int so we don't rely on implicit varchar->bigint conversion.
    try:
        naics_param = int(naics)
    except ValueError:
        return jsonify({"ok": False, "error": f"Invalid NAICS code '{naics}'."}), 400

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT TOP 500 placekey, location_name, latitude, longitude, "
                "wkt_area_sq_meters, naics_code "
                "FROM worchester_businesses "
                "WHERE naics_code = ? "
                "  AND latitude BETWEEN ? AND ? "
                "  AND longitude BETWEEN ? AND ?",
                naics_param,
                WORCESTER_BOUNDS["lat_min"], WORCESTER_BOUNDS["lat_max"],
                WORCESTER_BOUNDS["lon_min"], WORCESTER_BOUNDS["lon_max"],
            )
            rows = cur.fetchall()
        pois = [
            {
                "placekey": str(r[0]) if r[0] is not None else None,
                "name": str(r[1]) if r[1] is not None else "Unknown",
                "lat": float(r[2]),
                "lon": float(r[3]),
                "area_sqm": float(r[4]) if r[4] is not None else None,
                "naics_code": str(r[5]) if r[5] is not None else naics,
            }
            for r in rows
            if r[2] is not None and r[3] is not None
        ]
        return jsonify({"ok": True, "naics": naics, "pois": pois, "count": len(pois)})
    except Exception as exc:
        _record_error("/api/pois", exc)
        return jsonify({"ok": False, "error": _sanitize_exception(exc)}), 500


@app.route("/dbcheck")
def dbcheck():
    try:
        ok = test_connection()
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------
# Module 7 — Migration & verification endpoints
# -------------------------

# @app.route("/admin/migrate")
# def admin_migrate():
#     """
#     Spawns the SQLite -> Azure SQL migration on a background thread so the
#     request returns immediately (well under Gunicorn's 30s worker timeout
#     and the Azure edge proxy timeout). Re-entry is rejected while a previous
#     run is still active. Poll /admin/migrate/status for progress.
#     """
#     import threading
#     from migrate_to_azure_sql import execute_migration_task, migration_status

#     if migration_status["status"] == "running":
#         return jsonify({
#             "message": "A migration is already running.",
#             "progress_url": "/admin/migrate/status",
#             "current_status": migration_status,
#         }), 202

#     thread = threading.Thread(target=execute_migration_task, daemon=True)
#     thread.start()

#     return jsonify({
#         "ok": True,
#         "message": "Migration started. Poll /admin/migrate/status for progress.",
#         "progress_url": "/admin/migrate/status",
#     }), 202


@app.route("/admin/migrate/status")
def admin_migrate_status():
    """Read-only view of the live migration_status dict updated by the worker."""
    from migrate_to_azure_sql import migration_status
    return jsonify(migration_status)


@app.route("/db_structure")
def db_structure():
    """
    Lists base tables in Azure SQL with their row counts. Used to verify the
    migration parity against the local SQLite database after /admin/migrate
    completes.
    """
    from db import get_connection

    query = """
        SELECT
            t.name AS table_name,
            SUM(p.rows) AS row_count
        FROM sys.tables t
        INNER JOIN sys.partitions p
            ON p.object_id = t.object_id
        WHERE t.is_ms_shipped = 0
          AND p.index_id IN (0, 1)
        GROUP BY t.name
        ORDER BY t.name;
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
        return jsonify([
            {"TABLE_NAME": str(r[0]), "row_count": int(r[1] or 0)}
            for r in rows
        ])
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# -------------------------
# Run Huff Model
# -------------------------

@app.route("/api/run_huff", methods=["POST"])
def api_run_huff():
    try:
        from huff_engine import run_huff_model

        data = request.get_json(silent=True) or {}

        candidate_lat = get_first_present(data, ["candidate_lat", "lat", "latitude"])
        candidate_lon = get_first_present(data, ["candidate_lon", "lon", "lng", "longitude"])
        business_category = get_first_present(data, ["business_category", "naics_code", "naics"])
        floor_area = get_first_present(data, ["floor_area", "floor_area_sqm", "area", "area_sqm"])

        missing = []
        if candidate_lat is None:
            missing.append("candidate_lat")
        if candidate_lon is None:
            missing.append("candidate_lon")
        if business_category is None:
            missing.append("business_category or naics_code")
        if floor_area is None:
            missing.append("floor_area or floor_area_sqm")

        if missing:
            return jsonify({
                "ok": False,
                "error": "Missing required inputs: " + ", ".join(missing)
            }), 400

        try:
            candidate_lat = float(candidate_lat)
            candidate_lon = float(candidate_lon)
            floor_area = float(floor_area)
            business_category = str(business_category).strip()
        except Exception:
            return jsonify({
                "ok": False,
                "error": "Invalid input type. Latitude, longitude, and floor area must be numeric. NAICS/business category must be provided."
            }), 400

        if not business_category:
            return jsonify({"ok": False, "error": "Business category / NAICS code cannot be empty."}), 400

        # Map plain-language categories ("liquor store") to NAICS codes
        # server-side so non-JS callers (curl, tests) get the same behavior
        # as the chatbot.
        if not business_category.isdigit():
            mapped = NAICS_CATEGORY_MAP.get(business_category.lower())
            if mapped:
                business_category = mapped
            else:
                return jsonify({
                    "ok": False,
                    "error": (
                        f"Unknown business category '{business_category}'. "
                        "Provide a NAICS code or pick from the calibrated list "
                        "(see /api/categories)."
                    ),
                    "available": CATEGORIES,
                }), 400

        # 3-tier NAICS check (per Mohsen's Module 9 guidance):
        #   tier 1 (calibrated)   -> engine uses parameters table
        #   tier 2 (known POIs)   -> engine falls back to alpha=1, beta=2
        #   tier 3 (unknown)      -> reject with the historical-records message
        calibrated_codes = {c["naics"] for c in CATEGORIES}
        known_codes = set(_known_naics_list())

        if business_category in calibrated_codes:
            naics_tier = "calibrated"
        elif business_category in known_codes:
            naics_tier = "fallback"
        else:
            return jsonify({
                "ok": False,
                "error": (
                    f"There are no historical records for NAICS {business_category} "
                    "in our Worcester dataset, so the model can't produce any "
                    "results for this business category."
                ),
                "tier": "unknown",
                "available": CATEGORIES,
            }), 400

        if candidate_lat < -90 or candidate_lat > 90:
            return jsonify({"ok": False, "error": "candidate_lat must be between -90 and 90."}), 400

        if candidate_lon < -180 or candidate_lon > 180:
            return jsonify({"ok": False, "error": "candidate_lon must be between -180 and 180."}), 400

        if not is_in_worcester(candidate_lat, candidate_lon):
            return jsonify({
                "ok": False,
                "error": (
                    "Candidate location is outside the Worcester, MA service area. "
                    f"Latitude must be in [{WORCESTER_BOUNDS['lat_min']}, {WORCESTER_BOUNDS['lat_max']}] "
                    f"and longitude in [{WORCESTER_BOUNDS['lon_min']}, {WORCESTER_BOUNDS['lon_max']}]."
                ),
                "bounds": WORCESTER_BOUNDS,
            }), 400

        if floor_area <= 0:
            return jsonify({"ok": False, "error": "floor_area must be greater than zero."}), 400

        try:
            result = run_huff_model(
                candidate_lat=candidate_lat,
                candidate_lon=candidate_lon,
                business_category=business_category,
                floor_area=floor_area,
                db_connection=None
            )
        except ValueError as ve:
            # The engine raises ValueError when a known-tier NAICS has no
            # usable POI/visit data after joining. Convert to the same
            # historical-records message the user would have seen for tier 3.
            return jsonify({
                "ok": False,
                "error": (
                    f"There are no historical records for NAICS {business_category} "
                    "in our Worcester dataset, so the model can't produce any "
                    "results for this business category."
                ),
                "tier": "unknown",
                "detail": str(ve),
            }), 400

        result["naics_tier"] = naics_tier
        explanation = generate_explanation(result)

        return jsonify({
            "ok": True,
            "inputs": {
                "candidate_lat": candidate_lat,
                "candidate_lon": candidate_lon,
                "business_category": business_category,
                "floor_area": floor_area
            },
            "naics_tier": naics_tier,
            "result": result,
            "explanation": explanation
        })

    except Exception as e:
        _record_error("/api/run_huff", e)
        return jsonify({"ok": False, "error": _sanitize_exception(e)}), 500


# -------------------------
# Ask Follow-up Questions
# -------------------------

@app.route("/api/ask", methods=["POST"])
def api_ask():
    try:
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        result = data.get("result")
        inputs = data.get("inputs") or {}
        history = data.get("history") or []
        scenarios = data.get("scenarios") or []

        if not question or not result:
            return jsonify({"ok": False, "error": "Missing question or result"}), 400

        # Length cap — client also caps at 500, this is the server-side floor.
        if len(question) > 1000:
            question = question[:1000]

        # Cheap jailbreak / off-topic guard. Real defense is the system prompt,
        # but we short-circuit obvious attempts before they reach the LLM.
        if _looks_unsafe(question):
            return jsonify({
                "ok": True,
                "answer": (
                    "I can only help with Worcester store-location decisions — running "
                    "the Huff model, comparing sites, interpreting competitors. "
                    "What location would you like to analyze next?"
                ),
            })

        answer = answer_question(question, result, inputs, history, scenarios)
        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        _record_error("/api/ask", e)
        return jsonify({"ok": False, "error": _sanitize_exception(e)}), 500


@app.route("/api/debug/last_error")
def api_debug_last_error():
    """Returns the most recent unsanitised server error. Use this when the UI
    shows a generic 'database backend unavailable' message and you need the
    underlying pyodbc / OpenAI / driver detail to diagnose it."""
    return jsonify(_LAST_ERROR)


# Patterns we treat as obvious off-topic or jailbreak attempts.
_UNSAFE_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts?|rules?)", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"disregard\s+(your|all)\s+(instructions|rules)", re.I),
    re.compile(r"jailbreak|dan\s+mode|developer\s+mode", re.I),
    re.compile(r"<\s*script|javascript:|onerror\s*=", re.I),
]


def _looks_unsafe(text: str) -> bool:
    return any(rx.search(text) for rx in _UNSAFE_PATTERNS)


def _sanitize_exception(exc) -> str:
    """Strip backend internals (pyodbc class names, SQL state codes) from the
    user-facing error string. Keeps logs untouched."""
    raw = str(exc)
    low = raw.lower()
    if "pyodbc" in low or "odbc" in low or "sql server" in low:
        return "The database backend is temporarily unavailable. Please try again."
    if "openai" in low or "api key" in low or "deployment" in low:
        return "The AI explanation service is temporarily unavailable."
    if len(raw) > 200 or "<class" in raw or "traceback" in low:
        return "Something went wrong on the server. Please try again."
    return raw


# -------------------------
# Helper Functions
# -------------------------

def get_first_present(data, keys):
    """
    Returns the first value found in a dictionary from a list of possible keys.
    This lets the frontend send either:
      business_category / floor_area
    or:
      naics_code / floor_area_sqm
    """
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return None


def safe_competitor_sample(result, n=3):
    competitors = result.get("competitors", [])

    if not isinstance(competitors, list):
        return []

    return competitors[:n]


# -------------------------
# LLM Functions
# -------------------------

def generate_explanation(result):
    prompt = f"""
A location model has just produced these results for a proposed Worcester store:

Predicted visits: {result.get("predicted_visits")}
Market share: {result.get("market_share")}
Runtime (ms): {result.get("runtime_ms")}

Competitors (sample):
{safe_competitor_sample(result, 3)}

In 3-4 short sentences, plain language only (no jargon, no academic phrasing):
1. State the predicted visits and market share in one sentence.
2. Say in plain terms why this site likely scored that way (e.g. nearby competitors, distance to demand).
3. Mention one important limitation (the model ignores rent, parking, visibility, zoning, demographics).
"""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a decision-support assistant for a Worcester store-location tool. "
                    "Write in plain, practical language a small business owner would use. "
                    "No academic phrasing, no 'spatial interaction dynamics' or 'distance-decay parameters'. "
                    "Be brief and useful."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.4
    )

    return response.choices[0].message.content


def answer_question(question, result, inputs=None, history=None, scenarios=None):
    inputs = inputs or {}
    history = history or []
    scenarios = scenarios or []

    scenarios_block = ""
    if scenarios:
        lines = []
        for i, s in enumerate(scenarios, start=1):
            si = s.get("inputs", {}) or {}
            lines.append(
                f"  Scenario {i}: NAICS={si.get('business_category')}, "
                f"lat={si.get('candidate_lat')}, lon={si.get('candidate_lon')}, "
                f"area={si.get('floor_area')} m², "
                f"visits={s.get('predicted_visits')}, share={s.get('market_share')}"
            )
        scenarios_block = "Previously saved scenarios for comparison:\n" + "\n".join(lines) + "\n\n"

    system_prompt = (
        "You are the assistant for a Worcester, MA store-location decision-support tool. "
        "Your job is to help a non-technical user evaluate candidate business locations using "
        "the Huff model results, map, and saved scenarios shown in the app.\n\n"
        "Tone:\n"
        "- Plain, practical language. No academic phrasing, no 'spatial interaction dynamics', "
        "  no 'distance-decay'. Talk like a helpful analyst, not a textbook.\n"
        "- Short answers. Get to the point in a few sentences.\n"
        "- When comparing scenarios, lead with the recommendation and the one or two metrics "
        "  that drove it.\n\n"
        "Rules:\n"
        "- Never invent data. Only use values shown in the model result, inputs, and saved scenarios.\n"
        "- Never claim you reran the model. The app reruns the model only when the user gives a "
        "  complete input set (NAICS, latitude, longitude, floor area). If inputs are missing, "
        "  ask for the specific missing ones.\n"
        "- When referencing a saved scenario, name it explicitly (e.g. 'Scenario 2').\n"
        "- Always note key limitations once per answer (the model ignores rent, parking, "
        "  visibility, zoning, and demographics) when giving a recommendation.\n\n"
        "Out of scope — politely refuse and redirect:\n"
        "- General homework, essays, coding help unrelated to this tool, personal advice, "
        "  politics, entertainment, medical or legal advice, or anything not about Worcester "
        "  store-location decisions. Example refusal: 'I can only help with Worcester "
        "  store-location decisions in this tool — running scenarios, comparing sites, "
        "  understanding competitors. Want to try a different location?'"
    )

    context_prompt = (
        f"Current model inputs:\n{inputs}\n\n"
        f"Current model result:\n{result}\n\n"
        f"{scenarios_block}"
        f"User question:\n{question}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-10:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": context_prompt})

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=messages,
        temperature=0.5
    )

    return response.choices[0].message.content


# -------------------------
# Business-category → NAICS map
#
# IMPORTANT: every entry below maps to one of the 23 NAICS codes that have
# calibrated alpha/beta parameters in Azure SQL (parameters table, sourced
# from calibrated_parameters_filtered.csv). Adding labels that point to
# UNcalibrated codes produces "No calibrated alpha/beta parameters found
# for NAICS code XXXX" at runtime — see CATEGORIES below for the authoritative
# list shown to users.
# -------------------------

# Authoritative list of calibrated categories (NAICS code -> display label).
# Returned by /api/categories and used to populate the dropdown in the UI.
CATEGORIES = [
    {"naics": "4441",   "label": "Building Material & Supplies Dealers"},
    {"naics": "311811", "label": "Bakeries"},
    {"naics": "3399",   "label": "Other Miscellaneous Manufacturing"},
    {"naics": "447110", "label": "Gasoline Stations"},
    {"naics": "621210", "label": "Offices of Dentists"},
    {"naics": "522310", "label": "Mortgage & Credit Intermediation"},
    {"naics": "922110", "label": "Justice, Public Order, and Safety"},
    {"naics": "453991", "label": "Other Miscellaneous Retailers"},
    {"naics": "441310", "label": "Auto Parts, Accessories & Tire Stores"},
    {"naics": "445310", "label": "Beer, Wine & Liquor Stores"},
    {"naics": "452319", "label": "General Merchandise / Warehouse Clubs"},
    {"naics": "531120", "label": "Lessors of Real Estate"},
    {"naics": "522110", "label": "Banks / Depository Credit Intermediation"},
    {"naics": "611310", "label": "Colleges & Universities"},
    {"naics": "531210", "label": "Real Estate Agents & Brokers"},
    {"naics": "523930", "label": "Financial Investment Activities"},
    {"naics": "517312", "label": "Telecommunications Carriers"},
    {"naics": "621511", "label": "Medical & Diagnostic Laboratories"},
    {"naics": "6214",   "label": "Outpatient Care Centers"},
    {"naics": "812910", "label": "Pet Care & Other Personal Services"},
    {"naics": "448310", "label": "Jewelry, Luggage & Leather Goods"},
    {"naics": "512240", "label": "Sound Recording Studios"},
    {"naics": "524113", "label": "Insurance Carriers"},
]

# Plain-language aliases users might type — all of these resolve to a
# calibrated NAICS code. Keep this in sync with static/naics_map.js.
NAICS_CATEGORY_MAP = {
    # 4441 Building Material & Supplies
    "hardware": "4441", "hardware store": "4441",
    "home improvement": "4441", "building materials": "4441",
    "lumber": "4441", "lumber yard": "4441",
    # 311811 Bakeries
    "bakery": "311811", "bakeries": "311811", "bread shop": "311811",
    # 3399 Other Miscellaneous Manufacturing
    "miscellaneous manufacturing": "3399", "manufacturing": "3399",
    # 447110 Gasoline Stations
    "gas station": "447110", "gas": "447110", "fuel station": "447110",
    "petrol station": "447110",
    # 621210 Offices of Dentists
    "dentist": "621210", "dental office": "621210", "dental clinic": "621210",
    # 522310 Mortgage / Credit Intermediation
    "mortgage": "522310", "mortgage broker": "522310",
    "credit intermediation": "522310", "loan office": "522310",
    # 922110 Justice / Public Order
    "courthouse": "922110", "court": "922110", "public safety": "922110",
    # 453991 Other Miscellaneous Retailers
    "miscellaneous retail": "453991", "gift shop": "453991", "tobacco shop": "453991",
    # 441310 Auto parts
    "auto parts": "441310", "tire store": "441310", "tires": "441310",
    "car parts": "441310", "automotive parts": "441310",
    # 445310 Beer, Wine & Liquor
    "liquor store": "445310", "liquor": "445310", "wine store": "445310",
    "wine shop": "445310", "beer store": "445310",
    # 452319 General Merchandise / Warehouse Club
    "warehouse club": "452319", "supercenter": "452319",
    "general merchandise": "452319", "department store": "452319",
    # 531120 Lessors of Real Estate
    "lessor": "531120", "property leasing": "531120", "rental property": "531120",
    # 522110 Banks
    "bank": "522110", "credit union": "522110", "depository": "522110",
    # 611310 Colleges & Universities
    "college": "611310", "university": "611310", "campus": "611310",
    # 531210 Real Estate Agents
    "real estate agent": "531210", "real estate broker": "531210",
    "realtor": "531210", "real estate office": "531210",
    # 523930 Financial Investment
    "investment firm": "523930", "wealth management": "523930",
    "financial advisor": "523930", "investment advisor": "523930",
    # 517312 Telecoms
    "telecom": "517312", "wireless carrier": "517312", "phone carrier": "517312",
    "cellular store": "517312",
    # 621511 Medical Labs
    "medical lab": "621511", "diagnostic lab": "621511", "lab": "621511",
    "blood lab": "621511",
    # 6214 Outpatient Care
    "outpatient": "6214", "outpatient clinic": "6214", "urgent care": "6214",
    "clinic": "6214",
    # 812910 Pet care / personal services
    "pet care": "812910", "pet grooming": "812910", "pet services": "812910",
    "personal services": "812910",
    # 448310 Jewelry / luggage / leather
    "jewelry": "448310", "jewelry store": "448310",
    "luggage": "448310", "leather goods": "448310",
    # 512240 Sound Recording
    "recording studio": "512240", "sound studio": "512240", "music studio": "512240",
    # 524113 Insurance Carriers
    "insurance": "524113", "insurance agency": "524113",
    "insurance carrier": "524113",
}


# -------------------------
# Run locally
# -------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
