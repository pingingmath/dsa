/* Lahore Transit Simulation - NO LEAFLET (SVG Renderer) */

// ===================== REACT DEVTOOLS FIX =====================
if (typeof window !== "undefined") {
  if (
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__ &&
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__.overrideMethod
  ) {
    const originalOverrideMethod =
      window.__REACT_DEVTOOLS_GLOBAL_HOOK__.overrideMethod;
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__.overrideMethod = function (
      obj,
      methodName,
      fn
    ) {
      try {
        return originalOverrideMethod.call(this, obj, methodName, fn);
      } catch (error) {
        console.warn(
          "React DevTools overrideMethod error caught:",
          error.message
        );
        return function () {};
      }
    };
  }

  if (!window.initSimulation) {
    window.initSimulation = function () {
      console.log(
        "initSimulation called by React DevTools - Simulation is ready"
      );
      return Promise.resolve();
    };
  }
}

console.log("Simulation script loaded - NO LEAFLET (SVG Renderer)");

// ===================== GLOBALS =====================
const LAHORE_CENTER = [31.5204, 74.3587];
// numeric bounds (no Leaflet)
const LAHORE_BOUNDS = {
  minLat: 31.3,
  minLng: 74.1,
  maxLat: 31.7,
  maxLng: 74.55,
};

// Simulation state
let ROUTES = [];
let GRAPH = { nodes: [], edges: [] };
let coordsBase = new Map(); // stop -> {lat,lng}
let coords = new Map(); // stop -> {lat,lng}

// SVG rendering state (replaces Leaflet)
const SVG_NS = "http://www.w3.org/2000/svg";
let mapEl = null;
let svg = null;
let gEdges = null;
let gWeights = null;
let gStops = null;
let gBus = null;

let stopMarkers = new Map(); // stop -> {g,circle,icon,label}
let edgeLines = new Map(); // key -> {base,glow,weightText}
let weightMarkers = new Map(); // key -> weight <text>
let busMarker = null; // <text>
let busTrail = null; // <polyline>

let hasInitialized = false;

// “camera” for SVG (simple fit + zoom)
let view = {
  centerLat: LAHORE_CENTER[0],
  centerLng: LAHORE_CENTER[1],
  scale: 1, // px per degree
};

let isPaused = false;
let busAnimationRaf = null;

// Dijkstra state
let settledOrder = [];
let path = [];
let totalDistance = null;

// DOM Elements
let startSelect, endSelect, computeBtn, stopBtn, pauseBtn, playBtn, swapBtn;
let simMsg, searchStop;
let tGrid, tWeights, tLabels, tExplored, tSatellite, tAutoConnect;
let resetLayoutBtn, saveLayoutBtn, autoConnectBtn, clearRouteBtn;
let kpiDistance,
  kpiStops,
  kpiConnections,
  kpiStatus,
  netPill,
  routePill,
  stopCount;
let speedSlider, speedValue;
let zoomInBtn, zoomOutBtn, fitBoundsBtn, zoomLevel;

// small helpers
function $(id) {
  return document.getElementById(id);
}
function isChecked(el, fallback = false) {
  return el ? !!el.checked : fallback;
}
function safeText(el, text) {
  if (el) el.textContent = text;
}

// ===================== DOM INIT =====================
function initializeDOMReferences() {
  console.log("Initializing DOM references...");

  startSelect = $("startSelect");
  endSelect = $("endSelect");
  computeBtn = $("computeBtn");
  stopBtn = $("stopBtn");
  pauseBtn = $("pauseBtn");
  playBtn = $("playBtn");
  swapBtn = $("swapBtn");
  simMsg = $("simMsg");
  searchStop = $("searchStop");

  tGrid = $("tGrid");
  tWeights = $("tWeights");
  tLabels = $("tLabels");
  tExplored = $("tExplored");
  tSatellite = $("tSatellite");
  tAutoConnect = $("tAutoConnect");

  resetLayoutBtn = $("resetLayoutBtn");
  saveLayoutBtn = $("saveLayoutBtn");
  autoConnectBtn = $("autoConnectBtn");
  clearRouteBtn = $("clearRouteBtn");

  kpiDistance = $("kpiDistance");
  kpiStops = $("kpiStops");
  kpiConnections = $("kpiConnections");
  kpiStatus = $("kpiStatus");
  netPill = $("netPill");
  routePill = $("routePill");
  stopCount = $("stopCount");

  speedSlider = $("speed");
  speedValue = $("speedValue");

  zoomInBtn = $("zoomInBtn");
  zoomOutBtn = $("zoomOutBtn");
  fitBoundsBtn = $("fitBoundsBtn");
  zoomLevel = $("zoomLevel");

  mapEl = $("map");

  console.log("DOM references initialized");
}

function setMsg(el, text, isErr = false) {
  if (!el) return;
  el.textContent = text;
  el.style.color = isErr ? "#fecaca" : "#94a3b8";
}

function setKpis({ distance, stops, connections, status }) {
  if (kpiDistance) {
    kpiDistance.textContent =
      distance == null
        ? "—"
        : `${(Math.round(distance * 100) / 100).toFixed(2)} km`;
  }
  if (kpiStops) kpiStops.textContent = stops == null ? "0" : String(stops);
  if (kpiConnections)
    kpiConnections.textContent =
      connections == null ? "0" : String(connections);
  if (kpiStatus) kpiStatus.textContent = status || "🟢 Idle";
  if (stopCount) stopCount.textContent = stops == null ? "0" : String(stops);
}

// ===================== SVG "MAP" SETUP (NO LEAFLET) =====================
function injectStylesOnce() {
  if (document.getElementById("sim-svg-styles")) return;
  const style = document.createElement("style");
  style.id = "sim-svg-styles";
  style.textContent = `
    #map { position: relative; overflow: hidden; background: #0b1220; }
    #map.satellite { background: radial-gradient(circle at 30% 20%, #0f172a, #050814 60%); }

    .edge-base { stroke: #0f172a; stroke-width: 14; stroke-linecap: round; opacity: 0.55; }
    .edge-glow { stroke: #2563eb; stroke-width: 9; stroke-linecap: round; opacity: 0.85; }
    .edge-base.path { stroke: #0f766e; stroke-width: 18; opacity: 0.50; }
    .edge-glow.path { stroke: #10b981; stroke-width: 12; opacity: 0.95; }

    .weight-text { fill: #e5e7eb; font: 600 12px ui-sans-serif, system-ui; paint-order: stroke; stroke: rgba(0,0,0,0.55); stroke-width: 3px; }

    .stop { cursor: grab; }
    .stop:active { cursor: grabbing; }
    .stop-circle { fill: #1d4ed8; stroke: rgba(255,255,255,0.25); stroke-width: 2px; }
    .stop-circle.start { fill: #f59e0b; }
    .stop-circle.end { fill: #ef4444; }
    .stop-circle.path { fill: #10b981; }
    .stop-circle.explored { fill: #7c3aed; }

    .stop-icon { fill: white; font: 700 16px ui-sans-serif, system-ui; pointer-events: none; }
    .stop-label { fill: #e5e7eb; font: 600 12px ui-sans-serif, system-ui; paint-order: stroke; stroke: rgba(0,0,0,0.65); stroke-width: 3px; pointer-events: none; }

    .bus { font: 700 26px ui-sans-serif, system-ui; pointer-events: none; }
    .trail { fill: none; stroke: #f59e0b; stroke-width: 5; opacity: 0.6; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 8 12; }
  `;
  document.head.appendChild(style);
}

function createSvgEl(name) {
  return document.createElementNS(SVG_NS, name);
}

function getSvgSize() {
  if (!mapEl) return { w: 1, h: 1 };
  const r = mapEl.getBoundingClientRect();
  return { w: Math.max(1, r.width), h: Math.max(1, r.height) };
}

function worldToScreen(lat, lng) {
  const { w, h } = getSvgSize();
  const x = (lng - view.centerLng) * view.scale + w / 2;
  const y = (view.centerLat - lat) * view.scale + h / 2;
  return { x, y };
}

function screenToWorld(x, y) {
  const { w, h } = getSvgSize();
  const lng = (x - w / 2) / view.scale + view.centerLng;
  const lat = view.centerLat - (y - h / 2) / view.scale;
  return { lat, lng };
}

function initMap() {
  // This function name kept so the rest of your app flow stays the same,
  // but it now initializes SVG, not Leaflet.
  injectStylesOnce();

  if (!mapEl) {
    console.error("Map container (#map) not found!");
    return;
  }

  // wipe any previous children
  mapEl.innerHTML = "";
  mapEl.classList.toggle("satellite", isChecked(tSatellite, false));

  svg = createSvgEl("svg");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Transit network map");

  // layers
  gEdges = createSvgEl("g");
  gWeights = createSvgEl("g");
  gStops = createSvgEl("g");
  gBus = createSvgEl("g");

  svg.appendChild(gEdges);
  svg.appendChild(gWeights);
  svg.appendChild(gStops);
  svg.appendChild(gBus);

  mapEl.appendChild(svg);

  // keep zoom readout updated
  updateZoomLevel();

  // auto re-fit/re-render on resize
  const ro = new ResizeObserver(() => {
    // keep view center; just rerender
    renderEdges();
    renderStops();
    updateBusVisual();
  });
  ro.observe(mapEl);

  console.log("SVG map initialized");
}

function updateZoomLevel() {
  if (!zoomLevel) return;
  // show as "x" zoom rather than Leaflet integer zoom
  // base scale is arbitrary; we show relative to fit scale if available
  zoomLevel.textContent = `${view.scale.toFixed(0)} px/°`;
}

// ===================== STOP / EDGE RENDERING (SVG) =====================
function clearGroup(g) {
  if (!g) return;
  while (g.firstChild) g.removeChild(g.firstChild);
}

function renderStops() {
  console.log("Rendering stops (SVG)...");
  if (!svg || !gStops) return;

  stopMarkers.clear();
  clearGroup(gStops);

  if (!GRAPH.nodes || GRAPH.nodes.length === 0) return;

  GRAPH.nodes.forEach((stopName) => {
    const c = coords.get(stopName);
    if (!c || typeof c.lat !== "number" || typeof c.lng !== "number") return;

    const { x, y } = worldToScreen(c.lat, c.lng);

    const g = createSvgEl("g");
    g.setAttribute("class", "stop");
    g.dataset.stop = stopName;

    const circle = createSvgEl("circle");
    circle.setAttribute("cx", String(x));
    circle.setAttribute("cy", String(y));
    circle.setAttribute("r", "18");
    circle.setAttribute("class", "stop-circle");

    const icon = createSvgEl("text");
    icon.setAttribute("x", String(x));
    icon.setAttribute("y", String(y + 5));
    icon.setAttribute("text-anchor", "middle");
    icon.setAttribute("class", "stop-icon");
    icon.textContent = "🏢";

    const label = createSvgEl("text");
    label.setAttribute("x", String(x));
    label.setAttribute("y", String(y - 26));
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "stop-label");
    label.textContent = stopName;

    g.appendChild(circle);
    g.appendChild(icon);
    g.appendChild(label);
    gStops.appendChild(g);

    stopMarkers.set(stopName, { g, circle, icon, label });

    // click to select
    g.addEventListener("click", () => {
      if (!startSelect?.value) startSelect.value = stopName;
      else if (!endSelect?.value) endSelect.value = stopName;
      else {
        startSelect.value = endSelect.value;
        endSelect.value = stopName;
      }
      updateStopIcons();
      setMsg(simMsg, `Selected ${stopName}`, false);
    });

    // pointer-drag
    enableStopDragging(stopName);
  });

  updateStopIcons();
  console.log(`Rendered ${stopMarkers.size} stops`);
}

let dragState = {
  dragging: false,
  stopName: null,
  pointerId: null,
};

function enableStopDragging(stopName) {
  const entry = stopMarkers.get(stopName);
  if (!entry) return;

  const { g } = entry;

  g.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    dragState.dragging = true;
    dragState.stopName = stopName;
    dragState.pointerId = e.pointerId;
    g.setPointerCapture(e.pointerId);
  });

  g.addEventListener("pointermove", (e) => {
    if (!dragState.dragging || dragState.stopName !== stopName) return;

    const rect = mapEl.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const w = screenToWorld(x, y);

    const old = coords.get(stopName);
    if (!old) return;

    coords.set(stopName, { lat: w.lat, lng: w.lng });

    // update this stop position live
    updateSingleStopPosition(stopName);
    // update edges live
    renderEdges();
    // keep selection/path coloring
    updateStopIcons();
  });

  const endDrag = (e) => {
    if (!dragState.dragging || dragState.stopName !== stopName) return;
    dragState.dragging = false;
    dragState.stopName = null;
    dragState.pointerId = null;

    setMsg(simMsg, `Moved ${stopName} to new location`, false);
  };

  g.addEventListener("pointerup", endDrag);
  g.addEventListener("pointercancel", endDrag);
}

function updateSingleStopPosition(stopName) {
  const entry = stopMarkers.get(stopName);
  const c = coords.get(stopName);
  if (!entry || !c) return;

  const { x, y } = worldToScreen(c.lat, c.lng);

  entry.circle.setAttribute("cx", String(x));
  entry.circle.setAttribute("cy", String(y));
  entry.icon.setAttribute("x", String(x));
  entry.icon.setAttribute("y", String(y + 5));
  entry.label.setAttribute("x", String(x));
  entry.label.setAttribute("y", String(y - 26));
}

function updateStopIcons() {
  stopMarkers.forEach((entry, stopName) => {
    let type = "normal";
    if (stopName === startSelect?.value) type = "start";
    else if (stopName === endSelect?.value) type = "end";
    else if (path.includes(stopName)) type = "path";
    else if (settledOrder.includes(stopName) && isChecked(tExplored, false))
      type = "explored";

    entry.circle.setAttribute(
      "class",
      `stop-circle${type === "normal" ? "" : " " + type}`
    );

    // label visibility
    entry.label.style.opacity = isChecked(tLabels, true) ? "1" : "0";
  });
}

function renderEdges() {
  console.log("Rendering edges (SVG)...");
  if (!svg || !gEdges || !gWeights) return;

  edgeLines.clear();
  weightMarkers.clear();
  clearGroup(gEdges);
  clearGroup(gWeights);

  if (!isChecked(tGrid, true) || !GRAPH.edges || GRAPH.edges.length === 0)
    return;

  GRAPH.edges.forEach((edge) => {
    const fromCoord = coords.get(edge.from);
    const toCoord = coords.get(edge.to);
    if (!fromCoord || !toCoord) return;

    const a = worldToScreen(fromCoord.lat, fromCoord.lng);
    const b = worldToScreen(toCoord.lat, toCoord.lng);

    const isPathEdge = path.some((stop, idx) => {
      if (idx === path.length - 1) return false;
      return (
        (stop === edge.from && path[idx + 1] === edge.to) ||
        (stop === edge.to && path[idx + 1] === edge.from)
      );
    });

    const base = createSvgEl("line");
    base.setAttribute("x1", String(a.x));
    base.setAttribute("y1", String(a.y));
    base.setAttribute("x2", String(b.x));
    base.setAttribute("y2", String(b.y));
    base.setAttribute("class", `edge-base${isPathEdge ? " path" : ""}`);

    const glow = createSvgEl("line");
    glow.setAttribute("x1", String(a.x));
    glow.setAttribute("y1", String(a.y));
    glow.setAttribute("x2", String(b.x));
    glow.setAttribute("y2", String(b.y));
    glow.setAttribute("class", `edge-glow${isPathEdge ? " path" : ""}`);

    gEdges.appendChild(base);
    gEdges.appendChild(glow);

    const key = `${edge.from}-${edge.to}`;
    edgeLines.set(key, { base, glow });

    if (isChecked(tWeights, false)) {
      const dist =
        typeof edge.w === "number"
          ? edge.w
          : calculateDistance(
              fromCoord.lat,
              fromCoord.lng,
              toCoord.lat,
              toCoord.lng
            );

      const midX = (a.x + b.x) / 2;
      const midY = (a.y + b.y) / 2;

      const t = createSvgEl("text");
      t.setAttribute("x", String(midX));
      t.setAttribute("y", String(midY));
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("class", "weight-text");
      t.textContent = `${dist.toFixed(2)} km`;

      gWeights.appendChild(t);
      weightMarkers.set(key, t);
    }
  });

  console.log(`Rendered ${GRAPH.edges.length} edges`);
}

// ===================== GEOMETRY =====================
function calculateDistance(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function computePathDistance(pathStops) {
  if (!Array.isArray(pathStops) || pathStops.length < 2) return 0;
  let distance = 0;

  for (let i = 0; i < pathStops.length - 1; i++) {
    const from = pathStops[i];
    const to = pathStops[i + 1];
    const edge = GRAPH.edges.find(
      (e) =>
        (e.from === from && e.to === to) || (e.from === to && e.to === from)
    );

    if (edge && typeof edge.w === "number") distance += edge.w;
    else {
      const a = coords.get(from);
      const b = coords.get(to);
      if (a && b) distance += calculateDistance(a.lat, a.lng, b.lat, b.lng);
    }
  }
  return distance;
}

// ===================== DATA LOADING =====================
async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok)
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  return await response.json();
}

async function loadSimulationData() {
  console.log("Loading simulation data...");
  setMsg(simMsg, "Loading simulation data...");

  try {
    const routesData = await fetchJSON("/api/sim/routes");
    ROUTES = routesData.routes || [];
    console.log("Routes loaded:", ROUTES);

    const graphData = await fetchJSON("/api/sim/graph");
    console.log("Graph data loaded:", graphData);

    await processData(routesData, graphData);

    safeText(
      netPill,
      `Network: ${GRAPH.nodes.length} stops · ${GRAPH.edges.length} routes`
    );
    populateDropdowns();

    // view should fit data
    fitBoundsToStops();

    renderStops();
    renderEdges();

    setMsg(
      simMsg,
      `Loaded ${GRAPH.nodes.length} stops and ${GRAPH.edges.length} routes`
    );
    setKpis({
      distance: null,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🟢 Ready",
    });

    console.log("Data loaded successfully");
  } catch (error) {
    console.error("Failed to load simulation data:", error);
    setMsg(simMsg, `Error loading data: ${error.message}`, true);
    setKpis({
      distance: null,
      stops: null,
      connections: null,
      status: "🔴 Error",
    });

    createStableTestData();
  }
}

async function processData(routesData, graphData) {
  console.log("Processing data...");

  GRAPH = { nodes: [], edges: [] };
  coordsBase.clear();
  coords.clear();

  if (graphData.nodes && graphData.nodes.length > 0) {
    processGraphNodes(graphData.nodes);
  } else if (ROUTES.length > 0) {
    extractNodesFromRoutes();
  }

  // ensure coords exist before edges (so edge weights can compute)
  ensureStableCoordinates();

  if (graphData.edges && graphData.edges.length > 0) {
    processGraphEdges(graphData.edges);
  } else if (ROUTES.length > 0) {
    createStableEdgesFromRoutes();
  }

  // final safety
  ensureStableCoordinates();

  console.log("Final graph:", GRAPH);
}

function processGraphNodes(nodes) {
  const centerLat = LAHORE_CENTER[0];
  const centerLng = LAHORE_CENTER[1];
  const radius = 0.01;

  nodes.forEach((node, index) => {
    let nodeName;

    if (typeof node === "string") nodeName = node.trim();
    else if (typeof node === "object" && node) {
      nodeName = (node.name || node.id || `Stop_${index + 1}`)
        .toString()
        .trim();
    }

    if (!nodeName || GRAPH.nodes.includes(nodeName)) return;

    GRAPH.nodes.push(nodeName);

    const angle = (index * 2 * Math.PI) / Math.max(1, nodes.length);
    const dist = radius * (0.5 + Math.random() * 0.5);
    const fallbackLat = centerLat + Math.cos(angle) * dist;
    const fallbackLng = centerLng + Math.sin(angle) * dist;

    coords.set(nodeName, { lat: fallbackLat, lng: fallbackLng });
    coordsBase.set(nodeName, { lat: fallbackLat, lng: fallbackLng });
  });
}

function extractNodesFromRoutes() {
  const nodeSet = new Set();
  ROUTES.forEach((route) => {
    if (Array.isArray(route.stops)) {
      route.stops.forEach((s) => {
        if (typeof s === "string" && s.trim()) nodeSet.add(s.trim());
      });
    }
  });
  GRAPH.nodes = Array.from(nodeSet);
}

function processGraphEdges(edges) {
  edges.forEach((edge) => {
    if (!edge?.from || !edge?.to) return;
    if (!GRAPH.nodes.includes(edge.from) || !GRAPH.nodes.includes(edge.to))
      return;

    const exists = GRAPH.edges.some(
      (e) =>
        (e.from === edge.from && e.to === edge.to) ||
        (e.from === edge.to && e.to === edge.from)
    );
    if (exists) return;

    const a = coords.get(edge.from);
    const b = coords.get(edge.to);
    if (!a || !b) return;

    const distance =
      typeof edge.w === "number"
        ? edge.w
        : calculateDistance(a.lat, a.lng, b.lat, b.lng);

    GRAPH.edges.push({ from: edge.from, to: edge.to, w: distance });
  });
}

function createStableEdgesFromRoutes() {
  const edgeSet = new Set();

  ROUTES.forEach((route) => {
    if (!Array.isArray(route.stops)) return;

    for (let i = 0; i < route.stops.length - 1; i++) {
      const fromStop = route.stops[i]?.toString().trim();
      const toStop = route.stops[i + 1]?.toString().trim();

      if (!fromStop || !toStop || fromStop === toStop) continue;
      if (!GRAPH.nodes.includes(fromStop) || !GRAPH.nodes.includes(toStop))
        continue;

      const k = `${fromStop}-${toStop}`;
      const rk = `${toStop}-${fromStop}`;
      if (edgeSet.has(k) || edgeSet.has(rk)) continue;

      const a = coords.get(fromStop);
      const b = coords.get(toStop);
      if (!a || !b) continue;

      const distance = calculateDistance(a.lat, a.lng, b.lat, b.lng);
      GRAPH.edges.push({ from: fromStop, to: toStop, w: distance });
      edgeSet.add(k);
    }
  });
}

function ensureStableCoordinates() {
  const centerLat = LAHORE_CENTER[0];
  const centerLng = LAHORE_CENTER[1];
  const baseRadius = 0.005;

  GRAPH.nodes.forEach((nodeName, index) => {
    const c = coords.get(nodeName);
    if (c && typeof c.lat === "number" && typeof c.lng === "number") return;

    const angle = (index * 2 * Math.PI) / Math.max(1, GRAPH.nodes.length);
    const dist = baseRadius * (0.3 + Math.random() * 0.7);
    const lat = centerLat + Math.cos(angle) * dist;
    const lng = centerLng + Math.sin(angle) * dist;

    coords.set(nodeName, { lat, lng });
    if (!coordsBase.has(nodeName)) coordsBase.set(nodeName, { lat, lng });
  });
}

function createStableTestData() {
  console.log("Creating stable test data...");

  GRAPH.nodes = ["Bus Stop 1", "Bus Stop 2", "Bus Stop 3", "Bus Stop 4"];

  const centerLat = LAHORE_CENTER[0];
  const centerLng = LAHORE_CENTER[1];
  const radius = 0.003;

  GRAPH.nodes.forEach((stopName, index) => {
    const angle = (index * 2 * Math.PI) / GRAPH.nodes.length;
    const lat = centerLat + Math.cos(angle) * radius;
    const lng = centerLng + Math.sin(angle) * radius;
    coords.set(stopName, { lat, lng });
    coordsBase.set(stopName, { lat, lng });
  });

  GRAPH.edges = [
    { from: "Bus Stop 1", to: "Bus Stop 2", w: 0.5 },
    { from: "Bus Stop 2", to: "Bus Stop 3", w: 0.5 },
    { from: "Bus Stop 3", to: "Bus Stop 4", w: 0.5 },
    { from: "Bus Stop 4", to: "Bus Stop 1", w: 0.5 },
  ];

  safeText(
    netPill,
    `Network: ${GRAPH.nodes.length} stops · ${GRAPH.edges.length} routes (Test)`
  );

  populateDropdowns();
  fitBoundsToStops();
  renderStops();
  renderEdges();
  setMsg(simMsg, "Using test data. Server endpoints not reachable.", true);
}

function populateDropdowns() {
  if (!startSelect || !endSelect) return;

  startSelect.innerHTML = '<option value="">Select start</option>';
  endSelect.innerHTML = '<option value="">Select destination</option>';

  GRAPH.nodes.forEach((stopName) => {
    const a = document.createElement("option");
    a.value = stopName;
    a.textContent = stopName;
    startSelect.appendChild(a);

    const b = document.createElement("option");
    b.value = stopName;
    b.textContent = stopName;
    endSelect.appendChild(b);
  });

  if (GRAPH.nodes.length >= 2) {
    startSelect.value = GRAPH.nodes[0];
    endSelect.value = GRAPH.nodes[1];
  }
}

// ===================== VIEW CONTROLS (FIT / ZOOM) =====================
function fitBoundsToStops() {
  if (!GRAPH.nodes || GRAPH.nodes.length === 0) return;

  let minLat = Infinity,
    maxLat = -Infinity,
    minLng = Infinity,
    maxLng = -Infinity;

  GRAPH.nodes.forEach((name) => {
    const c = coords.get(name);
    if (!c) return;
    minLat = Math.min(minLat, c.lat);
    maxLat = Math.max(maxLat, c.lat);
    minLng = Math.min(minLng, c.lng);
    maxLng = Math.max(maxLng, c.lng);
  });

  if (!isFinite(minLat) || !isFinite(minLng)) return;

  // pad bounds a bit
  const padLat = (maxLat - minLat) * 0.15 || 0.01;
  const padLng = (maxLng - minLng) * 0.15 || 0.01;
  minLat -= padLat;
  maxLat += padLat;
  minLng -= padLng;
  maxLng += padLng;

  const { w, h } = getSvgSize();
  const padPx = 40;

  const scaleX = (w - padPx * 2) / Math.max(1e-9, maxLng - minLng);
  const scaleY = (h - padPx * 2) / Math.max(1e-9, maxLat - minLat);
  view.scale = Math.min(scaleX, scaleY);

  view.centerLat = (minLat + maxLat) / 2;
  view.centerLng = (minLng + maxLng) / 2;

  updateZoomLevel();
}

// ===================== ROUTE COMPUTATION =====================
async function computeRoute() {
  const start = startSelect?.value;
  const end = endSelect?.value;

  if (!start || !end) {
    setMsg(simMsg, "Please select both start and destination stops", true);
    return;
  }
  if (start === end) {
    setMsg(simMsg, "Start and destination cannot be the same", true);
    return;
  }

  setMsg(simMsg, "Computing shortest path...");
  setKpis({
    distance: null,
    stops: GRAPH.nodes.length,
    connections: GRAPH.edges.length,
    status: "🟡 Computing",
  });

  try {
    const result = await fetchJSON("/api/sim/path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start, end }),
    });

    settledOrder = result.settled_order || [];
    path = result.path || [];
    totalDistance = result.distance || null;

    if (path.length === 0) {
      setMsg(simMsg, "No path found between selected stops", true);
      setKpis({
        distance: null,
        stops: GRAPH.nodes.length,
        connections: GRAPH.edges.length,
        status: "🔴 No route",
      });
      updateStopIcons();
      renderEdges();
      return;
    }

    if (totalDistance == null) totalDistance = computePathDistance(path);

    safeText(routePill, `Path: ${path[0]} → ${path[path.length - 1]}`);
    setMsg(
      simMsg,
      `Found path: ${path.join(" → ")} | Distance: ${totalDistance?.toFixed(
        2
      )} km`
    );

    setKpis({
      distance: totalDistance,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🟢 Path found",
    });

    updateStopIcons();
    renderEdges();
    animateBusAlongPath();
  } catch (error) {
    console.error("Route computation error:", error);
    setMsg(
      simMsg,
      `Error computing route (server). Using client-side Dijkstra...`,
      true
    );
    computeClientSideRoute(start, end);
  }
}

function computeClientSideRoute(start, end) {
  console.log("Computing route client-side...");

  const distances = {};
  const previous = {};
  const unvisited = new Set(GRAPH.nodes);

  GRAPH.nodes.forEach((node) => {
    distances[node] = Infinity;
    previous[node] = null;
  });
  distances[start] = 0;
  settledOrder = [];

  while (unvisited.size > 0) {
    let current = null;
    let minDist = Infinity;

    unvisited.forEach((node) => {
      if (distances[node] < minDist) {
        minDist = distances[node];
        current = node;
      }
    });

    if (current === null || current === end) break;

    unvisited.delete(current);
    settledOrder.push(current);

    const neighbors = GRAPH.edges.filter(
      (edge) => edge.from === current || edge.to === current
    );

    neighbors.forEach((edge) => {
      const neighbor = edge.from === current ? edge.to : edge.from;
      if (!unvisited.has(neighbor)) return;

      const alt = distances[current] + edge.w;
      if (alt < distances[neighbor]) {
        distances[neighbor] = alt;
        previous[neighbor] = current;
      }
    });
  }

  path = [];
  totalDistance = distances[end];

  if (distances[end] !== Infinity) {
    let cur = end;
    while (cur !== null) {
      path.unshift(cur);
      cur = previous[cur];
    }
  }

  if (path.length > 0) {
    if (totalDistance === Infinity || totalDistance == null)
      totalDistance = computePathDistance(path);

    safeText(routePill, `Path: ${path[0]} → ${path[path.length - 1]}`);
    setMsg(
      simMsg,
      `Found path: ${path.join(" → ")} | Distance: ${
        totalDistance?.toFixed(2) || 0
      } km`
    );

    setKpis({
      distance: totalDistance,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🟢 Path found",
    });

    updateStopIcons();
    renderEdges();
    animateBusAlongPath();
  } else {
    setMsg(simMsg, "No path found between selected stops", true);
    setKpis({
      distance: null,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🔴 No route",
    });
    updateStopIcons();
    renderEdges();
  }
}

// ===================== BUS ANIMATION (SVG) =====================
function clearBus() {
  if (busAnimationRaf) {
    cancelAnimationFrame(busAnimationRaf);
    busAnimationRaf = null;
  }
  if (busMarker && busMarker.parentNode)
    busMarker.parentNode.removeChild(busMarker);
  if (busTrail && busTrail.parentNode)
    busTrail.parentNode.removeChild(busTrail);
  busMarker = null;
  busTrail = null;
}

function updateBusVisual() {
  // rerender positions after zoom/fit
  if (!busMarker || path.length < 1) return;
  // nothing else to do here; animation step updates position already
}

function animateBusAlongPath() {
  clearBus();
  if (!svg || !gBus) return;
  if (!Array.isArray(path) || path.length < 2) return;

  const startCoord = coords.get(path[0]);
  if (!startCoord) return;

  // bus marker
  busMarker = createSvgEl("text");
  busMarker.setAttribute("class", "bus");
  busMarker.textContent = "🚌";
  gBus.appendChild(busMarker);

  // trail polyline
  busTrail = createSvgEl("polyline");
  busTrail.setAttribute("class", "trail");
  gBus.appendChild(busTrail);

  const speed = parseFloat(speedSlider?.value || "1") || 1;
  let currentSegment = 0;
  let progress = 0;
  let lastTs = null;

  const trailPoints = [];

  const step = (ts) => {
    if (isPaused) {
      busAnimationRaf = requestAnimationFrame(step);
      return;
    }

    if (currentSegment >= path.length - 1) {
      busAnimationRaf = null;
      setMsg(simMsg, `Bus reached destination: ${path[path.length - 1]}`);
      setKpis({
        distance: totalDistance,
        stops: GRAPH.nodes.length,
        connections: GRAPH.edges.length,
        status: "🟢 Complete",
      });
      return;
    }

    if (!lastTs) lastTs = ts;
    const delta = ts - lastTs;
    lastTs = ts;

    const fromStop = path[currentSegment];
    const toStop = path[currentSegment + 1];
    const fromCoord = coords.get(fromStop);
    const toCoord = coords.get(toStop);

    if (!fromCoord || !toCoord) {
      currentSegment++;
      progress = 0;
      busAnimationRaf = requestAnimationFrame(step);
      return;
    }

    progress += (delta / 2000) * speed;
    if (progress >= 1) {
      progress = 0;
      currentSegment++;
      busAnimationRaf = requestAnimationFrame(step);
      return;
    }

    const lat = fromCoord.lat + (toCoord.lat - fromCoord.lat) * progress;
    const lng = fromCoord.lng + (toCoord.lng - fromCoord.lng) * progress;

    const p = worldToScreen(lat, lng);
    busMarker.setAttribute("x", String(p.x));
    busMarker.setAttribute("y", String(p.y));

    trailPoints.push(`${p.x},${p.y}`);
    if (trailPoints.length > 200) trailPoints.shift();
    busTrail.setAttribute("points", trailPoints.join(" "));

    const overallProgress =
      ((currentSegment + progress) / (path.length - 1)) * 100;
    setMsg(
      simMsg,
      `Bus: ${fromStop} → ${toStop} (${overallProgress.toFixed(0)}%)`
    );

    busAnimationRaf = requestAnimationFrame(step);
  };

  busAnimationRaf = requestAnimationFrame(step);
}

function clearRoute() {
  clearBus();
  path = [];
  settledOrder = [];
  totalDistance = null;

  updateStopIcons();
  renderEdges();
  safeText(routePill, "Path: Not Selected");

  setMsg(simMsg, "Route cleared");
  setKpis({
    distance: null,
    stops: GRAPH.nodes.length,
    connections: GRAPH.edges.length,
    status: "🟢 Idle",
  });
}

// ===================== EVENT HANDLERS =====================
function setupEventListeners() {
  console.log("Setting up event listeners...");

  computeBtn?.addEventListener("click", computeRoute);

  swapBtn?.addEventListener("click", () => {
    const temp = startSelect?.value;
    if (!startSelect || !endSelect) return;
    startSelect.value = endSelect.value;
    endSelect.value = temp;
    updateStopIcons();
    setMsg(simMsg, "Swapped start and destination");
  });

  playBtn?.addEventListener("click", () => {
    isPaused = false;
    if (pauseBtn) pauseBtn.textContent = "⏸️ Pause";
    setMsg(simMsg, "Resumed animation");
    setKpis({
      distance: totalDistance,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🟢 Running",
    });
  });

  pauseBtn?.addEventListener("click", () => {
    isPaused = !isPaused;
    if (pauseBtn) pauseBtn.textContent = isPaused ? "▶️ Resume" : "⏸️ Pause";
    setMsg(simMsg, isPaused ? "Paused animation" : "Resumed animation");
  });

  stopBtn?.addEventListener("click", () => {
    isPaused = false;
    clearRoute();
    setMsg(simMsg, "Stopped animation");
  });

  clearRouteBtn?.addEventListener("click", clearRoute);

  tGrid?.addEventListener("change", renderEdges);
  tWeights?.addEventListener("change", renderEdges);
  tLabels?.addEventListener("change", updateStopIcons);
  tExplored?.addEventListener("change", updateStopIcons);

  // "satellite" toggle becomes just a background style toggle (no tiles)
  tSatellite?.addEventListener("change", function () {
    if (!mapEl) return;
    mapEl.classList.toggle("satellite", !!this.checked);
  });

  speedSlider?.addEventListener("input", function () {
    safeText(speedValue, `${this.value}x`);
  });

  // Search
  searchStop?.addEventListener("input", function () {
    const query = (this.value || "").toLowerCase().trim();
    let firstMatch = null;

    stopMarkers.forEach((entry, stopName) => {
      if (!query) {
        entry.g.style.opacity = "1";
        return;
      }
      if (stopName.toLowerCase().includes(query)) {
        if (!firstMatch) firstMatch = stopName;
        entry.g.style.opacity = "1";
      } else {
        entry.g.style.opacity = "0.25";
      }
    });

    // optional: center view to first match
    if (firstMatch) {
      const c = coords.get(firstMatch);
      if (c) {
        view.centerLat = c.lat;
        view.centerLng = c.lng;
        renderEdges();
        renderStops();
        updateBusVisual();
      }
    }
  });

  searchStop?.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") return;
    const query = (this.value || "").toLowerCase().trim();
    if (!query) return;

    const match = GRAPH.nodes.find((name) =>
      name.toLowerCase().includes(query)
    );
    if (match) {
      if (!startSelect?.value) startSelect.value = match;
      else if (!endSelect?.value) endSelect.value = match;
      else endSelect.value = match;
      updateStopIcons();
    }
  });

  // Zoom controls (now control SVG view.scale)
  zoomInBtn?.addEventListener("click", () => {
    view.scale *= 1.2;
    updateZoomLevel();
    renderEdges();
    renderStops();
    updateBusVisual();
  });

  zoomOutBtn?.addEventListener("click", () => {
    view.scale /= 1.2;
    updateZoomLevel();
    renderEdges();
    renderStops();
    updateBusVisual();
  });

  fitBoundsBtn?.addEventListener("click", () => {
    fitBoundsToStops();
    renderEdges();
    renderStops();
    updateBusVisual();
  });

  resetLayoutBtn?.addEventListener("click", () => {
    coordsBase.forEach((c, stopName) => coords.set(stopName, { ...c }));
    fitBoundsToStops();
    renderStops();
    renderEdges();
    setMsg(simMsg, "Reset all stops to original positions");
  });

  saveLayoutBtn?.addEventListener("click", () => {
    coords.forEach((c, stopName) => coordsBase.set(stopName, { ...c }));
    setMsg(simMsg, "Saved current layout as default");
  });

  // Auto-connect (unchanged logic)
  autoConnectBtn?.addEventListener("click", function () {
    setMsg(simMsg, "Auto-connecting nearby stops...");

    const newEdges = [];
    const edgeSet = new Set();

    GRAPH.edges.forEach((e) => edgeSet.add(`${e.from}-${e.to}`));

    GRAPH.nodes.forEach((fromStop) => {
      GRAPH.nodes.forEach((toStop) => {
        if (fromStop === toStop) return;

        const k = `${fromStop}-${toStop}`;
        const rk = `${toStop}-${fromStop}`;
        if (edgeSet.has(k) || edgeSet.has(rk)) return;

        const a = coords.get(fromStop);
        const b = coords.get(toStop);
        if (!a || !b) return;

        const d = calculateDistance(a.lat, a.lng, b.lat, b.lng);
        if (d < 0.8) {
          newEdges.push({ from: fromStop, to: toStop, w: d });
          edgeSet.add(k);
        }
      });
    });

    GRAPH.edges.push(...newEdges);

    safeText(
      netPill,
      `Network: ${GRAPH.nodes.length} stops · ${GRAPH.edges.length} routes`
    );
    renderEdges();

    setMsg(simMsg, `Added ${newEdges.length} new connections`);
    setKpis({
      distance: totalDistance,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🟢 Updated",
    });
  });

  document.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "r") {
      event.preventDefault();
      computeRoute();
    }

    if (event.key === " " && !event.target.matches("input, textarea, select")) {
      event.preventDefault();
      if (busAnimationRaf) {
        isPaused = !isPaused;
        if (pauseBtn)
          pauseBtn.textContent = isPaused ? "▶️ Resume" : "⏸️ Pause";
        setMsg(simMsg, isPaused ? "Paused animation" : "Resumed animation");
      }
    }
  });

  console.log("Event listeners setup complete");
}

// ===================== INITIALIZATION =====================
async function initializeSimulation() {
  console.log("Initializing simulation...");

  try {
    if (hasInitialized) {
      console.warn("Simulation already initialized");
      return;
    }
    hasInitialized = true;

    initializeDOMReferences();
    initMap(); // SVG init
    setupEventListeners();
    await loadSimulationData();

    safeText(speedValue, `${speedSlider?.value || 1}x`);
    updateZoomLevel();

    setKpis({
      distance: null,
      stops: GRAPH.nodes.length,
      connections: GRAPH.edges.length,
      status: "🟢 Ready",
    });

    setMsg(simMsg, "Simulation ready. Select stops and compute route.");
    console.log("Simulation initialized successfully");
  } catch (error) {
    console.error("Initialization error:", error);
    setMsg(simMsg, `Initialization error: ${error.message}`, true);

    createStableTestData();
    setMsg(
      simMsg,
      "Using test data. Add your own stops or wait for server.",
      true
    );
  }
}

// ===================== START =====================
document.addEventListener("DOMContentLoaded", function () {
  console.log("DOM loaded, starting simulation...");
  setTimeout(initializeSimulation, 100);
});

window.initSimulation = initializeSimulation;

// Export for debugging
window.simulation = {
  GRAPH,
  coords,
  coordsBase,
  ROUTES,
  stopMarkers,
  edgeLines,
  weightMarkers,
  path,
  settledOrder,
  totalDistance,
  renderStops,
  renderEdges,
  updateStopIcons,
  clearRoute,
  computeRoute,
  calculateDistance,
  fitBoundsToStops,
  initializeSimulation,
};

console.log(
  "Lahore Transit Simulation script loaded - NO LEAFLET (SVG Renderer)"
);
