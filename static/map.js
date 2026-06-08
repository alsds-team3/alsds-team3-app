let candidateLocation = null;
let candidateMarker = null;
let competitorLayer = null;
let boundsRect = null;

// Worcester service-area bounding box. Default mirrors the server; replaced
// by /api/bounds on load so client and server stay in sync.
let WORCESTER_BOUNDS = {
  lat_min: 42.18, lat_max: 42.36,
  lon_min: -71.92, lon_max: -71.68
};

function isInWorcester(lat, lon) {
  return (
    lat >= WORCESTER_BOUNDS.lat_min && lat <= WORCESTER_BOUNDS.lat_max &&
    lon >= WORCESTER_BOUNDS.lon_min && lon <= WORCESTER_BOUNDS.lon_max
  );
}

const map = L.map("map").setView([42.2626, -71.8023], 12);

fetch("/api/bounds")
  .then(r => r.ok ? r.json() : null)
  .then(b => {
    if (b) WORCESTER_BOUNDS = b;
    drawBoundsRectangle();
  })
  .catch(() => drawBoundsRectangle());

function drawBoundsRectangle() {
  if (boundsRect) boundsRect.remove();
  boundsRect = L.rectangle(
    [
      [WORCESTER_BOUNDS.lat_min, WORCESTER_BOUNDS.lon_min],
      [WORCESTER_BOUNDS.lat_max, WORCESTER_BOUNDS.lon_max]
    ],
    { color: "#16a34a", weight: 2, fill: false, dashArray: "6 4" }
  ).addTo(map).bindTooltip("Worcester service area", { sticky: true });
}

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

fetch("/static/data/worcester_cbgs_map.geojson")
  .then(response => {
    if (!response.ok) {
      throw new Error("GeoJSON not found");
    }
    return response.json();
  })
  .then(data => {
    const geoLayer = L.geoJSON(data, {
      style: {
        weight: 1,
        color: "#2563eb",
        opacity: 0.7,
        fillOpacity: 0.08
      }
    }).addTo(map);

    map.fitBounds(geoLayer.getBounds());
  })
  .catch(error => {
    console.warn("Worcester GeoJSON layer could not be loaded:", error);
  });

map.on("click", function (event) {
  const lat = event.latlng.lat;
  const lon = event.latlng.lng;
  if (!isInWorcester(lat, lon)) {
    const sel = document.getElementById("selectedLocation");
    if (sel) {
      sel.innerText =
        `That point (${lat.toFixed(6)}, ${lon.toFixed(6)}) is outside the Worcester service area. ` +
        "Pick a spot inside the green dashed box.";
    }
    return;
  }
  setCandidateLocation(lat, lon, true);
});

function setCandidateLocation(lat, lon, notifyChat = false) {
  candidateLocation = {
    lat: Number(lat),
    lon: Number(lon)
  };

  if (candidateMarker) {
    candidateMarker.setLatLng([candidateLocation.lat, candidateLocation.lon]);
  } else {
    candidateMarker = L.marker([candidateLocation.lat, candidateLocation.lon])
      .addTo(map)
      .bindPopup("Proposed Store Location");
  }

  candidateMarker.openPopup();

  document.getElementById("selectedLocation").innerText =
    `Selected candidate location: ${candidateLocation.lat.toFixed(6)}, ${candidateLocation.lon.toFixed(6)}`;

  map.setView([candidateLocation.lat, candidateLocation.lon], 14);

  if (notifyChat && window.onMapLocationSelected) {
    window.onMapLocationSelected(candidateLocation);
  }
}

function getCandidateLocation() {
  return candidateLocation;
}

function plotCompetitors(competitors) {
  if (competitorLayer) {
    competitorLayer.remove();
  }

  competitorLayer = L.layerGroup().addTo(map);

  if (!Array.isArray(competitors)) {
    return;
  }

  competitors.forEach(comp => {
    if (comp.lat && comp.lon) {
      L.circleMarker([comp.lat, comp.lon], {
        radius: 6,
        weight: 1,
        color: "#dc2626",
        fillOpacity: 0.7
      })
        .addTo(competitorLayer)
        .bindPopup(
          `<strong>${escapeHtml(comp.name || "Competitor")}</strong><br>` +
          `Size: ${comp.size ?? "N/A"}<br>` +
          `Attraction: ${comp.attraction ?? "N/A"}`
        );
    }
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Expose functions so chat.js can call them.
window.setCandidateLocation = setCandidateLocation;
window.getCandidateLocation = getCandidateLocation;
window.plotCompetitors = plotCompetitors;
window.isInWorcester = isInWorcester;
window.getWorcesterBounds = () => WORCESTER_BOUNDS;
