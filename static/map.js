let candidateLocation = null;
let candidateMarker = null;
let competitorLayer = null;
let boundsRect = null;
let cbgLayer = null;
let categoryPoiLayer = null;

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
    { color: "#86efac", weight: 2, opacity: 0.85, fill: false, dashArray: "6 4" }
  ).addTo(map).bindTooltip("Worcester service area", { sticky: true });
}

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap &copy; CARTO",
  subdomains: "abcd"
}).addTo(map);

// CBG demand grid: prefer Azure SQL (Module 9), fall back to the static
// GeoJSON polygons if the database isn't reachable.
fetch("/api/cbgs")
  .then(r => r.ok ? r.json() : null)
  .then(data => {
    if (!data || !data.ok || !Array.isArray(data.cbgs) || data.cbgs.length === 0) {
      throw new Error("no SQL cbgs");
    }
    cbgLayer = L.layerGroup().addTo(map);
    data.cbgs.forEach(c => {
      L.circleMarker([c.lat, c.lon], {
        radius: 5,
        weight: 1.5,
        color: "#a1c9ff",
        fillColor: "#a1c9ff",
        fillOpacity: 0.85,
        className: "cbg-glow"
      })
        .addTo(cbgLayer)
        .bindTooltip(`CBG ${c.cbg_id}`, { sticky: true });
    });
    if (cbgLayer.getLayers().length > 0) {
      map.fitBounds(L.featureGroup(cbgLayer.getLayers()).getBounds(), { padding: [20, 20] });
    }
  })
  .catch(() => {
    fetch("/static/data/worcester_cbgs_map.geojson")
      .then(response => response.ok ? response.json() : null)
      .then(geo => {
        if (!geo) return;
        const geoLayer = L.geoJSON(geo, {
          style: { weight: 1, color: "#2563eb", opacity: 0.7, fillOpacity: 0.08 }
        }).addTo(map);
        map.fitBounds(geoLayer.getBounds());
      })
      .catch(err => console.warn("CBG layer unavailable:", err));
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
        radius: 9,
        weight: 2,
        color: "#ff6b6b",
        fillColor: "#ff8a8a",
        fillOpacity: 0.95,
        className: "competitor-glow"
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

function showCategoryPois(naics) {
  if (categoryPoiLayer) {
    categoryPoiLayer.remove();
    categoryPoiLayer = null;
  }
  if (!naics) return;
  fetch(`/api/pois?naics=${encodeURIComponent(naics)}`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || !data.ok || !Array.isArray(data.pois)) return;
      categoryPoiLayer = L.layerGroup().addTo(map);
      data.pois.forEach(p => {
        L.circleMarker([p.lat, p.lon], {
          radius: 8,
          weight: 2,
          color: "#ffb782",
          fillColor: "#ffb782",
          fillOpacity: 0.95,
          className: "poi-glow"
        })
          .addTo(categoryPoiLayer)
          .bindPopup(
            `<strong>${escapeHtml(p.name)}</strong><br>` +
            `NAICS: ${escapeHtml(p.naics_code)}<br>` +
            (p.area_sqm ? `Area: ${Number(p.area_sqm).toLocaleString()} m²` : "")
          );
      });
    })
    .catch(err => console.warn("POI overlay unavailable:", err));
}

function resetMapView() {
  // Drop candidate pin
  if (candidateMarker) { candidateMarker.remove(); candidateMarker = null; }
  candidateLocation = null;

  // Drop competitors (result of the last run) and category POI overlay
  if (competitorLayer) { competitorLayer.remove(); competitorLayer = null; }
  if (categoryPoiLayer) { categoryPoiLayer.remove(); categoryPoiLayer = null; }

  // Reset map view to the Worcester service-area bounding box
  map.fitBounds(
    [
      [WORCESTER_BOUNDS.lat_min, WORCESTER_BOUNDS.lon_min],
      [WORCESTER_BOUNDS.lat_max, WORCESTER_BOUNDS.lon_max],
    ],
    { padding: [20, 20] }
  );

  const sel = document.getElementById("selectedLocation");
  if (sel) {
    sel.innerText =
      "Click anywhere inside the Worcester service area to place a candidate site.";
  }
}

// Expose functions so chat.js can call them.
window.setCandidateLocation = setCandidateLocation;
window.getCandidateLocation = getCandidateLocation;
window.plotCompetitors = plotCompetitors;
window.showCategoryPois = showCategoryPois;
window.resetMapView = resetMapView;
window.isInWorcester = isInWorcester;
window.getWorcesterBounds = () => WORCESTER_BOUNDS;
