"""
Robust test suite for the ALSDS Team 3 app.

Covers:
- Endpoint smoke (/, /health)
- /api/run_huff input validation (missing fields, bad types, out-of-range,
  empty category, non-positive area, plain-language category mapping)
- /api/ask validation and end-to-end with history + scenarios
- Server-side NAICS_CATEGORY_MAP coverage and parity with static/naics_map.js
- Helper functions (get_first_present, safe_competitor_sample)
- Engine error propagation through the route

Run with:    python -m unittest -v test_app.py
"""

import os
import re
import sys
import json
import types
import unittest
from unittest.mock import patch, MagicMock

# Provide dummy Azure creds BEFORE importing app so AzureOpenAI(...) doesn't
# refuse to construct on import.
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-deployment")

# ---- Stub external dependencies so the suite runs hermetically -------------
# The app's runtime needs `openai` and `pyodbc`, but the test suite mocks the
# OpenAI client and the DB engine, so the real packages aren't required.
if "openai" not in sys.modules:
    fake_openai = types.ModuleType("openai")
    fake_openai.AzureOpenAI = lambda **kwargs: MagicMock(name="AzureOpenAIClient")
    sys.modules["openai"] = fake_openai

if "pyodbc" not in sys.modules:
    fake_pyodbc = types.ModuleType("pyodbc")
    fake_pyodbc.Connection = object
    fake_pyodbc.connect = lambda *a, **k: MagicMock(name="PyodbcConnection")
    sys.modules["pyodbc"] = fake_pyodbc

# huff_engine imports numpy/pandas at module level; if those aren't present
# we replace it with a stub that exposes run_huff_model for patching.
try:
    import huff_engine  # noqa: F401
except Exception:
    fake_engine = types.ModuleType("huff_engine")
    fake_engine.run_huff_model = lambda **kwargs: {}
    sys.modules["huff_engine"] = fake_engine

import app as app_module  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_completion(text):
    """Build a fake OpenAI response object with .choices[0].message.content."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


SAMPLE_RESULT = {
    "predicted_visits": 1234.5,
    "market_share": 0.0731,
    "runtime_ms": 42.0,
    "notes": "Model V4 — Azure SQL",
    "competitors": [
        {"name": "Comp A", "lat": 42.27, "lon": -71.80,
         "size": 800, "attraction": 0.91, "distance_miles": 0.4},
        {"name": "Comp B", "lat": 42.25, "lon": -71.79,
         "size": 1200, "attraction": 0.55, "distance_miles": 0.9},
    ],
    "inputs": {
        "candidate_lat": 42.26, "candidate_lon": -71.80,
        "business_category": "4441", "floor_area": 1000.0,
    },
}


# ---------------------------------------------------------------------------
# Fixture: Flask test client
# ---------------------------------------------------------------------------

class BaseAppTest(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

class TestSmoke(BaseAppTest):
    def test_index_renders(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"AI-Assisted Location Decision Support System", r.data)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok"})

    def test_static_naics_map_present(self):
        r = self.client.get("/static/naics_map.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"NAICS_MAP", r.data)


# ---------------------------------------------------------------------------
# Helper-function tests (no Flask needed)
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):
    def test_get_first_present_returns_first_match(self):
        d = {"a": None, "b": 2, "c": 3}
        self.assertEqual(app_module.get_first_present(d, ["a", "b", "c"]), 2)

    def test_get_first_present_returns_none_when_missing(self):
        self.assertIsNone(app_module.get_first_present({}, ["x", "y"]))

    def test_get_first_present_treats_zero_as_present(self):
        # 0 is a meaningful value; only None should be skipped.
        self.assertEqual(app_module.get_first_present({"x": 0}, ["x"]), 0)

    def test_safe_competitor_sample_limits(self):
        comps = [{"i": i} for i in range(10)]
        self.assertEqual(
            len(app_module.safe_competitor_sample({"competitors": comps}, n=3)),
            3,
        )

    def test_safe_competitor_sample_handles_non_list(self):
        self.assertEqual(
            app_module.safe_competitor_sample({"competitors": None}),
            [],
        )

    def test_safe_competitor_sample_handles_missing(self):
        self.assertEqual(app_module.safe_competitor_sample({}), [])


# ---------------------------------------------------------------------------
# NAICS map tests
# ---------------------------------------------------------------------------

class TestNaicsMap(unittest.TestCase):
    def test_known_labels_have_naics(self):
        for label in ["coffee shop", "grocery", "pharmacy", "gym", "restaurant"]:
            self.assertIn(label, app_module.NAICS_CATEGORY_MAP, label)
            self.assertTrue(
                app_module.NAICS_CATEGORY_MAP[label].isdigit(),
                f"NAICS for {label!r} must be digits",
            )

    def test_values_are_two_to_six_digit_strings(self):
        for label, code in app_module.NAICS_CATEGORY_MAP.items():
            self.assertRegex(code, r"^\d{2,6}$", f"{label} -> {code}")

    def test_server_map_parity_with_client_js(self):
        """
        Every key that exists in BOTH static/naics_map.js and app.py must map
        to the same NAICS code in both files. This stops the client and server
        from silently drifting apart.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        js_path = os.path.join(here, "static", "naics_map.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Extract "key": "code" pairs inside NAICS_MAP = { ... }
        block_match = re.search(r"NAICS_MAP\s*=\s*\{(.+?)\};", js, re.DOTALL)
        self.assertIsNotNone(block_match, "Could not locate NAICS_MAP literal")
        block = block_match.group(1)

        pairs = re.findall(r'"([^"]+)"\s*:\s*"(\d{2,6})"', block)
        js_map = dict(pairs)
        self.assertGreater(len(js_map), 10, "JS NAICS_MAP looks too small")

        mismatches = []
        for key, py_code in app_module.NAICS_CATEGORY_MAP.items():
            if key in js_map and js_map[key] != py_code:
                mismatches.append((key, py_code, js_map[key]))
        self.assertEqual(mismatches, [], f"NAICS mismatches: {mismatches}")


# ---------------------------------------------------------------------------
# /api/run_huff input-validation tests (no DB / engine needed)
# ---------------------------------------------------------------------------

class TestRunHuffValidation(BaseAppTest):
    def post(self, body):
        return self.client.post(
            "/api/run_huff",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_missing_all_fields(self):
        r = self.post({})
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertFalse(data["ok"])
        self.assertIn("Missing required inputs", data["error"])

    def test_missing_one_field(self):
        r = self.post({
            "candidate_lat": 42.26,
            "candidate_lon": -71.80,
            "business_category": "4441",
            # floor_area missing
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("floor_area", r.get_json()["error"])

    def test_non_numeric_lat(self):
        r = self.post({
            "candidate_lat": "north",
            "candidate_lon": -71.80,
            "business_category": "4441",
            "floor_area": 1000,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("Invalid input type", r.get_json()["error"])

    def test_lat_out_of_range(self):
        r = self.post({
            "candidate_lat": 999,
            "candidate_lon": -71.80,
            "business_category": "4441",
            "floor_area": 1000,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("candidate_lat", r.get_json()["error"])

    def test_lon_out_of_range(self):
        r = self.post({
            "candidate_lat": 42.26,
            "candidate_lon": -999,
            "business_category": "4441",
            "floor_area": 1000,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("candidate_lon", r.get_json()["error"])

    def test_valid_lat_lon_outside_worcester_rejected(self):
        # Boston (valid Earth coords, but not Worcester) must be rejected.
        r = self.post({
            "candidate_lat": 42.3601,
            "candidate_lon": -71.0589,
            "business_category": "4441",
            "floor_area": 1000,
        })
        self.assertEqual(r.status_code, 400)
        body = r.get_json()
        self.assertIn("Worcester", body["error"])
        self.assertIn("bounds", body)
        self.assertEqual(set(body["bounds"].keys()),
                         {"lat_min", "lat_max", "lon_min", "lon_max"})

    def test_zero_floor_area(self):
        r = self.post({
            "candidate_lat": 42.26,
            "candidate_lon": -71.80,
            "business_category": "4441",
            "floor_area": 0,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("floor_area", r.get_json()["error"])

    def test_negative_floor_area(self):
        r = self.post({
            "candidate_lat": 42.26,
            "candidate_lon": -71.80,
            "business_category": "4441",
            "floor_area": -50,
        })
        self.assertEqual(r.status_code, 400)

    def test_empty_business_category(self):
        r = self.post({
            "candidate_lat": 42.26,
            "candidate_lon": -71.80,
            "business_category": "   ",
            "floor_area": 1000,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("Business category", r.get_json()["error"])

    def test_unknown_label_rejected(self):
        r = self.post({
            "candidate_lat": 42.26,
            "candidate_lon": -71.80,
            "business_category": "unicorn emporium",
            "floor_area": 1000,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("Unknown business category", r.get_json()["error"])

    def test_aliases_accepted(self):
        """Backend should accept either naics_code/floor_area_sqm or
        business_category/floor_area."""
        with patch.object(app_module, "run_huff_model_imported", create=True):
            pass  # not used; we patch the engine module below.

        with patch("huff_engine.run_huff_model", return_value=SAMPLE_RESULT) as engine, \
             patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")

            r = self.post({
                "lat": 42.26, "lng": -71.80,
                "naics_code": "4441", "area_sqm": 1000,
            })
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertTrue(r.get_json()["ok"])
            engine.assert_called_once()
            _, kwargs = engine.call_args
            self.assertEqual(kwargs["business_category"], "4441")
            self.assertEqual(kwargs["floor_area"], 1000.0)


# ---------------------------------------------------------------------------
# /api/run_huff end-to-end with mocked engine + OpenAI
# ---------------------------------------------------------------------------

class TestRunHuffSuccess(BaseAppTest):
    def test_successful_run_returns_result_and_explanation(self):
        with patch("huff_engine.run_huff_model", return_value=SAMPLE_RESULT), \
             patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion(
                "Predicted visits of 1234 is moderate; share ~7%."
            )

            r = self.client.post(
                "/api/run_huff",
                json={
                    "candidate_lat": 42.26, "candidate_lon": -71.80,
                    "business_category": "4441", "floor_area": 1000,
                },
            )
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertTrue(body["ok"])
            self.assertEqual(body["result"]["predicted_visits"], 1234.5)
            self.assertIn("Predicted visits", body["explanation"])
            self.assertEqual(body["inputs"]["business_category"], "4441")

    def test_plain_language_category_resolved_server_side(self):
        with patch("huff_engine.run_huff_model", return_value=SAMPLE_RESULT) as engine, \
             patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")

            r = self.client.post(
                "/api/run_huff",
                json={
                    "candidate_lat": 42.26, "candidate_lon": -71.80,
                    "business_category": "Coffee Shop",
                    "floor_area": 1000,
                },
            )
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            _, kwargs = engine.call_args
            self.assertEqual(kwargs["business_category"], "7225")

    def test_engine_error_returns_500(self):
        with patch(
            "huff_engine.run_huff_model",
            side_effect=ValueError("No calibrated alpha/beta for NAICS 9999."),
        ):
            r = self.client.post(
                "/api/run_huff",
                json={
                    "candidate_lat": 42.26, "candidate_lon": -71.80,
                    "business_category": "9999", "floor_area": 1000,
                },
            )
            self.assertEqual(r.status_code, 500)
            self.assertIn("No calibrated", r.get_json()["error"])

    def test_worcester_bounds_inclusive(self):
        """Every corner and the center of the Worcester bounding box must be
        accepted, so the service area is genuinely inclusive of the whole city."""
        b = app_module.WORCESTER_BOUNDS
        corners = [
            (b["lat_min"], b["lon_min"]),
            (b["lat_min"], b["lon_max"]),
            (b["lat_max"], b["lon_min"]),
            (b["lat_max"], b["lon_max"]),
            ((b["lat_min"] + b["lat_max"]) / 2, (b["lon_min"] + b["lon_max"]) / 2),
        ]
        with patch("huff_engine.run_huff_model", return_value=SAMPLE_RESULT), \
             patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")
            for lat, lon in corners:
                r = self.client.post(
                    "/api/run_huff",
                    json={
                        "candidate_lat": lat, "candidate_lon": lon,
                        "business_category": "4441", "floor_area": 1,
                    },
                )
                self.assertEqual(r.status_code, 200, f"corner lat={lat},lon={lon}")

    def test_just_outside_worcester_rejected(self):
        """Coords one tick beyond each edge must be rejected."""
        b = app_module.WORCESTER_BOUNDS
        eps = 0.01
        outside = [
            (b["lat_min"] - eps, (b["lon_min"] + b["lon_max"]) / 2),
            (b["lat_max"] + eps, (b["lon_min"] + b["lon_max"]) / 2),
            ((b["lat_min"] + b["lat_max"]) / 2, b["lon_min"] - eps),
            ((b["lat_min"] + b["lat_max"]) / 2, b["lon_max"] + eps),
        ]
        for lat, lon in outside:
            r = self.client.post(
                "/api/run_huff",
                json={
                    "candidate_lat": lat, "candidate_lon": lon,
                    "business_category": "4441", "floor_area": 1,
                },
            )
            self.assertEqual(r.status_code, 400, f"should reject lat={lat},lon={lon}")
            self.assertIn("Worcester", r.get_json()["error"])

    def test_bounds_endpoint(self):
        r = self.client.get("/api/bounds")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(
            set(body.keys()),
            {"lat_min", "lat_max", "lon_min", "lon_max"},
        )
        # sanity: contains the Worcester city center (~42.26, -71.80)
        self.assertTrue(
            body["lat_min"] <= 42.2626 <= body["lat_max"]
            and body["lon_min"] <= -71.8023 <= body["lon_max"]
        )


# ---------------------------------------------------------------------------
# /api/ask tests
# ---------------------------------------------------------------------------

class TestAsk(BaseAppTest):
    def test_missing_question(self):
        r = self.client.post("/api/ask", json={"result": SAMPLE_RESULT})
        self.assertEqual(r.status_code, 400)

    def test_missing_result(self):
        r = self.client.post("/api/ask", json={"question": "why?"})
        self.assertEqual(r.status_code, 400)

    def test_answer_returned(self):
        with patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion(
                "Because Scenario 2 has more floor area."
            )
            r = self.client.post("/api/ask", json={
                "question": "Why is scenario 2 better?",
                "result": SAMPLE_RESULT,
                "inputs": SAMPLE_RESULT["inputs"],
                "history": [
                    {"role": "user", "content": "What does market share mean?"},
                    {"role": "assistant", "content": "It's the modeled fraction of visits."},
                ],
                "scenarios": [
                    {"inputs": {"business_category": "4441",
                                "candidate_lat": 42.26, "candidate_lon": -71.80,
                                "floor_area": 800},
                     "predicted_visits": 900, "market_share": 0.05},
                    {"inputs": {"business_category": "4441",
                                "candidate_lat": 42.27, "candidate_lon": -71.81,
                                "floor_area": 1500},
                     "predicted_visits": 1600, "market_share": 0.09},
                ],
            })
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["ok"])
            self.assertIn("Scenario 2", r.get_json()["answer"])

            # Verify history + scenarios actually reached the LLM call
            args, kwargs = oai.chat.completions.create.call_args
            messages = kwargs["messages"]
            roles = [m["role"] for m in messages]
            self.assertEqual(roles[0], "system")
            # the two history turns must be present in order
            self.assertIn("user", roles[1:])
            self.assertIn("assistant", roles[1:])
            self.assertIn("Scenario 1", messages[-1]["content"])
            self.assertIn("Scenario 2", messages[-1]["content"])

    def test_history_truncated_to_last_10(self):
        big_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
            for i in range(40)
        ]
        with patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")
            self.client.post("/api/ask", json={
                "question": "follow up",
                "result": SAMPLE_RESULT,
                "history": big_history,
            })
            _, kwargs = oai.chat.completions.create.call_args
            messages = kwargs["messages"]
            # 1 system + up to 10 history + 1 final user
            self.assertLessEqual(len(messages), 12)
            self.assertGreaterEqual(len(messages), 2)

    def test_bad_role_in_history_filtered(self):
        with patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")
            self.client.post("/api/ask", json={
                "question": "q",
                "result": SAMPLE_RESULT,
                "history": [{"role": "system", "content": "hijack"}],
            })
            _, kwargs = oai.chat.completions.create.call_args
            messages = kwargs["messages"]
            # only one system message (ours) — the injected one is filtered out
            self.assertEqual(sum(1 for m in messages if m["role"] == "system"), 1)


# ---------------------------------------------------------------------------
# Direct test of answer_question (no HTTP roundtrip)
# ---------------------------------------------------------------------------

class TestAnswerQuestion(unittest.TestCase):
    def test_no_scenarios_block_when_empty(self):
        with patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")
            app_module.answer_question("q", SAMPLE_RESULT, inputs={}, history=[], scenarios=[])
            _, kwargs = oai.chat.completions.create.call_args
            final = kwargs["messages"][-1]["content"]
            self.assertNotIn("Previously saved scenarios", final)

    def test_scenarios_block_when_provided(self):
        with patch.object(app_module, "client") as oai:
            oai.chat.completions.create.return_value = make_fake_completion("ok")
            app_module.answer_question(
                "q", SAMPLE_RESULT,
                inputs={},
                history=[],
                scenarios=[{
                    "inputs": {"business_category": "4441",
                               "candidate_lat": 1, "candidate_lon": 2,
                               "floor_area": 500},
                    "predicted_visits": 100, "market_share": 0.01,
                }],
            )
            _, kwargs = oai.chat.completions.create.call_args
            final = kwargs["messages"][-1]["content"]
            self.assertIn("Previously saved scenarios", final)
            self.assertIn("Scenario 1", final)


if __name__ == "__main__":
    unittest.main(verbosity=2)
