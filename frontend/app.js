// ── Strip markdown (** bold **, * italic *) ──
function stripMd(text) {
  if (!text) return "";
  return text.replace(/\*{1,3}([^*\n]*)\*{1,3}/g, "$1")
             .replace(/_{1,2}([^_\n]*)_{1,2}/g, "$1");
}

// ── Global state ──
let currentCalls = {};
let activecallId = null;
const markers = {};
const serviceMarkers = {};  // call.id → nearest service marker
const serviceLines = {};    // call.id → polyline

// ── Dispatch panel ──
const DISPATCH_SERVICES = [
  { type: "police",   emoji: "🚔", label: "POLICE",   color: "#3b82f6" },
  { type: "fire",     emoji: "🚒", label: "FIRE DEPT", color: "#ef4444" },
  { type: "hospital", emoji: "🏥", label: "MEDICAL",   color: "#22c55e" },
];

function updateDispatchPanel() {
  const panel = document.getElementById("dispatch-panel");
  if (!activecallId || !currentCalls[activecallId]) {
    panel.style.display = "none";
    return;
  }
  const call       = currentCalls[activecallId];
  const dispatched = call.dispatched_to || [];
  const nearest    = call.nearest_service;

  panel.style.display = "flex";

  // Titre de l'appel
  document.getElementById("dp-call-info").textContent =
    call.title || "Incident en cours";

  // Boutons de service
  document.getElementById("dp-services").innerHTML = DISPATCH_SERVICES.map(s => {
    const done = dispatched.includes(s.type);
    const dist = nearest?.type === s.type
      ? `${nearest.distance_km} km`
      : "";
    return `
      <div class="dp-btn${done ? " dp-dispatched" : ""}"
           style="--svc-color:${s.color}"
           onclick="dispatchService('${s.type}')">
        <div class="dp-btn-left">
          <span>${s.emoji} ${s.label}</span>
          ${dist ? `<span class="dp-dist">${dist}</span>` : ""}
        </div>
        <span class="dp-badge" style="color:${s.color};border-color:${s.color}">
          ${done ? "✓ SENT" : ""}
        </span>
        ${!done ? `<span class="dp-action">▶</span>` : ""}
      </div>`;
  }).join("");

  // Log des dispatchs
  const logEl = document.getElementById("dp-log");
  logEl.innerHTML = DISPATCH_SERVICES
    .filter(s => call[`dispatched_${s.type}_at`])
    .map(s => {
      const t = new Date(call[`dispatched_${s.type}_at`])
        .toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      return `<div class="dp-log-entry">
        <span class="dp-log-time">${t}</span>
        <span>${s.emoji} ${s.label} dispatched</span>
      </div>`;
    }).join("");
}

function dispatchService(serviceType) {
  if (!activecallId) return;
  const call = currentCalls[activecallId];
  if (!call) return;
  const dispatched = call.dispatched_to || [];
  if (dispatched.includes(serviceType)) return; // déjà dispatché

  // Optimistic update local
  call.dispatched_to = [...dispatched, serviceType];
  call[`dispatched_${serviceType}_at`] = new Date().toISOString();
  updateDispatchPanel();

  // Envoi au backend via WebSocket
  ws.send(JSON.stringify({
    type: "dispatch",
    call_id: activecallId,
    service: serviceType,
  }));
}

// ── Clock ──
const clockEl = document.getElementById("sl-clock");
function updateClock() {
  const now = new Date();
  clockEl.textContent = now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
updateClock();
setInterval(updateClock, 1000);

// ── Map ──
const map = L.map("map").setView([48.8566, 2.3522], 5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '© <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
  maxZoom: 19,
}).addTo(map);

// ── WebSocket ──
const ws = new WebSocket("ws://localhost:8000/dashboard");
ws.onopen = () => console.log("[WS] Dashboard connecté");
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.event === "db_response") {
    currentCalls = msg.data;
    updateDashboard();
  }
};

// ── Main update (appelé à chaque broadcast) ──
function updateDashboard() {
  renderSidebar();
  updateMarkers();
  if (activecallId && currentCalls[activecallId]) {
    const call = currentCalls[activecallId];
    renderConversation(call);
    updateEndCallButton(call);
  }
  updateDispatchPanel();
}

// ── Severity sort order ──
const SEVERITY_ORDER = { CRITICAL: 0, MODERATE: 1, LOW: 2, unknown: 3 };

function sortCalls(calls) {
  return Object.values(calls).sort((a, b) => {
    const sa = SEVERITY_ORDER[a.severity] ?? 3;
    const sb = SEVERITY_ORDER[b.severity] ?? 3;
    if (sa !== sb) return sa - sb;
    return new Date(b.time) - new Date(a.time); // même sévérité → plus récent en premier
  });
}

// ── Stats (compteurs animés) ──
const _statIds = {
  active:   "stat-active-val",
  critical: "stat-critical-val",
  moderate: "stat-moderate-val",
  low:      "stat-low-val",
};
function renderStats(sorted) {
  const vals = {
    active:   sorted.length,
    critical: sorted.filter(c => c.severity === "CRITICAL").length,
    moderate: sorted.filter(c => c.severity === "MODERATE").length,
    low:      sorted.filter(c => c.severity === "LOW").length,
  };
  Object.entries(_statIds).forEach(([k, id]) =>
    _animateCounter(document.getElementById(id), vals[k])
  );
}

// ── Sidebar gauche (FLIP animation) ──
function renderSidebar() {
  const list   = document.getElementById("call-list");
  const sorted = sortCalls(currentCalls);

  renderStats(sorted);

  if (sorted.length === 0) {
    list.innerHTML = `<div style="padding:20px;font-size:10px;letter-spacing:.1em;color:var(--muted);text-align:center">NO ACTIVE INCIDENTS</div>`;
    return;
  }

  // FLIP — étape 1 : mémoriser les positions actuelles
  const oldTops = {};
  list.querySelectorAll(".call-card[data-id]").forEach(card => {
    oldTops[card.dataset.id] = card.getBoundingClientRect().top;
  });

  // FLIP — étape 2 : reconstruire dans le nouvel ordre
  list.innerHTML = "";
  const newCards = {};
  sorted.forEach((call, i) => {
    const card = buildCard(call, i + 1);
    list.appendChild(card);
    newCards[call.id] = card;
  });

  // FLIP — étapes 3 & 4 : inverser puis jouer
  sorted.forEach((call) => {
    const card   = newCards[call.id];
    const oldTop = oldTops[call.id];

    if (oldTop === undefined) {
      // Nouvelle carte → slide-in depuis la gauche
      card.style.opacity   = "0";
      card.style.transform = "translateX(-14px)";
      requestAnimationFrame(() => {
        card.style.transition = "opacity 0.35s ease, transform 0.35s ease";
        card.style.opacity    = "1";
        card.style.transform  = "translateX(0)";
      });
      return;
    }

    const delta = oldTop - card.getBoundingClientRect().top;
    if (Math.abs(delta) < 1) return; // pas bougé

    // Snap à l'ancienne position sans transition
    card.style.transition = "none";
    card.style.transform  = `translateY(${delta}px)`;

    // Laisser le navigateur peindre, puis animer vers la nouvelle position
    requestAnimationFrame(() => requestAnimationFrame(() => {
      card.style.transition = "transform 0.5s cubic-bezier(0.25, 1, 0.5, 1)";
      card.style.transform  = "translateY(0)";
    }));
  });
}

const TYPE_LABEL = { fire: "FIRE", hospital: "MEDICAL", police: "POLICE", other: "OTHER" };
const TYPE_ICON  = { fire: "🔥", hospital: "🏥", police: "🚔", other: "📞" };

function buildCard(call, rank) {
  const card = document.createElement("div");
  const severity = call.severity || "unknown";
  card.className = `call-card severity-${severity}${call.id === activecallId ? " active" : ""}`;
  card.dataset.id   = call.id;
  card.dataset.rank = rank;

  const time = call.time
    ? new Date(call.time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "--:--:--";

  card.innerHTML = `
    <div class="call-card-header">
      <span class="call-title">${call.title || "INCIDENT EN COURS"}</span>
      <span class="badge badge-${severity}">${severity}</span>
    </div>
    <div class="call-location">⬡ ${call.location_name || "LOC UNKNOWN"}</div>
    <div class="call-footer">
      <span class="call-type-tag">${TYPE_ICON[call.type] || "📞"} ${TYPE_LABEL[call.type] || "—"}</span>
      <span class="call-time">${time}</span>
    </div>
  `;

  card.addEventListener("click", () => selectCall(call.id));
  return card;
}

// ── Sélection d'un appel ──
function selectCall(callId) {
  activecallId = callId;
  const call = currentCalls[callId];
  if (!call) return;

  // Highlight
  document.querySelectorAll(".call-card").forEach((c) => c.classList.remove("active"));
  document.querySelector(`.call-card[data-id="${callId}"]`)?.classList.add("active");

  // Zoom carte
  if (call.coordinates) {
    map.flyTo([call.coordinates.lat, call.coordinates.lng], 15, { duration: 1 });
    markers[callId]?.openPopup();
  }

  // Affiche la conversation + dispatch panel
  renderConversation(call);
  updateDispatchPanel();
  updateEndCallButton(call);
}

// ── Bouton End Call ──
function updateEndCallButton(call) {
  const btn = document.getElementById("btn-end-call");
  if (!btn || !call) return;
  const isActive = call.mode === "twilio" && call.status !== "ended";
  btn.style.display = isActive ? "flex" : "none";
}

function endCall() {
  if (!activecallId) return;
  const call = currentCalls[activecallId];
  if (!call || call.status === "ended") return;
  ws.send(JSON.stringify({ type: "end_call", call_id: activecallId }));
  // Feedback immédiat
  const btn = document.getElementById("btn-end-call");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="end-call-icon">📵</span> Ending…';
  }
}

// ── Score definitions (5 axes) ──
const SCORES_DEF = [
  { key: "anxiety",            label: "Anxiety",    invert: false },
  { key: "coherence",          label: "Coherence",  invert: true  },
  { key: "severity_score",     label: "Severity",   invert: false },
  { key: "seriousness",        label: "Seriousness",invert: false },
  { key: "proximity_to_victim",label: "Proximity",  invert: false },
];

let chartMode = "bar"; // "bar" | "radar"

function setChartMode(mode) {
  chartMode = mode;
  document.getElementById("btn-bar").classList.toggle("active",   mode === "bar");
  document.getElementById("btn-radar").classList.toggle("active", mode === "radar");
  // Reset l'état des deux renderers pour forcer une reconstruction propre
  document.getElementById("conv-scores").innerHTML = "";
  if (_radarAnimId) { cancelAnimationFrame(_radarAnimId); _radarAnimId = null; }
  _radarCurrent = null;
  if (activecallId && currentCalls[activecallId]) {
    renderScores(currentCalls[activecallId]);
  }
}

function getScoreColor(val, invert) {
  const v = invert ? 10 - val : val;
  if (v <= 3) return "var(--green)";
  if (v <= 6) return "var(--orange)";
  return "var(--red)";
}

function getStaticScores(call) {
  return {
    anxiety:             call.scores?.anxiety             ?? 5,
    coherence:           call.scores?.coherence           ?? 5,
    severity_score:      call.scores?.severity_score      ?? 5,
    seriousness:         call.scores?.seriousness         ?? 5,
    proximity_to_victim: call.scores?.proximity_to_victim ?? 5,
  };
}

// ── Bar chart (DOM update → CSS transition) ──
function renderBar(scores) {
  const el = document.getElementById("conv-scores");
  el.className = "";

  const alreadyBuilt = !!el.querySelector(".score-row[data-key]");
  if (!alreadyBuilt) {
    // Première fois : créer le DOM avec width à 0, puis animer au prochain frame
    el.innerHTML = SCORES_DEF.map((s) => `
      <div class="score-row" data-key="${s.key}">
        <span class="score-label">${s.label}</span>
        <div class="score-track">
          <div class="score-fill" style="width:0%;background:var(--muted)"></div>
        </div>
        <span class="score-value" style="color:var(--muted)">—</span>
      </div>`).join("");
    // Laisser le navigateur peindre à 0, puis déclencher la transition
    requestAnimationFrame(() => _updateBars(el, scores));
  } else {
    _updateBars(el, scores);
  }
}

function _updateBars(el, scores) {
  SCORES_DEF.forEach((s) => {
    const row   = el.querySelector(`.score-row[data-key="${s.key}"]`);
    if (!row) return;
    const val   = scores[s.key];
    const pct   = (val / 10) * 100;
    const color = getScoreColor(val, s.invert);
    row.querySelector(".score-fill").style.width      = `${pct}%`;
    row.querySelector(".score-fill").style.background = color;
    row.querySelector(".score-value").style.color     = color;
    // Compteur animé
    _animateCounter(row.querySelector(".score-value"), val);
  });
}

const _counterFrames = new WeakMap();
function _animateCounter(el, target) {
  if (_counterFrames.has(el)) cancelAnimationFrame(_counterFrames.get(el));
  const start     = parseFloat(el.textContent) || 0;
  const startTime = performance.now();
  const duration  = 600;
  function tick(now) {
    const t    = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3); // cubic ease-out
    el.textContent = Math.round(start + (target - start) * ease);
    if (t < 1) _counterFrames.set(el, requestAnimationFrame(tick));
  }
  _counterFrames.set(el, requestAnimationFrame(tick));
}

// ── Radar chart (SVG avec animation rAF) ──
const _R_N = 5, _R_SIZE = 170, _R_CX = 85, _R_CY = 85, _R_R = 58;
let _radarCurrent = null;   // valeurs normalisées courantes [0-1]
let _radarAnimId  = null;

function _radarPt(i, r) {
  const a = -Math.PI / 2 + i * (2 * Math.PI / _R_N);
  return { x: _R_CX + r * Math.cos(a), y: _R_CY + r * Math.sin(a) };
}

function _radarPtsStr(vals) {
  return vals.map((v, i) => { const p = _radarPt(i, _R_R * v); return `${p.x},${p.y}`; }).join(" ");
}

function _radarApply(el, vals) {
  const poly = el.querySelector("#rd-poly");
  if (poly) poly.setAttribute("points", _radarPtsStr(vals));
  SCORES_DEF.forEach((s, i) => {
    const dot = el.querySelector(`#rd-dot-${i}`);
    if (!dot) return;
    const p = _radarPt(i, _R_R * vals[i]);
    dot.setAttribute("cx", p.x);
    dot.setAttribute("cy", p.y);
    dot.setAttribute("fill", getScoreColor(Math.round(vals[i] * 10), s.invert));
  });
}

function renderRadar(scores) {
  const el = document.getElementById("conv-scores");
  el.className = "radar-mode";

  const target = SCORES_DEF.map(s => (scores[s.key] ?? 5) / 10);

  if (!el.querySelector("svg")) {
    // Première construction du SVG
    const levels = [0.2, 0.4, 0.6, 0.8, 1.0];
    const grid = levels.map(l =>
      `<polygon points="${Array.from({length:_R_N},(_,i)=>{const p=_radarPt(i,_R_R*l);return `${p.x},${p.y}`}).join(' ')}"
        fill="none" stroke="var(--border2)" stroke-width="0.8"/>`
    ).join('');
    const axes = Array.from({length:_R_N},(_,i)=>{
      const p = _radarPt(i, _R_R);
      return `<line x1="${_R_CX}" y1="${_R_CY}" x2="${p.x}" y2="${p.y}" stroke="var(--border2)" stroke-width="0.8"/>`;
    }).join('');
    const labels = SCORES_DEF.map((s, i) => {
      const lp = _radarPt(i, _R_R + 18);
      return `<text x="${lp.x}" y="${lp.y}" text-anchor="middle" dominant-baseline="middle"
        fill="var(--muted)" font-size="7" font-family="JetBrains Mono,monospace"
        letter-spacing="0.08em">${s.label.toUpperCase()}</text>`;
    }).join('');
    const dots = SCORES_DEF.map((_, i) =>
      `<circle id="rd-dot-${i}" cx="${_R_CX}" cy="${_R_CY}" r="3" fill="var(--muted)"/>`
    ).join('');

    _radarCurrent = Array(_R_N).fill(0.5);
    el.innerHTML = `
      <svg width="${_R_SIZE}" height="${_R_SIZE}" style="overflow:visible;display:block">
        ${grid}${axes}
        <polygon id="rd-poly" points="${_radarPtsStr(_radarCurrent)}"
          fill="rgba(45,212,191,0.12)" stroke="var(--accent)" stroke-width="1.5"
          stroke-linejoin="round"/>
        ${labels}${dots}
      </svg>`;
  }

  // Annuler l'animation précédente et lancer la nouvelle
  if (_radarAnimId) cancelAnimationFrame(_radarAnimId);
  const from      = [..._radarCurrent];
  const startTime = performance.now();
  const duration  = 700;

  function tick(now) {
    const t    = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3); // cubic ease-out
    _radarCurrent = from.map((v, i) => v + (target[i] - v) * ease);
    _radarApply(el, _radarCurrent);
    if (t < 1) _radarAnimId = requestAnimationFrame(tick);
  }
  _radarAnimId = requestAnimationFrame(tick);
}

// ── Dispatch ──
function renderScores(call) {
  const scores = getStaticScores(call);
  chartMode === "radar" ? renderRadar(scores) : renderBar(scores);
}

// ── Sidebar droite : conversation ──
function renderConversation(call) {
  const typeIcon = { fire: "🔥", hospital: "🏥", police: "🚔", other: "📞" };
  const severity = call.severity || "unknown";
  const transcript = call.transcript || [];

  renderScores(call);

  // Titre
  document.getElementById("conv-title").textContent =
    `${typeIcon[call.type] || "📞"} ${call.title || "Appel en cours"}`;


  // Meta chips
  const meta = document.getElementById("conv-meta");
  meta.innerHTML = `
    <span class="badge badge-${severity}" style="border-radius:999px;padding:3px 10px">${severity}</span>
    ${call.type ? `<span class="meta-chip">${typeIcon[call.type]} ${call.type}</span>` : ""}
    ${call.location_name ? `<span class="meta-chip">📍 ${call.location_name}</span>` : ""}
    ${call.recommendation ? `<span class="meta-chip" style="color:#fbbf24">⚡ ${call.recommendation}</span>` : ""}
    ${call.nearest_service ? `
      <span class="meta-chip" style="color:${SERVICE_COLOR[call.nearest_service.type]};border-color:${SERVICE_COLOR[call.nearest_service.type]}22">
        ${SERVICE_EMOJI[call.nearest_service.type]} ${call.nearest_service.name} — ${call.nearest_service.distance_km} km
      </span>` : ""}
  `;

  // Transcript
  const transcriptEl = document.getElementById("conv-transcript");
  const wasAtBottom = transcriptEl.scrollHeight - transcriptEl.scrollTop <= transcriptEl.clientHeight + 40;

  if (transcript.length === 0) {
    transcriptEl.innerHTML = `
      <div class="empty-state">
        <div style="font-size:28px;margin-bottom:8px">🎙️</div>
        Conversation en attente…
      </div>`;
    return;
  }

  transcriptEl.innerHTML = transcript
    .map((m) => `
      <div class="bubble ${m.role}">
        <div class="bubble-role">${m.role === "user" ? "👤 Appelant" : "🎙️ Dispatcher"}</div>
        ${stripMd(m.content)}
      </div>`)
    .join("");

  // Auto-scroll vers le bas si on y était déjà
  if (wasAtBottom) {
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }
}

// ── Carte : marqueurs ──
function updateMarkers() {
  Object.values(currentCalls).forEach((call) => {
    if (!call.coordinates) return;
    const { lat, lng } = call.coordinates;
    const severity = call.severity || "unknown";

    if (markers[call.id]) {
      markers[call.id].setLatLng([lat, lng]);
      markers[call.id].setIcon(buildIcon(severity));
      markers[call.id].getPopup()?.setContent(buildPopup(call));
    } else {
      // Nouveau marqueur → zoom automatique
      const marker = L.marker([lat, lng], { icon: buildIcon(severity) })
        .addTo(map)
        .bindPopup(buildPopup(call));

      marker.on("click", () => selectCall(call.id));
      markers[call.id] = marker;
      map.flyTo([lat, lng], 14, { duration: 1.5 });
    }

    // Service le plus proche
    updateNearestService(call);
  });
}

// ── Nearest service rendering ──
const SERVICE_EMOJI = { police: "🚔", fire: "🚒", hospital: "🏥" };
const SERVICE_COLOR = { police: "#3b82f6", fire: "#ef4444", hospital: "#22c55e" };

function updateNearestService(call) {
  const s = call.nearest_service;
  if (!s || !call.coordinates) return;

  const serviceLatLng = [s.lat, s.lng];
  const color = SERVICE_COLOR[s.type] || "#94a3b8";
  const emoji = SERVICE_EMOJI[s.type] || "🚨";

  // Itinéraire réel (OSRM) ou ligne droite en fallback
  if (serviceLines[call.id]) {
    serviceLines[call.id].remove();
  }
  const routePoints = s.route && s.route.length > 1
    ? s.route
    : [[call.coordinates.lat, call.coordinates.lng], serviceLatLng];

  serviceLines[call.id] = L.polyline(routePoints, {
    color,
    weight: 4,
    opacity: 0.8,
  }).addTo(map);

  // Marqueur service
  if (!serviceMarkers[call.id]) {
    const icon = L.divIcon({
      className: "",
      html: `<div class="service-marker service-${s.type}" style="color:${color}">${emoji}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
      popupAnchor: [0, -22],
    });

    serviceMarkers[call.id] = L.marker(serviceLatLng, { icon })
      .addTo(map)
      .bindPopup(`
        <div style="font-family:'JetBrains Mono',monospace;font-size:12px;min-width:180px;
                    background:#0b0e17;color:#c8d4e8;padding:10px 14px">
          <strong style="font-size:11px;letter-spacing:.04em">${emoji} ${s.name}</strong><br/>
          <span style="color:#94a3b8;font-size:10px">📍 ${s.address || "—"}</span><br/>
          ${s.phone ? `<span style="color:#94a3b8;font-size:10px">📞 ${s.phone}</span><br/>` : ""}
          ${s.hours ? `<span style="color:#94a3b8;font-size:10px">🕐 ${s.hours}</span><br/>` : ""}
          <span style="color:${color};font-weight:700;font-size:11px;margin-top:4px;display:inline-block;
                        letter-spacing:.06em">
            ◉ ${s.distance_km} km de l'appel
          </span>
        </div>`);
  }
}

function buildIcon(severity) {
  return L.divIcon({
    className: "",
    html: `<div class="marker-pin marker-${severity}"></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -26],
  });
}

function buildPopup(call) {
  const typeIcon = { fire: "🔥", hospital: "🏥", police: "🚔", other: "📞" };
  const img = call.street_image
    ? `<img src="${call.street_image}" width="260" height="150"
         style="display:block;width:260px;height:150px;object-fit:cover;margin:-10px -14px 8px;border-bottom:1px solid #1a2235"
         loading="lazy" />`
    : "";
  return `
    <div style="font-family:'JetBrains Mono',monospace;min-width:260px;font-size:12px;background:#0b0e17;color:#c8d4e8;padding:10px 14px">
      ${img}
      <strong style="font-size:11px;letter-spacing:.04em">${typeIcon[call.type] || "📞"} ${call.title || "Appel"}</strong><br/>
      <span style="color:#4a5c7a;font-size:10px">📍 ${call.location_name || "—"}</span><br/>
      <span style="margin-top:6px;display:inline-block;font-size:9px;font-weight:700;padding:1px 6px;border:1px solid;letter-spacing:.1em;
        color:${call.severity === "CRITICAL" ? "#f43f5e" : call.severity === "MODERATE" ? "#fb923c" : "#4ade80"};
        border-color:${call.severity === "CRITICAL" ? "#f43f5e" : call.severity === "MODERATE" ? "#fb923c" : "#4ade80"}">
        ${call.severity || "—"}
      </span>
    </div>`;
}
