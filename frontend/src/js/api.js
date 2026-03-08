/* ═══════════════════════════════════════════════
   api.js — API wrapper, global state, shared helpers
   ═══════════════════════════════════════════════ */

const API_BASE = 'http://localhost:5000';

// ─── GLOBAL STATE ───────────────────────────────
const state = {
  currentPage:    'dashboard',
  jobs:           [],
  companies:      [],
  resumes:        [],
  history:        [],
  lastMatchResults: null,
  apiOnline:      false,
  warehouseStats: { jobs: 0, resumes: 0 }
};

// ─── API FETCH WRAPPER ──────────────────────────
async function api(path, options = {}) {
  const url = API_BASE + path;
  const cfg = { ...options };

  // Auto-stringify JSON bodies (skip FormData)
  if (cfg.body && typeof cfg.body === 'object' && !(cfg.body instanceof FormData)) {
    cfg.headers = { 'Content-Type': 'application/json', ...(cfg.headers || {}) };
    cfg.body = JSON.stringify(cfg.body);
  }

  const res = await fetch(url, cfg);

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const e = await res.json(); msg = e.error || e.message || msg; } catch {}
    throw new Error(msg);
  }

  return res.json();
}

// ─── CHECK API STATUS ───────────────────────────
async function checkApiStatus() {
  try {
    const data = await api('/');
    state.apiOnline = true;
    state.warehouseStats = {
      jobs:    data.warehouse_jobs    || 0,
      resumes: data.warehouse_resumes || 0
    };
    document.getElementById('status-dot').className   = 'status-dot online';
    document.getElementById('status-text').textContent = 'API Online';
    document.getElementById('pill-jobs').textContent    = `${data.warehouse_jobs    || 0} Jobs`;
    document.getElementById('pill-resumes').textContent = `${data.warehouse_resumes || 0} Resumes`;
  } catch {
    state.apiOnline = false;
    document.getElementById('status-dot').className   = 'status-dot';
    document.getElementById('status-text').textContent = 'API Offline';
  }
}

// ─── SCORE HELPERS ──────────────────────────────
function scoreClass(s) {
  return s > 5 ? 'score-high' : s >= 2 ? 'score-mid' : 'score-low';
}
function scoreColor(s) {
  return s > 5 ? 'var(--success)' : s >= 2 ? 'var(--warning)' : 'var(--danger)';
}

// ─── FORMAT HELPERS ─────────────────────────────
function fmt4(n) { return (+n).toFixed(4); }

function fmtDate(d) {
  if (!d) return '—';
  const dt = new Date(d);
  return dt.toLocaleDateString('en-US',  { month: 'short', day: 'numeric', year: 'numeric' })
    + ' · '
    + dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function fmtDateShort(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ─── HTML HELPERS ───────────────────────────────
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderTags(terms, max = 8) {
  if (!terms || !terms.length) return '<span class="text-muted text-sm">none</span>';
  const visible = terms.slice(0, max);
  const extra   = terms.length - max;
  let html = visible.map(t => `<span class="tag">${escHtml(t)}</span>`).join('');
  if (extra > 0) html += `<span class="more-tag">+${extra} more</span>`;
  return html;
}

function scoreBarHtml(score, maxScore = 10) {
  const pct = Math.min((score / maxScore) * 100, 100);
  return `<div class="score-bar-wrap"><div class="score-bar-fill" data-pct="${pct}"></div></div>`;
}

function animateBars() {
  setTimeout(() => {
    document.querySelectorAll('.score-bar-fill').forEach(el => {
      el.style.width = el.dataset.pct + '%';
    });
  }, 50);
}

// ─── SKELETON HELPERS ───────────────────────────
function skeletonRows(n = 5, cols = 5) {
  return Array.from({ length: n }, () =>
    `<tr>${Array.from({ length: cols }, () =>
      `<td><div class="skeleton skeleton-line"></div></td>`
    ).join('')}</tr>`
  ).join('');
}

function skeletonCards(n = 4) {
  return Array.from({ length: n }, () =>
    `<div class="card" style="padding:20px;height:120px">
      <div class="skeleton skeleton-line w-40" style="height:40px;margin-bottom:12px"></div>
      <div class="skeleton skeleton-line w-80"></div>
      <div class="skeleton skeleton-line w-60"></div>
    </div>`
  ).join('');
}

// ─── MISC HELPERS ───────────────────────────────
function hslFromName(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return `hsl(${Math.abs(hash) % 360}, 60%, 45%)`;
}

function extractSkills(desc = '') {
  const keywords = desc.match(
    /\b(Python|JavaScript|TypeScript|React|Node\.js|SQL|AWS|Docker|Kubernetes|Git|Java|C\+\+|Go|Rust|Machine Learning|AI|TensorFlow|PyTorch|DevOps|CI\/CD|Agile|Linux|Redis|MongoDB|PostgreSQL|GraphQL|REST|API|Figma|UI\/UX|HTML|CSS|Terraform|Ansible|Azure|GCP|Spark|Hadoop|Scala|R|JIRA|Confluence|Kafka|RabbitMQ|Elasticsearch|Nginx|Bash|Shell)\b/g
  ) || [];
  return [...new Set(keywords)].slice(0, 5);
}

// ─── SVG ICONS ──────────────────────────────────
function svgDocs() {
  return `<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
    <rect x="3" y="2" width="11" height="14" rx="1"/>
    <rect x="6" y="5" width="16" height="14" rx="1" fill="white"/>
    <line x1="9" y1="9" x2="19" y2="9"/>
    <line x1="9" y1="12" x2="16" y2="12"/>
  </svg>`;
}
function svgBriefcase() {
  return `<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
    <rect x="2" y="7" width="16" height="11" rx="1"/>
    <path d="M7 7V5a3 3 0 016 0v2"/>
    <line x1="10" y1="11" x2="10" y2="14"/>
  </svg>`;
}
function svgBuilding() {
  return `<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
    <rect x="3" y="5" width="14" height="13" rx="1"/>
    <path d="M7 5V3h6v2"/>
    <line x1="7" y1="10" x2="7" y2="12"/>
    <line x1="10" y1="10" x2="10" y2="12"/>
    <line x1="13" y1="10" x2="13" y2="12"/>
    <line x1="7" y1="15" x2="7" y2="18"/>
    <line x1="13" y1="15" x2="13" y2="18"/>
  </svg>`;
}
function svgClock() {
  return `<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
    <circle cx="10" cy="10" r="8"/>
    <polyline points="10,5.5 10,10 13,12.5"/>
  </svg>`;
}
function svgEmptyInbox() {
  return `<svg width="80" height="80" viewBox="0 0 80 80" fill="none">
    <rect x="12" y="18" width="56" height="44" rx="4" fill="#EEF2FF" stroke="#C7D2FE" stroke-width="2"/>
    <path d="M12 42h16l6 8h12l6-8h16" stroke="#A5B4FC" stroke-width="2"/>
    <line x1="24" y1="30" x2="56" y2="30" stroke="#C7D2FE" stroke-width="2" stroke-linecap="round"/>
    <line x1="24" y1="36" x2="46" y2="36" stroke="#C7D2FE" stroke-width="2" stroke-linecap="round"/>
  </svg>`;
}
function svgEmptyClipboard() {
  return `<svg width="80" height="80" viewBox="0 0 80 80" fill="none">
    <rect x="16" y="12" width="48" height="58" rx="4" fill="#EEF2FF" stroke="#C7D2FE" stroke-width="2"/>
    <rect x="28" y="8" width="24" height="10" rx="3" fill="#A5B4FC"/>
    <line x1="24" y1="32" x2="56" y2="32" stroke="#C7D2FE" stroke-width="2" stroke-linecap="round"/>
    <line x1="24" y1="40" x2="50" y2="40" stroke="#C7D2FE" stroke-width="2" stroke-linecap="round"/>
    <line x1="24" y1="48" x2="44" y2="48" stroke="#C7D2FE" stroke-width="2" stroke-linecap="round"/>
  </svg>`;
}
