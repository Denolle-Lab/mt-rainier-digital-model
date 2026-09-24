// Rainier Sensor Atlas: MapLibre GL terrain viewer for the rainier3d sensor inventory.
// Data come from scripts/08_atlas.py (web/atlas/data/). Serve with `pixi run atlas`.
"use strict";

const D = "data/";
const TERRAIN = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
const LITH = { Qs: "#f2cc8f", Qra: "#f28482", To: "#bc8a5f", Tg: "#e63946", Td: "#9d4edd", Tdi: "#c77dff" };
const DEPTH = ["interpolate", ["linear"], ["get", "depth"], 0, "#fde725", 10, "#35b779", 20, "#31688e", 30, "#440154"];

const state = { view: "3d", style: "relief", color: "elev", vex: 1.5, fams: new Set(), retired: true,
  sections: [], draw: null, subVar: "vs", subModel: "", zmin: -6000, sliceZ: -2000, sliceOn: false, active: null };
const PRESETS = [ // name, A [lon, lat], B [lon, lat]
  ["W–E through summit", [-122.25, 46.8523], [-121.45, 46.8523]],
  ["S–N through summit", [-121.7603, 46.53], [-121.7603, 47.12]],
  ["WRSZ → summit", [-122.10, 46.78], [-121.55, 46.93]],
  ["Nisqually DAS corridor", [-121.93, 46.735], [-121.72, 46.79]],
];
const subName = () => (["vs", "vp"].includes(state.subVar) ? state.subVar + state.subModel : state.subVar);
const $ = (s) => document.querySelector(s);
const getJSON = (f) => fetch(D + f).then((r) => { if (!r.ok) throw new Error(f + " " + r.status); return r.json(); });
const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? "–" : Number(x).toFixed(d));

(async function main() {
  const [S, sites, das, dasCh, events] = await Promise.all(
    ["summary.json", "sites.geojson", "das.geojson", "das_channels.geojson", "events.geojson"].map(getJSON));
  const FAM = S.families;
  window.atlasData = { S, sites, events, dasCh, state, subName };
  Object.keys(FAM).forEach((k) => state.fams.add(k));

  // ---------- panels
  // the fiber counts as one sensor here; its channels are listed in the family bar
  $("#stats").innerHTML = [
    [S.n_sensors + 1, "sensors"], [S.n_operating + 1, "operating"],
    [S.n_sites, "sites"], [S.n_events, "events"],
  ].map(([v, l]) => `<div><b>${v.toLocaleString()}</b><span>${l}</span></div>`).join("");
  $("#sources").textContent = S.sources;
  $("#family-bar").innerHTML = Object.entries(FAM).map(([k, f]) =>
    `<button data-f="${k}"><i style="background:${f.color}"></i>${f.label} <em>${S.counts[k].sensors.toLocaleString()}${k === "das" ? " ch" : ""}</em></button>`).join("");
  $("#region-list").innerHTML = S.regions.map((r, i) =>
    `<li data-i="${i}" class="${i === 0 ? "on" : ""}">${r.name}<span>${r.sites}</span></li>`).join("");
  $("#overlay-list").innerHTML = Object.entries(S.overlays).map(([k, o]) => `
    <div class="ov"><div class="top"><label class="chk"><input type="checkbox" data-ov="${k}" /> ${o.label}</label></div>
    <input type="range" min="0" max="1" step="0.05" value="${o.opacity}" data-op="${k}" />
    ${o.registration ? `<small>registration: ${o.registration}</small>` : ""}</div>`).join("");
  drawLegendDonut(FAM);

  // ---------- map
  const dem = new mlcontour.DemSource({ url: TERRAIN, encoding: "terrarium", maxzoom: 13, worker: true });
  dem.setupMaplibre(maplibregl);
  const b = S.domain_bbox;
  const map = new maplibregl.Map({
    container: "map", maxPitch: 80, pitch: 58, bearing: -20, center: S.summit, zoom: 9.7,
    attributionControl: { compact: true },
    style: {
      version: 8, glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#0d1014" } }],
    },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
  window.atlasMap = map;

  map.on("load", async () => {
    const demSrc = { type: "raster-dem", tiles: [TERRAIN], tileSize: 256, encoding: "terrarium", maxzoom: 15 };
    map.addSource("terrain", { ...demSrc, attribution: "Terrain: AWS Terrain Tiles (Mapzen, USGS 3DEP)" });
    map.addSource("dem", demSrc);
    map.setTerrain({ source: "terrain", exaggeration: state.vex });

    map.addLayer({ id: "relief-color", type: "color-relief", source: "dem", paint: {
      "color-relief-opacity": 0.9,
      "color-relief-color": ["interpolate", ["linear"], ["elevation"],
        0, "#16231c", 400, "#1f3627", 800, "#2f4d34", 1200, "#4a6440", 1600, "#6f7550",
        2000, "#8c8266", 2500, "#a59d8c", 3000, "#c8c5bf", 3600, "#e4e6e8", 4400, "#ffffff"] } });
    map.addLayer({ id: "hillshade", type: "hillshade", source: "dem", paint: {
      "hillshade-exaggeration": 0.6, "hillshade-shadow-color": "rgba(0,0,0,0.65)",
      "hillshade-highlight-color": "rgba(255,255,255,0.18)", "hillshade-accent-color": "rgba(0,0,0,0.25)" } });

    for (const [k, o] of Object.entries(S.overlays)) {
      map.addSource("ov-" + k, { type: "image", url: D + o.url, coordinates: o.coordinates });
      map.addLayer({ id: "ov-" + k, type: "raster", source: "ov-" + k,
        layout: { visibility: "none" }, paint: { "raster-opacity": o.opacity, "raster-fade-duration": 0 } });
    }
    map.addLayer({ id: "hillshade-over", type: "hillshade", source: "dem", layout: { visibility: "none" }, paint: {
      "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "rgba(0,0,0,0.45)",
      "hillshade-highlight-color": "rgba(255,255,255,0.0)", "hillshade-accent-color": "rgba(0,0,0,0.1)" } });

    map.addSource("contours", { type: "vector", maxzoom: 15, tiles: [dem.contourProtocolUrl({
      thresholds: { 9: [200, 1000], 11: [100, 500], 12: [100, 500], 13: [50, 250], 14: [20, 100] },
      elevationKey: "ele", levelKey: "level", contourLayer: "contours" })] });
    map.addLayer({ id: "contours", type: "line", source: "contours", "source-layer": "contours",
      layout: { visibility: "none" }, paint: { "line-color": "rgba(232,236,241,0.45)",
        "line-width": ["match", ["get", "level"], 1, 1.1, 0.45] } });

    map.addSource("domain", { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "LineString",
      coordinates: [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]] } } });
    map.addLayer({ id: "domain", type: "line", source: "domain",
      paint: { "line-color": "rgba(232,236,241,0.5)", "line-width": 1, "line-dasharray": [3, 3] } });

    map.addSource("events", { type: "geojson", data: events });
    map.addLayer({ id: "events", type: "circle", source: "events", paint: {
      "circle-radius": ["interpolate", ["linear"], ["get", "mag"], 0, 1.6, 2, 3.2, 4, 8],
      "circle-color": DEPTH, "circle-opacity": 0.7, "circle-stroke-width": 0 } });

    map.addSource("das", { type: "geojson", data: das });
    map.addSource("das-ch", { type: "geojson", data: dasCh });
    map.addLayer({ id: "das-glow", type: "line", source: "das", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#ffffff", "line-width": 7, "line-blur": 6, "line-opacity": 0.35 } });
    map.addLayer({ id: "das-casing", type: "line", source: "das", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#0b0d10", "line-width": 5.5 } });
    map.addLayer({ id: "das-line", type: "line", source: "das", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#f8f9fa", "line-width": 3 } });
    map.addLayer({ id: "das-hit", type: "circle", source: "das-ch",
      paint: { "circle-radius": 6, "circle-opacity": 0, "circle-stroke-width": 0 } });

    // sites: geophone nodes as dots, everything else as donut markers
    const nodeFeats = sites.features.filter((f) => f.properties.family === "nodes" && f.properties.n === 1);
    const donutFeats = sites.features.filter((f) => !(f.properties.family === "nodes" && f.properties.n === 1));
    for (const f of donutFeats) {
      const p = f.properties;
      map.addImage("site-" + p.id, donut(JSON.parse(p.sensors), p.status !== "operating", FAM), { pixelRatio: 2 });
    }
    map.addSource("nodes", { type: "geojson", data: { type: "FeatureCollection", features: nodeFeats } });
    map.addLayer({ id: "nodes", type: "circle", source: "nodes", paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 2.2, 13, 5],
      "circle-color": ["case", ["==", ["get", "status"], "operating"], FAM.nodes.color, "#7d7050"],
      "circle-opacity": ["case", ["==", ["get", "status"], "operating"], 0.95, 0.45],
      "circle-stroke-color": "#0d1014", "circle-stroke-width": 0.8 } });
    map.addSource("sites", { type: "geojson", data: { type: "FeatureCollection", features: donutFeats } });
    map.addLayer({ id: "sites", type: "symbol", source: "sites", layout: {
      "icon-image": ["concat", "site-", ["get", "id"]], "icon-allow-overlap": true, "icon-ignore-placement": true,
      "icon-size": ["interpolate", ["linear"], ["zoom"], 8, 0.55, 11, 0.85, 14, 1.1],
      "symbol-sort-key": ["case", ["==", ["get", "status"], "operating"], 1, 0],
      "text-field": ["step", ["zoom"], "", 11, ["concat", ["get", "name"], "  ", ["to-string", ["get", "n"]]]],
      "text-font": ["Open Sans Semibold"], "text-size": 11, "text-anchor": "left", "text-offset": [1.3, 0],
      "text-optional": true },
      paint: { "text-color": "#e8ecf1", "text-halo-color": "rgba(10,12,16,0.85)", "text-halo-width": 1.4 } });

    map.addSource("sections", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "sections-casing", type: "line", source: "sections", paint: { "line-color": "#0b0d10", "line-width": 6 } });
    map.addLayer({ id: "sections", type: "line", source: "sections",
      paint: { "line-color": ["case", ["get", "active"], "#ffe066", "#e8ecf1"], "line-width": 3, "line-dasharray": [2, 1] } });
    map.addLayer({ id: "section-labels", type: "symbol", source: "sections", filter: ["==", "$type", "Point"],
      layout: { "text-field": ["get", "label"], "text-font": ["Open Sans Semibold"], "text-size": 14, "text-allow-overlap": true },
      paint: { "text-color": "#ffe066", "text-halo-color": "#0b0d10", "text-halo-width": 2 } });
    wireControls(map, S, FAM);
    if (S.model && S.model.available) wireSubsurface(map, S, FAM, sites, events);
    else document.querySelectorAll("#sub-var,#sub-model,#sub-zmin,#draw-section,#open-ug,#lyr-slice").forEach((e) => (e.disabled = true));
    applyFilters(map);
    wireHover(map, FAM);
  });
})().catch((e) => { document.body.insertAdjacentHTML("beforeend",
  `<div class="card" style="top:40%;left:40%">Could not load atlas data: ${e.message}<br>Run <code>pixi run s8</code> then <code>pixi run atlas</code>.</div>`); });

// ---------- donut marker: one ring segment per sensor, colored by family
function donut(sensors, retired, FAM) {
  const px = 2, S = 40 * px, c = document.createElement("canvas");
  c.width = c.height = S;
  const g = c.getContext("2d"), cx = S / 2, r = 13 * px, w = 5 * px;
  g.beginPath(); g.arc(cx, cx, r, 0, 2 * Math.PI); g.strokeStyle = "rgba(8,10,14,0.85)"; g.lineWidth = w + 3 * px; g.stroke();
  let segs = sensors.map((s) => s.family);
  if (segs.length > 18) { // aggregate: arc length proportional to family counts
    const cnt = {}; segs.forEach((f) => (cnt[f] = (cnt[f] || 0) + 1));
    segs = Object.entries(cnt).flatMap(([f, n]) => Array(Math.max(1, Math.round((18 * n) / segs.length))).fill(f));
  }
  const n = segs.length, gap = n > 1 ? 0.12 : 0;
  segs.forEach((f, i) => {
    const a0 = -Math.PI / 2 + (2 * Math.PI * i) / n + gap / 2, a1 = -Math.PI / 2 + (2 * Math.PI * (i + 1)) / n - gap / 2;
    g.beginPath(); g.arc(cx, cx, r, a0, a1); g.strokeStyle = FAM[f].color; g.globalAlpha = retired ? 0.4 : 1;
    g.lineWidth = w; g.lineCap = "butt"; g.stroke();
  });
  g.globalAlpha = 1; g.beginPath(); g.arc(cx, cx, 2.6 * px, 0, 2 * Math.PI);
  g.fillStyle = retired ? "#6b7480" : "#ffffff"; g.fill();
  return g.getImageData(0, 0, S, S);
}

function drawLegendDonut(FAM) {
  const img = donut(["seismic", "strong", "infrasound", "gnss"].map((f) => ({ family: f })), false, FAM);
  const c = $("#lg-donut"), g = c.getContext("2d"), tmp = document.createElement("canvas");
  tmp.width = img.width; tmp.height = img.height; tmp.getContext("2d").putImageData(img, 0, 0);
  g.drawImage(tmp, 0, 0, c.width, c.height);
}

// ---------- controls
function setVis(map, id, on) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none"); }

function applyStyle(map) {
  const relief = state.style === "relief";
  setVis(map, "relief-color", state.color === "elev");
  map.setPaintProperty("hillshade", "hillshade-highlight-color",
    state.color === "elev" ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.45)");
  map.setPaintProperty("hillshade", "hillshade-exaggeration", relief ? 0.6 : 0.25);
  setVis(map, "contours", !relief);
}

function applyFilters(map) {
  const fams = [...state.fams];
  const famF = ["any", ...fams.map((f) => ["in", f, ["get", "families"]])];
  const stF = state.retired ? true : ["==", ["get", "status"], "operating"];
  const f = ["all", famF, stF];
  map.setFilter("sites", f);
  map.setFilter("nodes", f);
  const dasOn = state.fams.has("das") && $("#lyr-das").checked;
  ["das-glow", "das-casing", "das-line", "das-hit"].forEach((id) => setVis(map, id, dasOn));
}

function wireControls(map, S, FAM) {
  document.querySelectorAll(".seg").forEach((seg) => seg.addEventListener("click", (e) => {
    const bt = e.target.closest("button"); if (!bt) return;
    seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === bt));
    state[seg.dataset.ctl] = bt.dataset.v;
    if (seg.dataset.ctl === "view") {
      if (state.view === "2d") { map.setTerrain(null); map.easeTo({ pitch: 0, bearing: 0, duration: 800 }); }
      else { map.setTerrain({ source: "terrain", exaggeration: state.vex }); map.easeTo({ pitch: 58, bearing: -20, duration: 800 }); }
    } else applyStyle(map);
  }));
  $("#vex").addEventListener("input", (e) => {
    state.vex = +e.target.value; $("#vex-label").textContent = `Vertical ×${state.vex}`;
    if (state.view === "3d") map.setTerrain({ source: "terrain", exaggeration: state.vex });
  });
  document.querySelectorAll("[data-ov]").forEach((cb) => cb.addEventListener("change", () => {
    setVis(map, "ov-" + cb.dataset.ov, cb.checked);
    setVis(map, "hillshade-over", [...document.querySelectorAll("[data-ov]")].some((x) => x.checked));
  }));
  document.querySelectorAll("[data-op]").forEach((sl) => sl.addEventListener("input", () =>
    map.setPaintProperty("ov-" + sl.dataset.op, "raster-opacity", +sl.value)));
  $("#lyr-das").addEventListener("change", () => applyFilters(map));
  $("#lyr-das-lith").addEventListener("change", (e) => map.setPaintProperty("das-line", "line-color", e.target.checked
    ? ["match", ["get", "lithology"], ...Object.entries(LITH).flat(), "#f8f9fa"] : "#f8f9fa"));
  $("#lyr-events").addEventListener("change", (e) => setVis(map, "events", e.target.checked));
  $("#lyr-retired").addEventListener("change", (e) => { state.retired = e.target.checked; applyFilters(map); });
  $("#lyr-domain").addEventListener("change", (e) => setVis(map, "domain", e.target.checked));
  $("#family-bar").addEventListener("click", (e) => {
    const bt = e.target.closest("button"); if (!bt) return;
    const f = bt.dataset.f;
    state.fams.has(f) ? state.fams.delete(f) : state.fams.add(f);
    bt.classList.toggle("off", !state.fams.has(f));
    applyFilters(map);
  });
  $("#region-list").addEventListener("click", (e) => {
    const li = e.target.closest("li"); if (!li) return;
    document.querySelectorAll("#region-list li").forEach((x) => x.classList.toggle("on", x === li));
    const r = S.regions[+li.dataset.i], bb = r.bbox, is3d = state.view === "3d";
    map.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]], { padding: { top: 60, bottom: 90, left: 280, right: 300 },
      pitch: is3d ? (r.pitch ?? 55) : 0, bearing: is3d ? (r.bearing ?? -20) : 0, duration: 1600 });
  });
}

// ---------- hover cards
function wireHover(map, FAM) {
  const box = $("#hover");
  const layers = ["sites", "nodes", "das-hit", "events"];
  map.on("mousemove", (e) => {
    const live = layers.filter((l) => map.getLayer(l) && map.getLayoutProperty(l, "visibility") !== "none");
    const f = map.queryRenderedFeatures(e.point, { layers: live })[0];
    map.getCanvas().style.cursor = f ? "pointer" : "";
    if (!f) { box.classList.add("hidden"); return; }
    box.innerHTML = f.layer.id === "events" ? eventCard(f.properties)
      : f.layer.id === "das-hit" ? dasCard(f.properties) : siteCard(f.properties, FAM);
    box.classList.remove("hidden");
    const W = window.innerWidth, H = window.innerHeight, bw = box.offsetWidth, bh = box.offsetHeight;
    box.style.left = Math.min(e.point.x + 18, W - bw - 12) + "px";
    box.style.top = Math.min(Math.max(e.point.y - 20, 12), H - bh - 12) + "px";
  });
  map.on("mouseout", () => box.classList.add("hidden"));
  map.on("click", (e) => {
    const f = map.queryRenderedFeatures(e.point, { layers: ["sites", "nodes"] })[0];
    if (f && f.properties.url) window.open(f.properties.url, "_blank");
  });
}

function siteCard(p, FAM) {
  const sensors = JSON.parse(p.sensors);
  const byFam = {};
  sensors.forEach((s) => (byFam[s.family] = (byFam[s.family] || 0) + 1));
  const famLine = Object.entries(byFam).map(([f, n]) => `${n} ${FAM[f].label.toLowerCase()}`).join(" · ");
  const elev = p.elev === null || p.elev === "null" || p.elev === undefined ? "" : ` · ${fmt(+p.elev)} m`;
  let h = `<h3>${p.name}</h3><div class="meta">${p.n} sensor${p.n > 1 ? "s" : ""}${elev} · ${p.status}<br>${famLine}<br>${p.source}</div>`;
  if (p.deployers) h += `<div class="sec">Deployment</div><div>${p.deployers}</div>`;
  if (p.notes) h += `<div class="note">${p.notes}</div>`;
  if (String(p.in_model) === "false") h += `<div class="more">outside the rainier3d model domain</div>`;
  const rows = sensors.slice(0, 12).map((s) => `<tr><td><span class="b" style="background:${FAM[s.family].color}"></span>${s.kind}
      ${s.channels ? `<div class="ch">${s.channels.length > 70 ? s.channels.slice(0, 70) + "…" : s.channels}</div>` : ""}</td>
      <td class="r">${s.status === "operating" ? "Operating" : "Retired"}<br>${s.start || "?"}${s.end ? " – " + s.end : " –"}</td></tr>`).join("");
  h += `<div class="sec">Sensors</div><table>${rows}</table>`;
  if (sensors.length > 12) h += `<div class="more">+${sensors.length - 12} more</div>`;
  if (p.url) h += `<div class="more">click to open station metadata</div>`;
  return h;
}

function dasCard(p) {
  return `<h3>DAS channel ${p.ch}</h3><div class="meta">Paradise–Nisqually Entrance fiber</div><table>
    <tr><td>Optical distance</td><td class="r">${fmt(p.optical_m, 1)} m</td></tr>
    <tr><td>Distance along road</td><td class="r">${fmt(p.road_m, 1)} m</td></tr>
    <tr><td>Elevation</td><td class="r">${fmt(p.elev)} m</td></tr>
    <tr><td>Lithology (channel table)</td><td class="r"><span class="b" style="background:${LITH[p.lithology] || "#999"}"></span>${p.lithology}</td></tr>
    ${p.notice ? `<tr><td>Notice</td><td class="r">${p.notice}</td></tr>` : ""}</table>`;
}

function eventCard(p) {
  return `<h3>M ${fmt(p.mag, 1)} earthquake</h3><div class="meta">${new Date(+p.time).toISOString().replace("T", " ").slice(0, 19)} UTC</div>
    <table><tr><td>Depth</td><td class="r">${fmt(p.depth, 1)} km</td></tr><tr><td>Type</td><td class="r">${p.type}</td></tr>
    <tr><td>ComCat id</td><td class="r">${p.id}</td></tr></table>`;
}


// ---------- subsurface: sections, depth slice, underground view
function sectionFeatures() {
  const f = [];
  state.sections.forEach((sec, i) => {
    const active = sec === state.active, tag = String.fromCharCode(65 + i);
    f.push({ type: "Feature", properties: { active }, geometry: { type: "LineString", coordinates: [sec.A, sec.B] } });
    f.push({ type: "Feature", properties: { label: tag, active }, geometry: { type: "Point", coordinates: sec.A } });
    f.push({ type: "Feature", properties: { label: tag + "′", active }, geometry: { type: "Point", coordinates: sec.B } });
  });
  return { type: "FeatureCollection", features: f };
}

function addSection(map, name, A, B) {
  const sec = { name, A, B };
  state.sections.push(sec);
  state.active = sec;
  map.getSource("sections").setData(sectionFeatures());
  renderSection(sec);
  if (window.Underground && window.Underground.isOpen()) window.Underground.refresh();
}

async function renderSection(sec) {
  const panel = $("#section-panel"), cv = $("#sec-canvas"), over = $("#sec-over");
  panel.classList.remove("hidden");
  const i = state.sections.indexOf(sec), tag = String.fromCharCode(65 + i);
  $("#sec-title").textContent = `${tag}–${tag}′  ${sec.name}`;
  const wrap = cv.parentElement, dpr = Math.min(2, window.devicePixelRatio || 1);
  // floors: the panel can still be laid out at zero size in the frame it is unhidden (phone sheets)
  const W = Math.max(320, Math.min(1400, Math.round(wrap.clientWidth * dpr))), H = Math.max(160, Math.min(600, Math.round(wrap.clientHeight * dpr)));
  $("#sec-meta").textContent = "computing…";
  const name = subName();
  const r = await Sub.section(name, sec.A, sec.B, { zmin: state.zmin, width: W, height: H });
  sec.result = r;
  cv.width = over.width = W; cv.height = over.height = H;
  const g = cv.getContext("2d");
  g.fillStyle = "#0b0d10"; g.fillRect(0, 0, W, H);
  g.drawImage(r.canvas, 0, 0);
  const zpx = (z) => ((r.zmax - z) / (r.zmax - r.zmin)) * (H - 1);
  // sea level, surface line
  g.strokeStyle = "rgba(255,255,255,0.35)"; g.setLineDash([4 * dpr, 4 * dpr]); g.beginPath();
  g.moveTo(0, zpx(0)); g.lineTo(W, zpx(0)); g.stroke(); g.setLineDash([]);
  g.strokeStyle = "#f8f9fa"; g.lineWidth = 1.5 * dpr; g.beginPath();
  r.surf.forEach((z, c) => (c ? g.lineTo(c, zpx(z)) : g.moveTo(c, zpx(z)))); g.stroke();
  // ice: surface minus IceBoost thickness
  const surf = Sub.surf(), ice = [];
  for (let c = 0; c < W; c++) {
    const t = c / (W - 1);
    ice.push(Sub.surfaceAt(r.xa + t * (r.xb - r.xa), r.ya + t * (r.yb - r.ya), "ice"));
  }
  g.fillStyle = "rgba(190,225,255,0.85)";
  ice.forEach((h, c) => { if (h > 2) g.fillRect(c, zpx(r.surf[c]), 1, Math.max(1, zpx(r.surf[c] - h) - zpx(r.surf[c]))); });
  void surf;
  // seismicity and sensors projected onto the section
  const W_km = +$("#sec-w").value, len = r.len, dx = (r.xb - r.xa) / len, dy = (r.yb - r.ya) / len;
  const proj = (lon, lat) => {
    const [x, y] = Sub.utm(lon, lat), along = (x - r.xa) * dx + (y - r.ya) * dy, perp = Math.abs(-(x - r.xa) * dy + (y - r.ya) * dx);
    return along >= 0 && along <= len && perp <= W_km * 1000 ? along : null;
  };
  sec.projected = [];
  if ($("#sec-events").checked) {
    for (const f of window.atlasData.events.features) {
      const a = proj(...f.geometry.coordinates);
      if (a === null) continue;
      const z = -f.properties.depth * 1000, px = (a / len) * (W - 1), py = zpx(z);
      if (py < 0 || py > H) continue;
      g.beginPath(); g.arc(px, py, (1.2 + 0.9 * Math.max(0, f.properties.mag)) * dpr, 0, 2 * Math.PI);
      g.fillStyle = "rgba(255,255,255,0.85)"; g.fill(); g.strokeStyle = "#0b0d10"; g.lineWidth = 0.8 * dpr; g.stroke();
      sec.projected.push({ px, py, f });
    }
  }
  for (const f of window.atlasData.sites.features) {
    if (f.properties.status !== "operating") continue;
    const a = proj(...f.geometry.coordinates);
    if (a === null) continue;
    const c = Math.round((a / len) * (W - 1)), py = zpx(r.surf[Math.min(W - 1, c)]);
    g.fillStyle = f.properties.color; g.beginPath();
    g.moveTo(c, py - 9 * dpr); g.lineTo(c - 5 * dpr, py - 1 * dpr); g.lineTo(c + 5 * dpr, py - 1 * dpr); g.closePath(); g.fill();
  }
  // axes
  const span = (r.zmax - r.zmin) / 1000, step = span > 15 ? 5 : span > 6 ? 2 : 1;
  const ticks = [];
  for (let z = Math.ceil(r.zmin / 1000 / step) * step; z <= r.zmax / 1000; z += step) ticks.push(z);
  $("#sec-yaxis").innerHTML = ticks.map((z) => `<div style="top:${(zpx(z * 1000) / H) * 100}%">${z} km</div>`).join("");
  const ve = (len / W) / ((r.zmax - r.zmin) / H);
  $("#sec-meta").textContent = `${Sub.meta().vars[name].label} · ${(len / 1000).toFixed(1)} km long · ` +
    `elevation (NAVD88) · vertical exaggeration ×${ve.toFixed(1)} · ice from IceBoost v2 · white dots: PNSN events within ${W_km} km`;
  $("#sec-cbar").innerHTML = Sub.colorbar(name);
  if (window.Underground && window.Underground.isOpen()) window.Underground.refresh();
}

function wireSubsurface(map, S, FAM) {
  $("#presets").innerHTML = PRESETS.map((p, i) => `<button class="btn" data-p="${i}">${p[0]}</button>`).join("");
  $("#presets").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const p = PRESETS[+b.dataset.p];
    const found = state.sections.find((x) => x.name === p[0]);
    if (found) { state.active = found; map.getSource("sections").setData(sectionFeatures()); renderSection(found); }
    else addSection(map, p[0], p[1], p[2]);
  });
  const rerender = () => {
    if (state.active) renderSection(state.active);
    if (state.sliceOn) updateSlice(map, S);
    if (window.Underground && window.Underground.isOpen()) window.Underground.refresh();
  };
  $("#sub-var").addEventListener("change", (e) => { state.subVar = e.target.value; rerender(); });
  $("#sub-model").addEventListener("change", (e) => { state.subModel = e.target.value; rerender(); });
  $("#sub-zmin").addEventListener("change", (e) => { state.zmin = +e.target.value; rerender(); });
  $("#sec-events").addEventListener("change", () => state.active && renderSection(state.active));
  $("#sec-w").addEventListener("change", () => state.active && renderSection(state.active));
  $("#sec-close").addEventListener("click", () => $("#section-panel").classList.add("hidden"));
  $("#draw-section").addEventListener("click", () => {
    state.draw = state.draw ? null : [];
    $("#draw-section").classList.toggle("on", !!state.draw);
    $("#draw-section").textContent = state.draw ? "Click point A on the map…" : "✎ Draw a section (click A, then B)";
    map.getCanvas().style.cursor = state.draw ? "crosshair" : "";
  });
  map.on("click", (e) => {
    if (!state.draw) return;
    state.draw.push([e.lngLat.lng, e.lngLat.lat]);
    if (state.draw.length === 1) { $("#draw-section").textContent = "Click point B…"; return; }
    const [A, B] = state.draw;
    state.draw = null;
    $("#draw-section").classList.remove("on");
    $("#draw-section").textContent = "✎ Draw a section (click A, then B)";
    map.getCanvas().style.cursor = "";
    addSection(map, "user section", A, B);
  });
  // readout on the section
  $("#sec-over").addEventListener("mousemove", (e) => {
    const sec = state.active, r = sec && sec.result; if (!r) return;
    const rect = e.target.getBoundingClientRect(), W = r.width, H = r.height;
    const c = Math.round(((e.clientX - rect.left) / rect.width) * (W - 1)), row = Math.round(((e.clientY - rect.top) / rect.height) * (H - 1));
    const z = r.zmax - (row / (H - 1)) * (r.zmax - r.zmin), d = (c / (W - 1)) * r.len, v = r.vals[row * W + c];
    const m = Sub.meta(), vv = m.vars[r.name];
    const txt = Number.isNaN(v) ? "air" : vv.categorical ? (m.units[v] || v) : `${v.toFixed(vv.vmax > 50 ? 0 : 2)} ${vv.units}`;
    $("#sec-read").textContent = `distance ${(d / 1000).toFixed(2)} km · elevation ${(z / 1000).toFixed(2)} km · ${vv.label} ${txt}`;
    const ev = (sec.projected || []).find((p) => Math.hypot(p.px - c, p.py - row) < 6);
    if (ev) $("#sec-read").textContent += ` · M${fmt(ev.f.properties.mag, 1)} at ${fmt(ev.f.properties.depth, 1)} km depth`;
  });
  // depth slice on the map
  map.addSource("slice", { type: "image", url: blankPNG(), coordinates: S_corners() });
  map.addLayer({ id: "slice", type: "raster", source: "slice", layout: { visibility: "none" },
    paint: { "raster-opacity": 0.85, "raster-fade-duration": 0 } }, "domain");
  $("#lyr-slice").addEventListener("change", (e) => { state.sliceOn = e.target.checked; setVis(map, "slice", state.sliceOn);
    if (state.sliceOn) updateSlice(map, S); });
  $("#slice-z").addEventListener("input", (e) => { state.sliceZ = +e.target.value;
    $("#slice-lbl").textContent = `${(state.sliceZ / 1000).toFixed(2)} km`; });
  $("#slice-z").addEventListener("change", () => { if (state.sliceOn) updateSlice(map, S);
    if (window.Underground && window.Underground.isOpen()) window.Underground.refresh(); });
  $("#open-ug").addEventListener("click", () => {
    if (!state.sections.length) addSection(map, PRESETS[0][0], PRESETS[0][1], PRESETS[0][2]);
    window.Underground.open();
  });
  Sub.init();
}

function S_corners() {
  const m = window.atlasData.S.domain_bbox;
  return [[m[0], m[3]], [m[2], m[3]], [m[2], m[1]], [m[0], m[1]]];
}
function blankPNG() {
  const c = document.createElement("canvas"); c.width = c.height = 1; return c.toDataURL();
}
async function updateSlice(map, S) {
  await Sub.init();
  const r = await Sub.slice(subName(), state.sliceZ, 250);
  map.getSource("slice").updateImage({ url: r.canvas.toDataURL(), coordinates: Sub.meta().surface.corners_lonlat });
  void S;
}

// Phone layout: the dock opens one panel at a time as a bottom sheet (CSS reads <html data-sheet>);
// the underground controls fold to their title row so the 3D view stays visible.
(function wireDock() {
  const root = document.documentElement;
  const buttons = [...document.querySelectorAll("#dock button")];
  const set = (s) => {
    root.dataset.sheet = s || "";
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.sheet === s)));
  };
  buttons.forEach((b) => b.addEventListener("click", () => set(root.dataset.sheet === b.dataset.sheet ? "" : b.dataset.sheet)));
  const fold = document.getElementById("ug-fold"), ug = document.getElementById("ug-controls");
  if (fold && ug) {
    if (matchMedia("(max-width: 700px)").matches) ug.classList.add("folded");
    fold.addEventListener("click", () => ug.classList.toggle("folded"));
  }
})();
