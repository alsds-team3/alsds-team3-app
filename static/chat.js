const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const saveScenarioBtn = document.getElementById("saveScenarioBtn");
const clearScenariosBtn = document.getElementById("clearScenariosBtn");

const state = {
  step: "category",
  business_category: null,
  business_category_label: null,
  candidate_lat: null,
  candidate_lon: null,
  floor_area: null,
  last_result: null,
  last_inputs: null,
  history: [],
  scenarios: []
};

let competitorChart = null;
let scenarioChart = null;
let CATEGORIES_LIST = [];

const inputCard = document.getElementById("inputCard");

addBotMessage(
  "Welcome. I will guide you through a store-location scenario for Worcester, MA. " +
  "Pick a category below, type a label like 'liquor store', or enter a calibrated NAICS code."
);

// -------------------------------------------------------------------------
// Adaptive input card — renders contextual pickers in the chat based on
// state.step so users can click instead of type for the structured inputs.
// -------------------------------------------------------------------------
function renderInputCard() {
  if (!inputCard) return;

  if (state.step === "category") {
    const cats = CATEGORIES_LIST.length ? CATEGORIES_LIST :
      (window.getCalibratedCategories ? window.getCalibratedCategories() : []);
    const popular = cats.slice(0, 8);
    const optionHtml = cats.map(c =>
      `<option value="${c.naics}">${escapeHtml(c.label)} (${c.naics})</option>`
    ).join("");

    inputCard.innerHTML = `
      <div class="card-head">Pick a business category</div>
      <div class="pick-row">
        <select class="pick-select" id="inlineCatSelect">
          <option value="">— all calibrated categories —</option>
          ${optionHtml}
        </select>
      </div>
      <div class="picker-chips">
        ${popular.map(c =>
          `<button type="button" class="pick-chip" data-naics="${c.naics}">
             ${escapeHtml(c.label)}<span class="code">${c.naics}</span>
           </button>`
        ).join("")}
      </div>
    `;
    const sel = document.getElementById("inlineCatSelect");
    sel.addEventListener("change", () => {
      if (sel.value) submitInline(sel.value);
    });
    inputCard.querySelectorAll(".pick-chip").forEach(btn => {
      btn.addEventListener("click", () => submitInline(btn.dataset.naics));
    });
    return;
  }

  if (state.step === "location") {
    inputCard.innerHTML = `
      <div class="card-head">Pick a candidate location</div>
      <div class="pick-row">
        <input class="pick-input" id="inlineCoord" type="text"
               placeholder="42.2671, -71.8003" autocomplete="off" />
        <button type="button" class="pick-action" id="inlineCoordGo">Use</button>
      </div>
      <div class="picker-chips">
        <span class="pick-chip" style="cursor:default;background:transparent;border:none;color:var(--on-surface-variant);">
          or click anywhere on the map →
        </span>
      </div>
    `;
    const inp = document.getElementById("inlineCoord");
    const go = document.getElementById("inlineCoordGo");
    const fire = () => { if (inp.value.trim()) submitInline(inp.value.trim()); };
    go.addEventListener("click", fire);
    inp.addEventListener("keydown", e => { if (e.key === "Enter") fire(); });
    return;
  }

  if (state.step === "floor_area") {
    const presets = [250, 500, 1000, 2000, 5000];
    inputCard.innerHTML = `
      <div class="card-head">Pick a floor area (m²)</div>
      <div class="pick-row">
        <input class="pick-input" id="inlineArea" type="number" min="1" step="1"
               placeholder="e.g. 1000" autocomplete="off" />
        <button type="button" class="pick-action" id="inlineAreaGo">Run</button>
      </div>
      <div class="picker-chips">
        ${presets.map(a =>
          `<button type="button" class="pick-chip" data-area="${a}">
             ${a.toLocaleString()} m²
           </button>`
        ).join("")}
      </div>
    `;
    const inp = document.getElementById("inlineArea");
    const go = document.getElementById("inlineAreaGo");
    const fire = () => { if (inp.value.trim()) submitInline(inp.value.trim()); };
    go.addEventListener("click", fire);
    inp.addEventListener("keydown", e => { if (e.key === "Enter") fire(); });
    inputCard.querySelectorAll(".pick-chip").forEach(btn => {
      btn.addEventListener("click", () => submitInline(btn.dataset.area));
    });
    return;
  }

  // step === "ready" — no structured input needed, hide the card.
  inputCard.innerHTML = "";
}

function submitInline(text) {
  chatInput.value = String(text);
  handleSend();
}

renderInputCard();

window.onCategoriesLoaded = function (cats) {
  CATEGORIES_LIST = Array.isArray(cats) ? cats : [];
  const sel = document.getElementById("categorySelect");
  if (sel && sel.dataset.populated !== "1") {
    sel.dataset.populated = "1";
    sel.innerHTML =
      '<option value="">— pick a calibrated category —</option>' +
      CATEGORIES_LIST.map(c =>
        `<option value="${c.naics}">${escapeHtml(c.label)} (${c.naics})</option>`
      ).join("");
  }
  renderInputCard();
};

const categorySelect = document.getElementById("categorySelect");
if (categorySelect) {
  categorySelect.addEventListener("change", () => {
    const code = categorySelect.value;
    if (!code) return;
    chatInput.value = code;
    handleSend();
    categorySelect.value = "";
  });
}

sendBtn.addEventListener("click", handleSend);
saveScenarioBtn.addEventListener("click", saveCurrentScenario);
clearScenariosBtn.addEventListener("click", clearScenarios);

const resetBtn = document.getElementById("resetBtn");
if (resetBtn) {
  resetBtn.addEventListener("click", () => {
    state.step = "category";
    renderInputCard();
    state.business_category = null;
    state.business_category_label = null;
    state.candidate_lat = null;
    state.candidate_lon = null;
    state.floor_area = null;
    state.last_result = null;
    state.last_inputs = null;
    state.history = [];
    saveScenarioBtn.disabled = true;
    addBotMessage(
      "Started over. Enter a business category (e.g. 'coffee shop') or a NAICS code to begin again."
    );
  });
}

chatInput.addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    handleSend();
  }
});

window.onMapLocationSelected = function (location) {
  state.candidate_lat = location.lat;
  state.candidate_lon = location.lon;

  if (state.step === "location") {
    addBotMessage(
      `Great, I captured the candidate location: ${location.lat.toFixed(6)}, ${location.lon.toFixed(6)}. ` +
      "Now enter the proposed store floor area in square meters."
    );
    state.step = "floor_area";
    renderInputCard();
    return;
  }

  // After a successful run, a fresh map click should be a real input change,
  // not silently ignored. Re-run with the same NAICS + area so the user can
  // explore alternative sites without re-typing everything.
  if (state.step === "ready" && state.business_category && state.floor_area) {
    addBotMessage(
      `New candidate location captured: ${location.lat.toFixed(6)}, ${location.lon.toFixed(6)}. ` +
      `Rerunning the model with NAICS ${state.business_category} and floor area ${state.floor_area} m².`
    );
    runModel().catch(err => addErrorMessage(err.message || String(err)));
  }
};

async function handleSend() {
  const text = chatInput.value.trim();
  if (!text) return;

  addUserMessage(text);
  chatInput.value = "";

  try {
    const rerunInputs = extractRerunInputs(text);

    if (rerunInputs) {
      if (window.isInWorcester &&
          !window.isInWorcester(rerunInputs.candidate_lat, rerunInputs.candidate_lon)) {
        addBotMessage(
          "I can only rerun the model for locations inside the Worcester service area. " +
          "Pick a point inside the green dashed box and try again."
        );
        return;
      }
      await rerunModelFromMessage(rerunInputs);
      return;
    }

    if (state.step === "category") {
      const resolved = window.resolveBusinessCategory(text);

      if (!resolved) {
        const cats = (window.getCalibratedCategories || (() => []))();
        const sample = cats.slice(0, 8).map(c => `${c.label} (${c.naics})`).join(", ");
        addBotMessage(
          "I can only run the model for categories that have calibrated " +
          "parameters in our dataset. Pick one from the dropdown, or try a label like: " +
          sample + (cats.length > 8 ? ", …" : "") + "."
        );
        return;
      }

      state.business_category = resolved;
      state.business_category_label = text;
      state.step = "location";
      renderInputCard();

      if (window.showCategoryPois) {
        window.showCategoryPois(resolved);
      }

      const wasMapped = !/^\d{2,6}$/.test(text.trim());
      addBotMessage(
        (wasMapped
          ? `I mapped "${text}" to NAICS ${resolved}. `
          : `Using NAICS ${resolved}. `) +
        "Now click the proposed store location on the map, or type coordinates as: 42.24, -71.78"
      );
      return;
    }

    if (state.step === "location") {
      const coords = parseCoordinates(text);

      if (!coords) {
        addBotMessage("Please click the map or type coordinates in this format: 42.24, -71.78");
        return;
      }

      if (window.isInWorcester && !window.isInWorcester(coords.lat, coords.lon)) {
        const b = window.getWorcesterBounds ? window.getWorcesterBounds() : null;
        addBotMessage(
          `That point is outside the Worcester service area${b
            ? ` (lat ${b.lat_min}–${b.lat_max}, lon ${b.lon_min}–${b.lon_max})`
            : ""}. Please pick a location inside the green dashed box on the map.`
        );
        return;
      }

      state.candidate_lat = coords.lat;
      state.candidate_lon = coords.lon;

      if (window.setCandidateLocation) {
        window.setCandidateLocation(coords.lat, coords.lon, false);
      }

      state.step = "floor_area";
      renderInputCard();
      addBotMessage("Great. Now enter the proposed store floor area in square meters.");
      return;
    }

    if (state.step === "floor_area") {
      const area = Number(text.replace(/,/g, ""));

      if (!Number.isFinite(area) || area <= 0) {
        addBotMessage("Please enter a positive numeric floor area, such as 1000.");
        return;
      }

      state.floor_area = area;
      state.step = "ready";
      renderInputCard();

      addBotMessage(
        `Thanks. I will run the Huff model for NAICS ${state.business_category}, ` +
        `location (${state.candidate_lat.toFixed(6)}, ${state.candidate_lon.toFixed(6)}), ` +
        `and floor area ${state.floor_area} square meters.`
      );

      await runModel();
      return;
    }

    if (state.step === "ready") {
      // Allow partial updates after the first run so users aren't forced to
      // retype every input. Anything we can confidently parse as a NAICS,
      // a coordinate pair, or a floor area updates that field and reruns.
      const update = parsePartialUpdate(text);
      if (update) {
        await applyPartialUpdate(update);
        return;
      }
      await askQuestion(text);
      return;
    }
  } catch (error) {
    addErrorMessage(error.message || String(error));
  }
}

async function rerunModelFromMessage(inputs) {
  state.business_category = inputs.business_category;
  state.candidate_lat = inputs.candidate_lat;
  state.candidate_lon = inputs.candidate_lon;
  state.floor_area = inputs.floor_area;
  state.step = "ready";
  renderInputCard();

  if (window.showCategoryPois) window.showCategoryPois(state.business_category);

  addBotMessage(
    `I found a new complete input set. Rerunning the Huff model for NAICS ${state.business_category}, ` +
    `location (${state.candidate_lat.toFixed(6)}, ${state.candidate_lon.toFixed(6)}), ` +
    `and floor area ${state.floor_area} square meters.`
  );

  if (window.setCandidateLocation) {
    window.setCandidateLocation(state.candidate_lat, state.candidate_lon, false);
  }

  await runModel();
}

async function runModel() {
  addBotMessage("Running the model now...");

  const response = await fetch("/api/run_huff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_lat: state.candidate_lat,
      candidate_lon: state.candidate_lon,
      business_category: state.business_category,
      floor_area: state.floor_area,
      naics_code: state.business_category,
      floor_area_sqm: state.floor_area
    })
  });

  const data = await response.json();

  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Model failed.");
  }

  state.last_result = data.result;
  state.last_inputs = {
    business_category: state.business_category,
    business_category_label: state.business_category_label,
    candidate_lat: state.candidate_lat,
    candidate_lon: state.candidate_lon,
    floor_area: state.floor_area
  };

  renderResult(data.result);
  renderCompetitorChart(data.result.competitors);

  if (window.plotCompetitors) {
    window.plotCompetitors(data.result.competitors);
  }

  saveScenarioBtn.disabled = false;

  let tierNote = "";
  if (data.naics_tier === "fallback") {
    tierNote =
      `⚠ NAICS ${state.business_category} is not calibrated. The engine used ` +
      "default parameters (α=1, β=2) — treat these numbers as a rough estimate.\n\n";
  }

  addBotMessage(
    tierNote +
    (data.explanation ? data.explanation + "\n\n" : "") +
    "You can now: (a) ask follow-up questions, (b) click a new spot on the map to rerun there, " +
    "(c) type 'use NAICS 5121', 'change category to gym', or '1500 sqm' to update just one input, " +
    "or (d) click \"Start over\" to reset."
  );
}

async function askQuestion(question) {
  if (!state.last_result) {
    addBotMessage("Please complete a model run first.");
    return;
  }

  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      result: state.last_result,
      inputs: state.last_inputs,
      history: state.history.slice(-10),
      scenarios: state.scenarios.map(s => ({
        inputs: s.inputs,
        predicted_visits: s.result.predicted_visits,
        market_share: s.result.market_share
      }))
    })
  });

  const data = await response.json();

  if (!response.ok || !data.ok) {
    throw new Error(data.error || "The assistant could not answer.");
  }

  state.history.push({ role: "user", content: question });
  state.history.push({ role: "assistant", content: data.answer });

  addBotMessage(data.answer);
}

function renderResult(result) {
  const cards = document.getElementById("resultCards");

  const predictedVisits = result.predicted_visits;
  const marketShare = Number(result.market_share);
  const runtime = result.runtime_ms;
  const competitorCount = Array.isArray(result.competitors) ? result.competitors.length : 0;
  const notes = result.notes ?? "";

  cards.classList.remove("empty");
  cards.innerHTML = `
    <div class="stat-card accent-amber">
      <div class="label">Competitors</div>
      <div class="value">${competitorCount}</div>
      <div class="sub">nearby in category</div>
    </div>
    <div class="stat-card accent-violet">
      <div class="label">Runtime</div>
      <div class="value">${formatNumber(runtime)}<span style="font-size:12px;font-weight:500;"> ms</span></div>
      <div class="sub">${escapeHtml(notes) || "model execution"}</div>
    </div>
  `;

  // Mirror the headline numbers into the bottom-left glass cards.
  const visitsEl = document.getElementById("visitsValue");
  const shareEl = document.getElementById("shareValue");
  if (visitsEl) visitsEl.textContent = formatNumber(predictedVisits);
  if (shareEl) {
    shareEl.textContent = Number.isFinite(marketShare)
      ? (marketShare * 100).toFixed(1) + "%"
      : "—";
  }

  // Visualize competitor attraction as a 6-bar sparkline in the visits card.
  const bars = document.querySelectorAll("#visitsBars span");
  if (bars.length) {
    const comps = Array.isArray(result.competitors) ? result.competitors : [];
    const attractions = comps
      .map(c => Number(c.attraction ?? 0))
      .filter(n => Number.isFinite(n));
    const sample = attractions.slice(0, 6);
    while (sample.length < 6) sample.push(0);
    const max = Math.max(...sample, 1);
    const peakIdx = sample.indexOf(Math.max(...sample));
    bars.forEach((b, i) => {
      const pct = Math.max(8, (sample[i] / max) * 100);
      b.style.height = pct + "%";
      b.classList.toggle("peak", i === peakIdx);
    });
  }

  const tableWrap = document.getElementById("competitorTable");
  const competitors = Array.isArray(result.competitors) ? result.competitors : [];

  if (competitors.length === 0) {
    tableWrap.innerHTML = "<div class='result-empty'>No competitor records returned.</div>";
    return;
  }

  tableWrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Distance</th>
          <th>Size</th>
          <th>Attraction</th>
        </tr>
      </thead>
      <tbody>
        ${competitors.map(c => `
          <tr>
            <td>${escapeHtml(c.name ?? c.place_name ?? c.poi_name ?? "Unknown")}</td>
            <td>${escapeHtml(c.distance_miles ?? c.distance ?? "N/A")}</td>
            <td>${escapeHtml(c.size ?? c.floor_area ?? c.area ?? "N/A")}</td>
            <td>${escapeHtml(c.attraction ?? "N/A")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderCompetitorChart(competitors) {
  const wrap = document.querySelector(".chart-wrap");
  const canvas = document.getElementById("competitorChart");

  if (!Array.isArray(competitors) || competitors.length === 0 || typeof Chart === "undefined") {
    wrap.classList.remove("has-data");
    if (competitorChart) {
      competitorChart.destroy();
      competitorChart = null;
    }
    return;
  }

  const top = [...competitors]
    .map(c => ({
      name: String(c.name ?? c.place_name ?? c.poi_name ?? "Unknown"),
      attraction: Number(c.attraction ?? 0)
    }))
    .filter(c => Number.isFinite(c.attraction))
    .sort((a, b) => b.attraction - a.attraction)
    .slice(0, 10);

  if (top.length === 0) {
    wrap.classList.remove("has-data");
    if (competitorChart) { competitorChart.destroy(); competitorChart = null; }
    return;
  }

  wrap.classList.add("has-data");

  const cfg = {
    type: "bar",
    data: {
      labels: top.map(t => t.name.length > 22 ? t.name.slice(0, 20) + "…" : t.name),
      datasets: [{
        label: "Attraction",
        data: top.map(t => t.attraction),
        backgroundColor: "#2563eb"
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true } }
    }
  };

  if (competitorChart) {
    competitorChart.data = cfg.data;
    competitorChart.update();
  } else {
    competitorChart = new Chart(canvas.getContext("2d"), cfg);
  }
}

function saveCurrentScenario() {
  if (!state.last_result || !state.last_inputs) return;

  state.scenarios.push({
    id: Date.now(),
    inputs: { ...state.last_inputs },
    result: state.last_result
  });

  renderScenarios();
  addBotMessage(`Saved scenario #${state.scenarios.length}. Run another to compare side-by-side.`);
}

function clearScenarios() {
  state.scenarios = [];
  renderScenarios();
}

function renderScenarios() {
  const wrap = document.getElementById("comparisonContent");
  clearScenariosBtn.disabled = state.scenarios.length === 0;

  if (state.scenarios.length === 0) {
    wrap.innerHTML = `<div class="result-empty">
      Saved scenarios appear here side-by-side. Run the model and click "Save scenario" to compare alternatives.
    </div>`;
    return;
  }

  let bestIdx = 0;
  let bestVisits = -Infinity;
  state.scenarios.forEach((s, i) => {
    const v = Number(s.result.predicted_visits);
    if (Number.isFinite(v) && v > bestVisits) {
      bestVisits = v;
      bestIdx = i;
    }
  });

  const cards = state.scenarios.map((s, i) => {
    const v = Number(s.result.predicted_visits);
    const ms = Number(s.result.market_share);
    const isBest = i === bestIdx && state.scenarios.length > 1;
    return `
      <div class="scenario-card ${isBest ? "best" : ""}">
        <button class="remove" data-id="${s.id}" title="Remove">&times;</button>
        ${isBest ? '<span class="badge">Best predicted visits</span>' : ""}
        <h4>Scenario #${i + 1}</h4>
        <div class="row"><span class="k">NAICS</span><span class="v">${escapeHtml(s.inputs.business_category)}</span></div>
        <div class="row"><span class="k">Lat, Lon</span><span class="v">${s.inputs.candidate_lat.toFixed(4)}, ${s.inputs.candidate_lon.toFixed(4)}</span></div>
        <div class="row"><span class="k">Floor area</span><span class="v">${formatNumber(s.inputs.floor_area)} m²</span></div>
        <div class="row"><span class="k">Visits</span><span class="v">${formatNumber(v)}</span></div>
        <div class="row"><span class="k">Market share</span><span class="v">${Number.isFinite(ms) ? (ms * 100).toFixed(2) + "%" : "N/A"}</span></div>
        <div class="row"><span class="k">Competitors</span><span class="v">${Array.isArray(s.result.competitors) ? s.result.competitors.length : 0}</span></div>
      </div>
    `;
  }).join("");

  wrap.innerHTML = `<div class="comparison-grid">${cards}</div>`;

  wrap.querySelectorAll(".remove").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = Number(btn.getAttribute("data-id"));
      state.scenarios = state.scenarios.filter(s => s.id !== id);
      renderScenarios();
    });
  });

  renderScenarioChart();
}

function renderScenarioChart() {
  const chartWrap = document.getElementById("scenarioChartWrap");
  const canvas = document.getElementById("scenarioChart");
  if (!chartWrap || !canvas || typeof Chart === "undefined") return;

  if (state.scenarios.length < 2) {
    chartWrap.style.display = "none";
    if (scenarioChart) { scenarioChart.destroy(); scenarioChart = null; }
    return;
  }

  chartWrap.style.display = "block";

  const labels = state.scenarios.map((_, i) => `Scenario ${i + 1}`);
  const visits = state.scenarios.map(s => Number(s.result.predicted_visits) || 0);
  const share = state.scenarios.map(s => {
    const ms = Number(s.result.market_share);
    return Number.isFinite(ms) ? ms * 100 : 0;
  });

  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Predicted Visits",
          data: visits,
          backgroundColor: "#2563eb",
          yAxisID: "yVisits"
        },
        {
          label: "Market Share (%)",
          data: share,
          backgroundColor: "#16a34a",
          yAxisID: "yShare"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        yVisits: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          title: { display: true, text: "Visits" }
        },
        yShare: {
          type: "linear",
          position: "right",
          beginAtZero: true,
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Share (%)" }
        }
      }
    }
  };

  if (scenarioChart) {
    scenarioChart.data = cfg.data;
    scenarioChart.update();
  } else {
    scenarioChart = new Chart(canvas.getContext("2d"), cfg);
  }
}

// -------------------------------------------------------------------
// Partial-update parser
//
// After a successful run, users want to tweak ONE input at a time
// ("change naics to 5121", "use 1500 sqm", "42.27, -71.81") without
// re-typing everything. We detect single-field updates and rerun
// the model keeping the other current state values.
// -------------------------------------------------------------------
function parsePartialUpdate(message) {
  const update = {};

  // 1. Coordinates anywhere in the message.
  const coords = parseCoordinates(message);
  if (coords) {
    update.candidate_lat = coords.lat;
    update.candidate_lon = coords.lon;
  }

  // 2. Floor area — only match when the unit/keyword is explicit, so a
  // bare number (which might be a NAICS) doesn't get misread as an area.
  const areaMatch =
    message.match(/(?:floor\s+)?area\s*(?:of|is|=|:|to)?\s*([\d,]+(?:\.\d+)?)/i) ||
    message.match(/([\d,]+(?:\.\d+)?)\s*(?:square\s+meters|square\s+metres|sqm|sq\.?\s*m|m2|m²)/i);
  if (areaMatch) {
    const area = Number(areaMatch[1].replace(/,/g, ""));
    if (Number.isFinite(area) && area > 0) update.floor_area = area;
  }

  // 3. NAICS — explicit keyword, OR a known plain-language category,
  // OR a bare 2-6 digit number (only if no area was already matched
  // from the same number).
  const naicsExplicit =
    message.match(/naics(?:\s+code)?\s*(?:is|=|:|of|for|to)?\s*(\d{2,6})/i) ||
    message.match(/(?:business\s+)?category\s*(?:is|=|:|of|for|to)?\s*(\d{2,6})/i);
  if (naicsExplicit) {
    update.business_category = naicsExplicit[1];
  } else if (window.resolveBusinessCategory) {
    const resolved = window.resolveBusinessCategory(message);
    if (resolved) update.business_category = resolved;
  }
  if (!update.business_category) {
    // Bare digit string like "5121" with nothing else.
    const bare = message.trim().match(/^(\d{2,6})$/);
    if (bare && update.floor_area === undefined) {
      update.business_category = bare[1];
    }
  }

  return Object.keys(update).length > 0 ? update : null;
}

async function applyPartialUpdate(update) {
  const changes = [];

  if (update.business_category && update.business_category !== state.business_category) {
    state.business_category = update.business_category;
    changes.push(`NAICS → ${update.business_category}`);
    if (window.showCategoryPois) window.showCategoryPois(update.business_category);
  }

  if (update.candidate_lat !== undefined && update.candidate_lon !== undefined) {
    if (window.isInWorcester && !window.isInWorcester(update.candidate_lat, update.candidate_lon)) {
      addBotMessage(
        "That location is outside the Worcester service area. " +
        "Pick a point inside the green dashed box on the map."
      );
      return;
    }
    if (update.candidate_lat !== state.candidate_lat ||
        update.candidate_lon !== state.candidate_lon) {
      state.candidate_lat = update.candidate_lat;
      state.candidate_lon = update.candidate_lon;
      if (window.setCandidateLocation) {
        window.setCandidateLocation(state.candidate_lat, state.candidate_lon, false);
      }
      changes.push(`location → ${update.candidate_lat.toFixed(4)}, ${update.candidate_lon.toFixed(4)}`);
    }
  }

  if (update.floor_area && update.floor_area !== state.floor_area) {
    state.floor_area = update.floor_area;
    changes.push(`floor area → ${update.floor_area} m²`);
  }

  if (changes.length === 0) {
    addBotMessage("Nothing changed — those values match the current inputs.");
    return;
  }

  addBotMessage(`Updated ${changes.join(", ")}. Rerunning the model now.`);
  await runModel();
}

function extractRerunInputs(message) {
  const coords = parseCoordinates(message);
  if (!coords) return null;

  let businessCategory = null;
  const naicsMatch =
    message.match(/naics(?:\s+code)?\s*(?:is|=|:|of|for)?\s*(\d{2,6})/i) ||
    message.match(/business\s+category\s*(?:is|=|:|of|for)?\s*(\d{2,6})/i) ||
    message.match(/category\s*(?:is|=|:|of|for)?\s*(\d{2,6})/i);

  if (naicsMatch) {
    businessCategory = naicsMatch[1];
  } else if (window.resolveBusinessCategory) {
    // try keyword resolution from the message
    businessCategory = window.resolveBusinessCategory(message);
  }

  const areaMatch =
    message.match(/area\s*(?:of|is|=|:)?\s*([\d,]+(?:\.\d+)?)/i) ||
    message.match(/floor\s+area\s*(?:of|is|=|:)?\s*([\d,]+(?:\.\d+)?)/i) ||
    message.match(/([\d,]+(?:\.\d+)?)\s*(?:square\s+meters|square\s+metres|sqm|sq\.?\s*m|m2|m²)/i);

  if (!businessCategory || !areaMatch) return null;

  const floorArea = Number(areaMatch[1].replace(/,/g, ""));
  if (!Number.isFinite(floorArea) || floorArea <= 0) return null;

  return {
    business_category: businessCategory,
    candidate_lat: coords.lat,
    candidate_lon: coords.lon,
    floor_area: floorArea
  };
}

function parseCoordinates(text) {
  const match = text.match(/(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)/);
  if (!match) return null;

  const lat = Number(match[1]);
  const lon = Number(match[2]);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;

  return { lat, lon };
}

function formatNumber(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return escapeHtml(value ?? "N/A");
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function addBotMessage(text) { addMessage(text, "bot"); }
function addUserMessage(text) { addMessage(text, "user"); }
function addErrorMessage(text) { addMessage(text, "error"); }

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = `message ${type}`;
  div.innerText = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
