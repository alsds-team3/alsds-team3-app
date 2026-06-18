// Business category -> NAICS code mapping
//
// Every code below MUST exist in the calibrated parameters table in Azure SQL
// (mirror of CATEGORIES / NAICS_CATEGORY_MAP in app.py). Adding labels that
// point to uncalibrated NAICS codes produces "No calibrated alpha/beta
// parameters found" at runtime — users see that as a red error in chat.

// Calibrated NAICS list — used for the dropdown / suggestion chips.
// Populated from /api/categories on load (this is just a fallback).
let CALIBRATED_CATEGORIES = [
  { naics: "4441",   label: "Building Material & Supplies Dealers" },
  { naics: "311811", label: "Bakeries" },
  { naics: "3399",   label: "Other Miscellaneous Manufacturing" },
  { naics: "447110", label: "Gasoline Stations" },
  { naics: "621210", label: "Offices of Dentists" },
  { naics: "522310", label: "Mortgage & Credit Intermediation" },
  { naics: "922110", label: "Justice, Public Order, and Safety" },
  { naics: "453991", label: "Other Miscellaneous Retailers" },
  { naics: "441310", label: "Auto Parts, Accessories & Tire Stores" },
  { naics: "445310", label: "Beer, Wine & Liquor Stores" },
  { naics: "452319", label: "General Merchandise / Warehouse Clubs" },
  { naics: "531120", label: "Lessors of Real Estate" },
  { naics: "522110", label: "Banks / Depository Credit Intermediation" },
  { naics: "611310", label: "Colleges & Universities" },
  { naics: "531210", label: "Real Estate Agents & Brokers" },
  { naics: "523930", label: "Financial Investment Activities" },
  { naics: "517312", label: "Telecommunications Carriers" },
  { naics: "621511", label: "Medical & Diagnostic Laboratories" },
  { naics: "6214",   label: "Outpatient Care Centers" },
  { naics: "812910", label: "Pet Care & Other Personal Services" },
  { naics: "448310", label: "Jewelry, Luggage & Leather Goods" },
  { naics: "512240", label: "Sound Recording Studios" },
  { naics: "524113", label: "Insurance Carriers" },
];

const NAICS_MAP = {
  "hardware": "4441", "hardware store": "4441",
  "home improvement": "4441", "building materials": "4441",
  "lumber": "4441", "lumber yard": "4441",

  "bakery": "311811", "bakeries": "311811", "bread shop": "311811",

  "miscellaneous manufacturing": "3399", "manufacturing": "3399",

  "gas station": "447110", "gas": "447110", "fuel station": "447110",
  "petrol station": "447110",

  "dentist": "621210", "dental office": "621210", "dental clinic": "621210",

  "mortgage": "522310", "mortgage broker": "522310",
  "credit intermediation": "522310", "loan office": "522310",

  "courthouse": "922110", "court": "922110", "public safety": "922110",

  "miscellaneous retail": "453991", "gift shop": "453991", "tobacco shop": "453991",

  "auto parts": "441310", "tire store": "441310", "tires": "441310",
  "car parts": "441310", "automotive parts": "441310",

  "liquor store": "445310", "liquor": "445310", "wine store": "445310",
  "wine shop": "445310", "beer store": "445310",

  "warehouse club": "452319", "supercenter": "452319",
  "general merchandise": "452319", "department store": "452319",

  "lessor": "531120", "property leasing": "531120", "rental property": "531120",

  "bank": "522110", "credit union": "522110", "depository": "522110",

  "college": "611310", "university": "611310", "campus": "611310",

  "real estate agent": "531210", "real estate broker": "531210",
  "realtor": "531210", "real estate office": "531210",

  "investment firm": "523930", "wealth management": "523930",
  "financial advisor": "523930", "investment advisor": "523930",

  "telecom": "517312", "wireless carrier": "517312", "phone carrier": "517312",
  "cellular store": "517312",

  "medical lab": "621511", "diagnostic lab": "621511", "lab": "621511",
  "blood lab": "621511",

  "outpatient": "6214", "outpatient clinic": "6214", "urgent care": "6214",
  "clinic": "6214",

  "pet care": "812910", "pet grooming": "812910", "pet services": "812910",
  "personal services": "812910",

  "jewelry": "448310", "jewelry store": "448310",
  "luggage": "448310", "leather goods": "448310",

  "recording studio": "512240", "sound studio": "512240", "music studio": "512240",

  "insurance": "524113", "insurance agency": "524113",
  "insurance carrier": "524113",
};

function isCalibratedNaics(code) {
  return CALIBRATED_CATEGORIES.some(c => c.naics === String(code));
}

function resolveBusinessCategory(input) {
  if (!input) return null;
  const text = String(input).trim().toLowerCase();

  // Bare NAICS code — accept any code that the server knows about
  // (calibrated 23 OR uncalibrated-but-present-in-POI-data). The server
  // will reject truly unknown codes with the historical-records message.
  if (/^\d{2,6}$/.test(text)) {
    if (isCalibratedNaics(text)) return text;
    if (KNOWN_NAICS.has(text)) return text;
    // KNOWN_NAICS may not be populated yet (race with /api/categories).
    // Accept the code and let the server gate it.
    return text;
  }

  // Exact label match in the alias table.
  if (NAICS_MAP[text]) return NAICS_MAP[text];

  // Fuzzy: longest alias key contained in the input string.
  let best = null;
  for (const key of Object.keys(NAICS_MAP)) {
    if (text.includes(key)) {
      if (!best || key.length > best.length) best = key;
    }
  }
  return best ? NAICS_MAP[best] : null;
}

// All NAICS codes present in worchester_businesses (calibrated + fallback).
// Populated from /api/categories. Used to permit fallback runs without
// rejecting the request at the frontend.
let KNOWN_NAICS = new Set();

// Refresh from the server so client and server can't drift.
fetch("/api/categories")
  .then(r => r.ok ? r.json() : null)
  .then(data => {
    if (!data) return;
    if (Array.isArray(data.categories) && data.categories.length) {
      CALIBRATED_CATEGORIES = data.categories;
    }
    if (data.aliases && typeof data.aliases === "object") {
      Object.assign(NAICS_MAP, data.aliases);
    }
    if (Array.isArray(data.known_naics)) {
      KNOWN_NAICS = new Set(data.known_naics.map(String));
    }
    if (typeof window.onCategoriesLoaded === "function") {
      window.onCategoriesLoaded(CALIBRATED_CATEGORIES);
    }
  })
  .catch(() => { /* keep local fallback */ });

function isKnownNaics(code) {
  return KNOWN_NAICS.has(String(code));
}
function naicsTier(code) {
  if (isCalibratedNaics(code)) return "calibrated";
  if (isKnownNaics(code)) return "fallback";
  return "unknown";
}
window.isKnownNaics = isKnownNaics;
window.naicsTier = naicsTier;

window.NAICS_MAP = NAICS_MAP;
window.resolveBusinessCategory = resolveBusinessCategory;
window.isCalibratedNaics = isCalibratedNaics;
window.getCalibratedCategories = () => CALIBRATED_CATEGORIES;
