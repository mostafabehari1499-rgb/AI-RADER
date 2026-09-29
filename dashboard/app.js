/* AI RADAR dashboard — vanilla JS, no build step, works on GitHub Pages. */
const FILTERS = ["All","Breaking","Models","Agents","Tools","Research","GitHub","YouTube","Open Source","Video","Image","Audio","Coding","Robotics","MCP","Experiments","Saved"];
let EVENTS = [], activeFilter = "All";

const grid = document.getElementById("grid");
const stats = document.getElementById("stats");
const emptyBox = document.getElementById("empty");
const searchBox = document.getElementById("search");
const sortBox = document.getElementById("sort");
const modal = document.getElementById("modal");
const modalBody = document.getElementById("modal-body");

function savedIds() { try { return new Set(JSON.parse(localStorage.getItem("radar_saved") || "[]")); } catch { return new Set(); } }
function toggleSave(id) {
  const s = savedIds();
  if (s.has(id)) s.delete(id); else s.add(id);
  localStorage.setItem("radar_saved", JSON.stringify([...s]));
  render();
}

async function loadData() {
  // Works both when served from repo root and from dashboard/ dir (GitHub Pages).
  const candidates = ["./data/events.json", "../data/events.json", "data/events.json"];
  for (const u of candidates) {
    try {
      const r = await fetch(u, { cache: "no-store" });
      if (r.ok) { EVENTS = await r.json(); return; }
    } catch { /* try next */ }
  }
  EVENTS = [];
}

function matchFilter(ev) {
  const q = (searchBox.value || "").toLowerCase();
  if (q) {
    const hay = `${ev.title} ${ev.description} ${ev.source} ${ev.category} ${(ev.tags||[]).join(" ")}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  const cat = (ev.category || "").toUpperCase();
  const subs = ((ev.subcategories || []).join(" ")).toUpperCase();
  const tags = ((ev.tags || []).join(" ")).toLowerCase();
  switch (activeFilter) {
    case "All": return true;
    case "Breaking": return (ev.importance_level === "BREAKING" || ev.importance_level === "HIGH");
    case "Models": return cat === "MODEL";
    case "Agents": return cat === "AGENT" || subs.includes("AGENT");
    case "Tools": return cat === "TOOL";
    case "Research": return cat === "RESEARCH";
    case "GitHub": return ev.source_type === "github" || cat === "GITHUB";
    case "YouTube": return ev.source_type === "youtube";
    case "Open Source": return subs.includes("OPEN_SOURCE") || cat === "OPEN_SOURCE" || tags.includes("open");
    case "Video": return cat === "VIDEO" || subs.includes("VIDEO") || tags.includes("video");
    case "Image": return cat === "IMAGE";
    case "Audio": return cat === "AUDIO";
    case "Coding": return cat === "CODING";
    case "Robotics": return cat === "ROBOTICS";
    case "MCP": return cat === "MCP" || subs.includes("MCP");
    case "Experiments": return ev.experiment && ev.experiment.can_test_free;
    case "Saved": return savedIds().has(ev.id);
    default: return true;
  }
}

function sorted(list) {
  const m = sortBox.value;
  const L = [...list];
  if (m === "important") L.sort((a,b)=>(b.importance_score||0)-(a.importance_score||0));
  else if (m === "trending") L.sort((a,b)=>(b.trend_score||0)-(a.trend_score||0));
  else if (m === "content") L.sort((a,b)=>((b.ai||{}).content_score||0)-((a.ai||{}).content_score||0));
  else L.sort((a,b)=>String(b.discovered_at||"").localeCompare(String(a.discovered_at||"")));
  return L;
}

function esc(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").slice(0,400); }

function card(ev) {
  const exp = ev.experiment || {};
  const testPill = exp.can_test_free ? `<span class="pill ok">🧪 free test</span>` : `<span class="pill">no free test</span>`;
  const trend = `<span class="pill ${ev.trend_status==="HOT"||ev.trend_status==="VIRAL"?"hot":""}">📈 ${ev.trend_status||""}</span>`;
  const ai = ev.ai || {};
  return `<div class="card">
    <div class="meta"><span class="pill acc">${esc(ev.category)}</span><span class="pill">⭐ ${ev.importance_score||0}</span>${trend}${testPill}</div>
    <h3><a href="${esc(ev.url)}" target="_blank" rel="noopener">${esc(ev.title)}</a></h3>
    <div class="kv">${esc(ev.source)} · ${esc((ev.published_at||ev.discovered_at||"").slice(0,10))}</div>
    <div class="desc">${esc((ai.summary_en || ev.description || "").slice(0,160))}</div>
    ${ai.summary_ar ? `<div class="ar" dir="auto">${esc(ai.summary_ar.slice(0,160))}</div>` : ""}
    <div class="row">
      <button onclick='openModal(${JSON.stringify(ev.id)})'>READ</button>
      <a href="${esc(ev.url)}" target="_blank" rel="noopener">SOURCE</a>
      ${(exp.options||[])[0] ? `<a class="primary" href="${esc(exp.options[0].url)}" target="_blank" rel="noopener">TRY</a>` : ""}
      <button onclick='toggleSave(${JSON.stringify(ev.id)})'>${savedIds().has(ev.id) ? "★ SAVED" : "☆ SAVE"}</button>
    </div>
  </div>`;
}

function render() {
  const list = sorted(EVENTS.filter(matchFilter));
  stats.textContent = `${list.length} shown · ${EVENTS.length} total events`;
  grid.innerHTML = list.slice(0, 200).map(card).join("");
  emptyBox.hidden = list.length > 0;
}

function openModal(id) {
  const ev = EVENTS.find(e => e.id === id);
  if (!ev) return;
  const ai = ev.ai || {}, exp = ev.experiment || {};
  const opts = (exp.options || []).map(o => `<li><a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(o.name)}</a> <span class="kv">(${esc(o.type)})</span></li>`).join("") || "<li>No verified free option.</li>";
  modalBody.innerHTML = `
    <h2>${esc(ev.title)}</h2>
    <div class="kv"><b>${esc(ev.category)}</b> · ${esc(ev.source)} · ${esc(ev.published_at||ev.discovered_at||"")}</div>
    <p>${esc(ev.description)}</p>
    ${ai.summary_ar ? `<h4>الملخص العربي</h4><p dir="auto">${esc(ai.summary_ar)}</p>` : ""}
    <h4>Why it matters</h4><p>${esc(ai.why || (ev.importance_reasons||[]).join("; "))}</p>
    <h4>Free testing</h4><ul>${opts}</ul>
    <h4>Hardware (estimated)</h4><p class="kv">${esc(JSON.stringify(exp.hardware || {}))}</p>
    <h4>Content ideas</h4><p class="kv">${esc((ai.video_titles||[]).join(" · "))}</p>
    <p><a href="${esc(ev.url)}" target="_blank" rel="noopener">Open original source →</a></p>`;
  modal.hidden = false;
}

function buildFilters() {
  const nav = document.getElementById("filters");
  nav.innerHTML = "";
  FILTERS.forEach(f => {
    const b = document.createElement("button");
    b.textContent = f;
    if (f === activeFilter) b.classList.add("active");
    b.onclick = () => { activeFilter = f; buildFilters(); render(); };
    nav.appendChild(b);
  });
}

window.openModal = openModal; window.toggleSave = toggleSave;
document.getElementById("modal-close").onclick = () => modal.hidden = true;
modal.addEventListener("click", e => { if (e.target === modal) modal.hidden = true; });
searchBox.addEventListener("input", render);
sortBox.addEventListener("change", render);

(async () => { buildFilters(); await loadData(); render(); })();
