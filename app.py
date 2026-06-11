import os
from flask import Flask, request, jsonify, render_template
from openai import AzureOpenAI

from db import test_connection

app = Flask(__name__)


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
    Return the authoritative list of NAICS codes that have calibrated
    alpha/beta parameters. The frontend uses this to render a dropdown so
    users can't pick uncalibrated categories.
    """
    return jsonify({
        "categories": CATEGORIES,
        "aliases": NAICS_CATEGORY_MAP,
    })


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

@app.route("/admin/migrate")
def admin_migrate():
    """
    Spawns the SQLite -> Azure SQL migration on a background thread so the
    request returns immediately (well under Gunicorn's 30s worker timeout
    and the Azure edge proxy timeout). Re-entry is rejected while a previous
    run is still active. Poll /admin/migrate/status for progress.
    """
    import threading
    from migrate_to_azure_sql import execute_migration_task, migration_status

    if migration_status["status"] == "running":
        return jsonify({
            "message": "A migration is already running.",
            "progress_url": "/admin/migrate/status",
            "current_status": migration_status,
        }), 202

    thread = threading.Thread(target=execute_migration_task, daemon=True)
    thread.start()

    return jsonify({
        "ok": True,
        "message": "Migration started. Poll /admin/migrate/status for progress.",
        "progress_url": "/admin/migrate/status",
    }), 202


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

        # Reject codes that aren't calibrated. Without this, the user gets a
        # generic 500 from the engine; with it, they get the list of codes
        # that actually work.
        calibrated_codes = {c["naics"] for c in CATEGORIES}
        if business_category not in calibrated_codes:
            return jsonify({
                "ok": False,
                "error": (
                    f"NAICS {business_category} is not in the calibrated dataset. "
                    "Pick one of the calibrated categories below."
                ),
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

        result = run_huff_model(
            candidate_lat=candidate_lat,
            candidate_lon=candidate_lon,
            business_category=business_category,
            floor_area=floor_area,
            db_connection=None  # Teams can replace this with Azure SQL usage
        )

        explanation = generate_explanation(result)

        return jsonify({
            "ok": True,
            "inputs": {
                "candidate_lat": candidate_lat,
                "candidate_lon": candidate_lon,
                "business_category": business_category,
                "floor_area": floor_area
            },
            "result": result,
            "explanation": explanation
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------
# Ask Follow-up Questions
# -------------------------

@app.route("/api/ask", methods=["POST"])
def api_ask():
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question")
        result = data.get("result")
        inputs = data.get("inputs") or {}
        history = data.get("history") or []
        scenarios = data.get("scenarios") or []

        if not question or not result:
            return jsonify({"ok": False, "error": "Missing question or result"}), 400

        answer = answer_question(question, result, inputs, history, scenarios)

        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
You are an expert in retail location analytics.

A Huff-style gravity model has been run with the following results:

Predicted visits: {result.get("predicted_visits")}
Market share: {result.get("market_share")}
Runtime (ms): {result.get("runtime_ms")}

Competitors (sample):
{safe_competitor_sample(result, 3)}

Explain clearly:
1. What the predicted visits and market share mean
2. What factors likely influenced the result
3. Keep it short and intuitive, about 3-5 sentences
"""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": "You explain retail analytics and Huff model results clearly for students."
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
        "You are a helpful data science assistant for a location analytics web app. "
        "You remember the user's previous questions and saved scenarios within this conversation "
        "and can reference them when answering follow-up questions.\n\n"
        "Rules:\n"
        "- Do not invent data; only use what is shown in the model result, inputs, and saved scenarios.\n"
        "- Do not claim that you reran the Huff model. The app reruns the model only when the user's "
        "  message contains a complete input set (NAICS code, latitude, longitude, floor area).\n"
        "- If the user asks to rerun with new inputs but the message is missing some, tell them which "
        "  inputs are still required.\n"
        "- When comparing saved scenarios, be explicit about which scenario is being referenced."
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
