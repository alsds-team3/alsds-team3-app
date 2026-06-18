"""
Local dev launcher for the ALSDS Flask app.

Swaps Azure SQL for the bundled SQLite mirror at Data/team_3.db and stubs the
Azure OpenAI client with a deterministic placeholder. Run:

    python run_local.py

Then open http://localhost:8000.

NO Azure credentials, ODBC driver, or pyodbc install are required — the
production code paths are monkey-patched at import time.
"""

import os
import re
import sys
import sqlite3
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SQLITE_PATH = HERE / "Data" / "team_3.db"

if not SQLITE_PATH.exists():
    sys.exit(f"Missing local SQLite mirror at {SQLITE_PATH}")

# ---------------------------------------------------------------------------
# 1. Stub pyodbc BEFORE app.py / db.py import. They only need pyodbc.connect
#    and the Connection symbol; we never actually call the real driver.
# ---------------------------------------------------------------------------
sys.modules.setdefault(
    "pyodbc",
    types.SimpleNamespace(connect=lambda *a, **k: None, Connection=object),
)

# ---------------------------------------------------------------------------
# 2. Cursor / Connection adapter so SQLite quacks like the pyodbc cursor
#    surface the app uses (execute + positional params, TOP-N rewriting,
#    context-manager close).
# ---------------------------------------------------------------------------

_TOP_RX = re.compile(r"\s*SELECT\s+TOP\s+(\d+)\s+(.*)", re.IGNORECASE | re.DOTALL)


class _SqliteCursor:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, *params):
        # pyodbc lets callers pass either a tuple or positional varargs;
        # SQLite wants a single sequence.
        if len(params) == 1 and isinstance(params[0], (list, tuple)):
            params = tuple(params[0])
        # Rewrite "SELECT TOP N ..." to SQLite's LIMIT clause.
        m = _TOP_RX.match(sql)
        if m:
            sql = f"SELECT {m.group(2)} LIMIT {m.group(1)}"
        self._raw.execute(sql, params)
        return self

    def fetchall(self):
        return self._raw.fetchall()

    def fetchone(self):
        return self._raw.fetchone()


class _SqliteConn:
    def __init__(self, raw):
        self._raw = raw
        self._closed = False

    def cursor(self):
        return _SqliteCursor(self._raw.cursor())

    def close(self):
        if not self._closed:
            self._raw.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def _local_get_connection():
    return _SqliteConn(sqlite3.connect(str(SQLITE_PATH)))


# ---------------------------------------------------------------------------
# 3. Set placeholder env vars so the Azure OpenAI client constructor accepts
#    them at import time. Real calls are stubbed below.
# ---------------------------------------------------------------------------
os.environ.setdefault("AZURE_OPENAI_API_KEY", "local-stub")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://local.invalid")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "local-stub")
os.environ.setdefault("SQL_CONNECTION_STRING", "Driver={SQLite Stub};Database=local")

# ---------------------------------------------------------------------------
# 4. Import the app, then patch its DB + LLM hooks.
# ---------------------------------------------------------------------------
import db                                  # noqa: E402
db.get_connection = _local_get_connection  # type: ignore[assignment]
db.test_connection = lambda: True          # type: ignore[assignment]

import huff_engine                         # noqa: E402
huff_engine.get_connection = _local_get_connection  # type: ignore[assignment]

# pandas.read_sql trips on our adapter because it expects sqlite3.Connection
# or SQLAlchemy. Reach inside the adapter for the raw sqlite3 connection.
_orig_read_sql = huff_engine.pd.read_sql


def _patched_read_sql(sql, conn, params=None):
    if isinstance(conn, _SqliteConn):
        return _orig_read_sql(sql, conn._raw, params=params)
    return _orig_read_sql(sql, conn, params=params)


huff_engine.pd.read_sql = _patched_read_sql

import app                                 # noqa: E402

# Stub the LLM calls so the app doesn't try to hit Azure OpenAI.
app.generate_explanation = lambda result: (
    f"[LOCAL STUB] Predicted visits: {result.get('predicted_visits')}, "
    f"market share: {result.get('market_share')}. Parameter source: "
    f"{result.get('parameter_source','calibrated')}. "
    "(Run on Azure to get a real GPT explanation.)"
)
app.answer_question = lambda question, result, inputs=None, history=None, scenarios=None: (
    f"[LOCAL STUB] You asked: \"{question}\". "
    "GPT answers are disabled in local mode — deploy to Azure for live responses."
)

# Reset cached known-NAICS list so it pulls from SQLite on first request.
app._KNOWN_NAICS_CACHE = None


if __name__ == "__main__":
    print(f"=> SQLite source : {SQLITE_PATH}")
    print(f"=> Azure OpenAI  : stubbed (no API calls)")
    print(f"=> Open          : http://localhost:8000")
    app.app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=False)
