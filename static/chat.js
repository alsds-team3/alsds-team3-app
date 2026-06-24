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

const quickChips = document.getElementById("quickChips");

addBotMessage(
  "Welcome. I will guide you through a store-location scenario for Worcester, MA. " +
  "Pick a category below, type a label like 'liquor store', or enter a calibrated NAICS code."
);

// -------------------------------------------------------------------------
// One smart input + a single state-aware chip row. Placeholder + chips
// change with state.step so the user always sees the next-best action.
// -------------------------------------------------------------------------
const PLACEHOLDERS = {
  category: "Type a category, NAICS code, or pick a chip…",
  location: "Type 42.26, -71.80 — or click anywhere on the map",
  floor_area: "Enter floor area in m² (e.g. 1000)",
  ready: "Ask about site feasibility, compare scenarios…",
};

const POPULAR_CATS = ["4441", "311811", "445310", "447110"]; // hardware, bakery, liquor, gas
const LOCATION_PRESETS = [
  { label: "Downtown",  lat: 42.2626, lon: -71.8023 },
  { label: "Tatnuck",   lat: 42.2735, lon: -71.8330 },
  { label: "Lincoln St",lat: 42.2900, lon: -71.8050 },
];
const AREA_PRESETS = [500, 1000, 2500];

function renderQuickChips() {
  if (!quickChips) return;
  chatInput.placeholder = PLACEHOLDERS[state.step] || PLACEHOLDERS.ready;
  chatInput.type = state.step === "floor_area" ? "number" : "text";

  if (state.step === "category") {
    const cats = (CATEGORIES_LIST.length
      ? CATEGORIES_LIST
      : (window.getCalibratedCategories ? window.getCalibratedCategories() : []));
    const popularChips = POPULAR_CATS
      .map(code => cats.find(c => c.naics === code))
      .filter(Boolean);
    quickChips.innerHTML =
      popularChips.map(c =>
        `<button type="button" data-send="${c.naics}">${escapeHtml(c.label)}</button>`
      ).join("") +
      `<button type="button" class="more" id="chipBrowseAll">▾ Browse all (${cats.length})</button>`;

    document.getElementById("chipBrowseAll").addEventListener("click", () => {
      const sel = document.getElementById("categorySelect");
      if (!sel) return;
      const code = window.prompt(
        "Pick a NAICS code:\n\n" +
        cats.map((c, i) => `${i + 1}. ${c.label} (${c.naics})`).join("\n") +
        "\n\nType the number or paste a NAICS code:"
      );
      if (!code) return;
      const trimmed = code.trim();
      const idx = Number(trimmed);
      const picked = Number.isInteger(idx) && idx >= 1 && idx <= cats.length
        ? cats[idx - 1].naics
        : trimmed;
      submitChip(picked);
    });
  } else if (state.step === "location") {
    quickChips.innerHTML = LOCATION_PRESETS.map(p =>
      `<button type="button" data-send="${p.lat}, ${p.lon}">${escapeHtml(p.label)}</button>`
    ).join("");
  } else if (state.step === "floor_area") {
    quickChips.innerHTML = AREA_PRESETS.map(a =>
      `<button type="button" data-send="${a}">${a.toLocaleString()} m²</button>`
    ).join("");
  } else {
    // ready — follow-up actions only
    quickChips.innerHTML = `
      <button type="button" data-send="Compare the saved scenarios">Compare</button>
      <button type="button" data-send="What are the main competitors?">Competitors</button>
      <button type="button" data-send="What are the limitations of this result?">Limitations</button>
    `;
  }

  quickChips.querySelectorAll("button[data-send]").forEach(btn => {
    btn.addEventListener("click", () => submitChip(btn.dataset.send));
  });
}

function submitChip(text) {
  chatInput.value = String(text);
  handleSend();
}

// -------------------------------------------------------------------------
// Smalltalk + safety helpers — kept tiny on purpose. We don't try to be a
// general chatbot; we just keep the DSS focused.
// -------------------------------------------------------------------------
const GREETINGS = /^(hi|hii|hey|hello|howdy|yo|hola|namaste|good\s+(morning|afternoon|evening|day))[.! ]*$/i;
const THANKS    = /^(thanks?|thank\s+you|thx|ty|cheers|appreciate(\s+it)?)[.! ]*$/i;
const FAREWELL  = /^(bye|goodbye|see\s+ya|see\s+you|later|gn|gtg)[.! ]*$/i;
const HELP_RX   = /^(help|what\s+can\s+you\s+do|how\s+does\s+this\s+work|what\s+is\s+this)\??$/i;

function handleSmalltalk(text) {
  if (GREETINGS.test(text)) {
    return "Hi! I'm your Worcester store-location advisor. Pick a calibrated " +
           "business category below to get started, or click anywhere on the map " +
           "to drop a candidate pin.";
  }
  if (THANKS.test(text)) {
    return "You're welcome. Want to compare another location, or try a different category?";
  }
  if (FAREWELL.test(text)) {
    return "Take care. Click \"Start over\" any time to run a new scenario.";
  }
  if (HELP_RX.test(text)) {
    return "I help evaluate retail/business sites in Worcester. Three quick steps: " +
           "1) pick a category, 2) drop a pin on the map, 3) enter floor area in m². " +
           "After the model runs, you can compare scenarios or ask follow-up questions.";
  }
  return null;
}

// Cheap prompt-injection / off-topic filter. Catches obvious jailbreak
// patterns; real defense is the system prompt on the server.
const UNSAFE_PATTERNS = [
  /ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts?|rules?)/i,
  /system\s+prompt/i,
  /disregard\s+(your|all)\s+(instructions|rules)/i,
  /act\s+as\s+(?!a\s+(store|location|business|retail))/i,
  /jailbreak|dan\s+mode|developer\s+mode/i,
  /<\s*script|javascript:|onerror\s*=/i,
];

function looksUnsafe(text) {
  if (text.length > 500) return true;
  return UNSAFE_PATTERNS.some(rx => rx.test(text));
}

// Off-topic detector. Catches questions that are clearly not about location
// decisions — recipes, weather, code help, trivia, etc. — so we can refuse
// politely instead of falling through to a step-specific parse error.
const OFF_TOPIC_PATTERNS = [
  /\b(recipe|cook|bake|ingredients?|how to make)\b/i,
  /\b(weather|forecast|temperature today|rain|snow)\b/i,
  /\b(joke|riddle|poem|story|essay|homework)\b/i,
  /\b(stock|crypto|bitcoin|ethereum|nft)\b/i,
  /\b(diagnose|symptom|medicine|prescription|dose|disease)\b/i,
  /\b(lawyer|legal advice|sue|lawsuit|contract law)\b/i,
  /\b(translate|translation)\s+(this|that|into|to)\b/i,
  /\b(write|generate)\s+(me\s+)?(a\s+)?(code|program|script|python|javascript|essay|email)\b/i,
  /\b(president|election|politics|war|religion)\b/i,
];

const ON_TOPIC_HINTS = /\b(naics|huff|worcester|store|business|cafe|bakery|liquor|bank|gas|hardware|location|site|map|cbg|competitor|visit|market\s+share|floor\s+area|m2|sq\s*m|coordinates?|lat|lon|scenario)\b/i;

function looksOffTopic(text) {
  if (ON_TOPIC_HINTS.test(text)) return false;
  return OFF_TOPIC_PATTERNS.some(rx => rx.test(text));
}

const OFF_TOPIC_REPLIES = [
  "That's outside what I can help with — I'm built for Worcester store-location decisions only. " +
  "Want to pick a business category and drop a candidate pin instead?",
  "I'd love to help, but I can only run the Huff site-feasibility model for Worcester businesses. " +
  "Pick a category like \"bakery\" or \"liquor store\" to get started.",
  "That's not in my lane — I'm focused on Worcester retail site analysis. " +
  "Try a category from the chips below, or click a location on the map.",
];
let _offTopicIdx = 0;
function offTopicReply() {
  const r = OFF_TOPIC_REPLIES[_offTopicIdx % OFF_TOPIC_REPLIES.length];
  _offTopicIdx += 1;
  return r;
}

function friendlyError(raw) {
  const s = String(raw || "");
  if (/pyodbc|odbc|sql\s*server|connection\s+timeout|tcp\s+provider/i.test(s)) {
    return "I couldn't reach the Azure SQL backend just now. Please try the run again in a moment.";
  }
  if (/api\s*key|openai|deployment/i.test(s)) {
    return "The AI explanation service is unavailable right now, but the model itself can still run.";
  }
  if (s.length > 200) return "Something went wrong on the server. Please try again.";
  return s || "Something went wrong. Please try again.";
}

const renderInputCard = renderQuickChips;  // back-compat shim
renderQuickChips();

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
    // 1. Clear in-flight scenario state, but KEEP chat messages and
    //    state.history so the conversation stays visible for context.
    state.step = "category";
    state.business_category = null;
    state.business_category_label = null;
    state.candidate_lat = null;
    state.candidate_lon = null;
    state.floor_area = null;
    state.last_result = null;
    state.last_inputs = null;
    // state.history intentionally preserved
    // state.scenarios intentionally preserved (saved comparisons stay)

    // 2. Reset the map: clear candidate pin, competitor + POI overlays,
    //    and zoom back to the Worcester service-area bounds.
    if (window.resetMapView) window.resetMapView();

    // 3. Clear the result panel + bottom-left mini-cards so old numbers
    //    don't linger next to the fresh prompt.
    const visitsEl = document.getElementById("visitsValue");
    const shareEl = document.getElementById("shareValue");
    const compEl = document.getElementById("competitorsValue");
    const runtimeEl = document.getElementById("runtimeValue");
    const runtimeNote = document.getElementById("runtimeNote");
    if (visitsEl) visitsEl.textContent = "—";
    if (shareEl) shareEl.textContent = "—";
    if (compEl) compEl.textContent = "—";
    if (runtimeEl) runtimeEl.textContent = "—";
    if (runtimeNote) runtimeNote.textContent = "model execution";
    document.querySelectorAll("#visitsBars span").forEach(b => {
      b.style.height = "30%";
      b.classList.remove("peak");
    });
    const compTable = document.getElementById("competitorTable");
    if (compTable) {
      compTable.innerHTML =
        '<div class="result-empty">Run the model to see competitors.</div>';
    }
    if (competitorChart) {
      competitorChart.destroy();
      competitorChart = null;
      document.querySelector(".chart-wrap")?.classList.remove("has-data");
    }

    saveScenarioBtn.disabled = true;

    // 4. Re-render the step-1 chip row and prompt for category.
    renderInputCard();
    addBotMessage(
      "Started a new scenario. The map is back to the Worcester overview — " +
      "pick a category below or type a business label to begin."
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
    runModel().catch(err => addErrorMessage(friendlyError(err.message || String(err))));
  }
};

async function handleSend() {
  const text = chatInput.value.trim();
  if (!text) return;

  addUserMessage(text);
  chatInput.value = "";

  // Lightweight smalltalk + safety pre-filter handled entirely client-side.
  // Catches greetings, thanks, and obvious off-topic / jailbreak attempts
  // before they hit the model APIs.
  const smalltalk = handleSmalltalk(text);
  if (smalltalk) {
    addBotMessage(smalltalk);
    return;
  }
  if (looksUnsafe(text)) {
    addBotMessage(
      "I can only help with Worcester store-location decisions: running the Huff model, " +
      "comparing sites, interpreting competitors. Try a category like \"bakery\" or " +
      "drop a pin on the map."
    );
    return;
  }
  if (looksOffTopic(text)) {
    addBotMessage(offTopicReply());
    return;
  }

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
    addErrorMessage(friendlyError(error.message || String(error)));
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
    throw new Error(friendlyError(data.error || "Model failed."));
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

  // Flash the "Results ready ▸" pop on the top-right details button so the
  // user knows where to look for the competitor chart and table.
  if (window.flashDetailsReady) window.flashDetailsReady();

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
  const predictedVisits = result.predicted_visits;
  const marketShare = Number(result.market_share);
  const runtime = result.runtime_ms;
  const competitorCount = Array.isArray(result.competitors) ? result.competitors.length : 0;
  const notes = result.notes ?? "";

  // Mirror competitor count + runtime into the bottom-left mini cards
  // (moved here from the advisor pane to reduce chat-pane clutter).
  const compEl = document.getElementById("competitorsValue");
  const runtimeEl = document.getElementById("runtimeValue");
  const runtimeNote = document.getElementById("runtimeNote");
  if (compEl) compEl.textContent = String(competitorCount);
  if (runtimeEl) runtimeEl.textContent = formatNumber(runtime);
  if (runtimeNote) runtimeNote.textContent = notes ? notes.split(".")[0] : "model execution";

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

  // Show at most 10 competitors — long lists overwhelmed the panel
  // per professor's feedback. Engine already caps at 10 nearest.
  const shownCompetitors = competitors.slice(0, 10);
  tableWrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Distance</th>
          <th>Size</th>
          <th>Market share</th>
        </tr>
      </thead>
      <tbody>
        ${shownCompetitors.map(c => {
          const ms = Number(c.market_share);
          const msCell = Number.isFinite(ms) && ms > 0
            ? (ms * 100).toFixed(2) + "%"
            : "N/A";
          return `
          <tr>
            <td>${escapeHtml(c.name ?? c.place_name ?? c.poi_name ?? "Unknown")}</td>
            <td>${escapeHtml(c.distance_miles ?? c.distance ?? "N/A")}</td>
            <td>${escapeHtml(c.size ?? c.floor_area ?? c.area ?? "N/A")}</td>
            <td>${msCell}</td>
          </tr>
        `;}).join("")}
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

  // Rank by current market share (visits-based) — what the business owner
  // wants to know per professor's note. Attraction stays in the result
  // object for debugging but isn't surfaced in the chart anymore.
  const top = [...competitors]
    .map(c => ({
      name: String(c.name ?? c.place_name ?? c.poi_name ?? "Unknown"),
      sharePct: Number(c.market_share ?? 0) * 100
    }))
    .filter(c => Number.isFinite(c.sharePct) && c.sharePct > 0)
    .sort((a, b) => b.sharePct - a.sharePct)
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
        label: "Market share (%)",
        data: top.map(t => t.sharePct),
        backgroundColor: "#2563eb"
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.parsed.x.toFixed(2)}% of category visits`
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { callback: (v) => v + "%" }
        }
      }
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

  // Comparison validity rules (from professor's feedback):
  //   - Saved scenarios MUST share the same NAICS code.
  //   - Two scenarios may share location OR size, but NOT BOTH (a duplicate
  //     candidate would just produce the same model output).
  const candidate = state.last_inputs;
  const SAME_COORD_EPS = 1e-5; // ~1 meter; treats tiny floating diffs as "same point"

  if (state.scenarios.length > 0) {
    const baselineNaics = String(state.scenarios[0].inputs.business_category);
    if (String(candidate.business_category) !== baselineNaics) {
      addBotMessage(
        `I can't save this — the existing comparison set is for NAICS ${baselineNaics}, ` +
        `but this run is NAICS ${candidate.business_category}. ` +
        `Clear the saved scenarios first, or rerun with NAICS ${baselineNaics}.`
      );
      return;
    }

    const dup = state.scenarios.find(s => {
      const sameLatLon =
        Math.abs(s.inputs.candidate_lat - candidate.candidate_lat) < SAME_COORD_EPS &&
        Math.abs(s.inputs.candidate_lon - candidate.candidate_lon) < SAME_COORD_EPS;
      const sameArea = Number(s.inputs.floor_area) === Number(candidate.floor_area);
      return sameLatLon && sameArea;
    });
    if (dup) {
      addBotMessage(
        "I can't save this — it matches an existing scenario on both location and floor area. " +
        "Change at least one of them (move the pin, or use a different store size) and save again."
      );
      return;
    }
  }

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
