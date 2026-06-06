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
# Routes
# -------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


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

        # Map plain-language categories ("coffee shop") to NAICS codes server-side
        # so non-JS callers (curl, tests) get the same behavior as the chatbot.
        if not business_category.isdigit():
            mapped = NAICS_CATEGORY_MAP.get(business_category.lower())
            if mapped:
                business_category = mapped
            else:
                return jsonify({
                    "ok": False,
                    "error": f"Unknown business category '{business_category}'. Provide a NAICS code or a known label."
                }), 400

        if candidate_lat < -90 or candidate_lat > 90:
            return jsonify({"ok": False, "error": "candidate_lat must be between -90 and 90."}), 400

        if candidate_lon < -180 or candidate_lon > 180:
            return jsonify({"ok": False, "error": "candidate_lon must be between -180 and 180."}), 400

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
# Business-category → NAICS map (server-side mirror of static/naics_map.js)
# -------------------------

NAICS_CATEGORY_MAP = {
    "supermarket": "4451", "grocery": "4451", "grocery store": "4451",
    "convenience store": "4452", "convenience": "4452",
    "gas station": "4471",
    "pharmacy": "4461", "drug store": "4461",
    "clothing": "4481", "clothing store": "4481", "apparel": "4481",
    "shoe store": "4482", "jewelry": "4483",
    "sporting goods": "4511",
    "book store": "4512", "bookstore": "4512",
    "department store": "4522",
    "electronics": "4431", "electronics store": "4431",
    "furniture": "4421", "furniture store": "4421",
    "home improvement": "4441", "hardware": "4441", "hardware store": "4441",
    "building materials": "4441",
    "florist": "4531", "office supplies": "4532", "pet store": "4539",
    "restaurant": "7225", "full service restaurant": "7225",
    "fast food": "7225", "coffee shop": "7225", "coffee": "7225",
    "cafe": "7225", "café": "7225",
    "bar": "7224", "pub": "7224",
    "bakery": "3118",
    "hotel": "7211", "motel": "7211",
    "gym": "7139", "fitness center": "7139",
    "salon": "8121", "hair salon": "8121", "barber": "8121", "barber shop": "8121",
    "dry cleaner": "8123", "laundry": "8123",
    "auto repair": "8111", "car wash": "8111",
    "bank": "5221",
    "movie theater": "5121", "cinema": "5121",
}


# -------------------------
# Run locally
# -------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
