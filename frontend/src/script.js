/* ══════════════════════════════════════════════════════════════════
   ResumeIQ — script.js
   Upload tab: full analysis (BM25 + skill gap + impact + what-if)
   Database tab: BM25 score list (unchanged)
   ══════════════════════════════════════════════════════════════════ */

const API_BASE = "http://127.0.0.1:5000";

/* ── Utilities ─────────────────────────────────────────────────────── */

const $ = id => document.getElementById(id);

function showToast(msg, duration = 3200) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), duration);
}

function formatBytes(b) {
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}

function setLoading(btn, on) {
  if (on) {
    btn.dataset.orig = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span><span class="btn-text">Analysing…</span>`;
    btn.classList.add("loading");
  } else {
    btn.innerHTML = btn.dataset.orig || btn.innerHTML;
    btn.classList.remove("loading");
  }
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/* ── Tab Navigation ────────────────────────────────────────────────── */

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

/* ── Char counters ──────────────────────────────────────────────────── */

["uploadJobText|uploadCharCount", "dbJobText|dbCharCount"].forEach(pair => {
  const [taId, cId] = pair.split("|");
  const ta = $(taId), c = $(cId);
  ta.addEventListener("input", () => {
    const n = ta.value.length;
    c.textContent = `${n.toLocaleString()} character${n !== 1 ? "s" : ""}`;
  });
});

/* ── File Management ────────────────────────────────────────────────── */

let selectedFiles = [];

function renderFileList() {
  const list = $("fileList");
  list.innerHTML = "";
  selectedFiles.forEach((f, i) => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `
      <div class="file-icon">PDF</div>
      <span class="file-name">${esc(f.name)}</span>
      <span class="file-size">${formatBytes(f.size)}</span>
      <button class="file-remove" data-i="${i}" title="Remove">✕</button>
    `;
    list.appendChild(item);
  });
  list.querySelectorAll(".file-remove").forEach(btn => {
    btn.addEventListener("click", () => {
      selectedFiles.splice(+btn.dataset.i, 1);
      renderFileList();
    });
  });
}

function addFiles(files) {
  const existing = new Set(selectedFiles.map(f => f.name + f.size));
  Array.from(files).forEach(f => {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      showToast(`"${f.name}" skipped — PDF only.`); return;
    }
    const k = f.name + f.size;
    if (!existing.has(k)) { selectedFiles.push(f); existing.add(k); }
  });
  renderFileList();
}

$("resumeFiles").addEventListener("change", e => { addFiles(e.target.files); e.target.value = ""; });

const dropZone = $("dropZone");
dropZone.addEventListener("click", () => $("resumeFiles").click());
["dragenter", "dragover"].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("dragover"); }));
["dragleave", "drop"].forEach(ev => dropZone.addEventListener(ev, () => dropZone.classList.remove("dragover")));
dropZone.addEventListener("drop", e => { e.preventDefault(); addFiles(e.dataTransfer.files); });

$("uploadClear").addEventListener("click", () => {
  selectedFiles = [];
  renderFileList();
  $("uploadJobText").value = "";
  $("uploadCharCount").textContent = "0 characters";
  $("uploadResults").innerHTML = "";
});

/* ── Top-K Stepper ──────────────────────────────────────────────────── */

let topK = 5;
$("stepUp").addEventListener("click",   () => { topK = Math.min(topK + 1, 20); $("topKVal").textContent = topK; });
$("stepDown").addEventListener("click", () => { topK = Math.max(topK - 1, 1);  $("topKVal").textContent = topK; });

/* ═══════════════════════════════════════════════════════════════════════
   ANALYSIS RENDERING
   ═══════════════════════════════════════════════════════════════════════ */

/* composite ring color class */
function ringClass(label) {
  if (label === "Excellent Fit") return "ring-green";
  if (label === "Good Fit")      return "ring-amber";
  if (label === "Fair Fit")      return "ring-orange";
  return "ring-red";
}

/* fit badge color class */
function fitClass(color) {
  const map = { green: "fit-green", amber: "fit-amber", orange: "fit-orange", red: "fit-red" };
  return map[color] || "fit-red";
}

/* animate all composite rings in a container */
function animateCompositeRings(container) {
  container.querySelectorAll(".ring-fill[data-target]").forEach(ring => {
    const target = parseFloat(ring.dataset.target);
    requestAnimationFrame(() => { ring.style.strokeDashoffset = target; });
  });
}

/* animate all impact bars */
function animateImpactBars(container) {
  container.querySelectorAll(".impact-bar[data-w]").forEach(bar => {
    const w = bar.dataset.w;
    requestAnimationFrame(() => { bar.style.width = w; });
  });
}

/* build a skill chip */
function chip(label, cls) {
  return `<span class="chip ${cls}"><span class="chip-dot"></span>${esc(label)}</span>`;
}

/* build the score ring SVG */
function compositeRingSVG(score, fitLabel) {
  const circumference = 182;
  const offset = circumference * (1 - Math.min(score / 100, 1));
  const cls = ringClass(fitLabel);
  return `
    <div class="ac-ring-wrap">
      <div class="comp-ring">
        <svg width="72" height="72" viewBox="0 0 72 72">
          <circle class="ring-track" cx="36" cy="36" r="29"/>
          <circle class="ring-fill ${cls}" cx="36" cy="36" r="29"
            style="stroke-dashoffset:${circumference}"
            data-target="${offset}"/>
        </svg>
        <div class="ring-val">${score}%</div>
      </div>
      <span class="ring-lbl">Match</span>
    </div>
  `;
}

/* build one impact item */
function impactItemHTML(item, maxImpact) {
  const barPct = maxImpact > 0 ? Math.min((item.impact / maxImpact) * 100, 100) : 0;
  return `
    <div class="impact-item">
      <div class="impact-top">
        <span class="impact-skill">${esc(item.skill)}</span>
        <span class="impact-badge">+${item.impact}% score</span>
      </div>
      <div class="impact-bar-wrap">
        <div class="impact-bar" data-w="${barPct.toFixed(1)}%"></div>
      </div>
      <div class="impact-suggestion">${esc(item.suggestion)}</div>
      <div class="impact-time">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        ${esc(item.learn_time)}
      </div>
    </div>
  `;
}

/* render full analysis list */
function renderAnalysis(analyses, container, parseErrors = []) {
  container.innerHTML = "";

  if (parseErrors.length > 0) {
    const eb = document.createElement("div");
    eb.className = "parse-errors";
    eb.innerHTML = parseErrors.map(e =>
      `<div class="parse-error-item">⚠️ <strong>${esc(e.file)}</strong> — ${esc(e.error)}</div>`
    ).join("");
    container.appendChild(eb);
  }

  if (!analyses || analyses.length === 0) {
    container.innerHTML += `<div class="state-card"><div class="state-icon">🔍</div><div class="state-title">No results</div><div class="state-msg">Try a more detailed job description or ensure the PDFs have readable text.</div></div>`;
    return;
  }

  // Summary bar
  const summary = document.createElement("div");
  summary.className = "analysis-summary";
  summary.innerHTML = `
    <span class="summary-title">Analysis Results</span>
    <span class="summary-meta">${analyses.length} resume${analyses.length > 1 ? "s" : ""} ranked by composite score</span>
  `;
  container.appendChild(summary);

  const list = document.createElement("div");
  list.className = "analysis-list";

  analyses.forEach((a, i) => {
    if (a.error) return; // skip failed ones

    const maxImpact = a.impact_list && a.impact_list.length > 0
      ? Math.max(...a.impact_list.map(x => x.impact))
      : 1;

    const matchedHTML = a.matched_skills && a.matched_skills.length > 0
      ? a.matched_skills.map(s => chip(s, "chip-matched")).join("")
      : `<span class="empty-skills">None detected</span>`;

    const missingHTML = a.missing_skills && a.missing_skills.length > 0
      ? a.missing_skills.map(s => chip(s, "chip-missing")).join("")
      : `<span class="empty-skills">None — great coverage!</span>`;

    const bonusHTML = a.bonus_skills && a.bonus_skills.length > 0
      ? a.bonus_skills.map(s => chip(s, "chip-bonus")).join("")
      : `<span class="empty-skills">None</span>`;

    const impactHTML = a.impact_list && a.impact_list.length > 0
      ? a.impact_list.slice(0, 5).map(item => impactItemHTML(item, maxImpact)).join("")
      : `<span class="empty-skills">No missing skills detected — excellent match!</span>`;

    const card = document.createElement("div");
    card.className = "analysis-card";
    card.style.animationDelay = `${i * 70}ms`;
    card.dataset.resumeId = a.id;

    card.innerHTML = `
      <!-- ── Card Header ── -->
      <div class="ac-header">
        <div class="ac-rank">${String(i + 1).padStart(2, "0")}</div>
        <div class="ac-name-block">
          <div class="ac-name">${esc(a.id)}</div>
          <div class="ac-scores-row">
            <span class="score-pill sp-bm25">Semantic ${a.breakdown ? a.breakdown.semantic + '%' : (a.skill_score + '%')}</span>
            <span class="score-pill sp-skill">Skills ${a.breakdown ? a.breakdown.skills + '%' : a.skill_score + '%'}</span>
            <span class="fit-badge ${fitClass(a.fit_color)}">${esc(a.fit_label)}</span>
          </div>
        </div>
        ${compositeRingSVG(a.composite_score, a.fit_label)}
      </div>

      <!-- ── Card Body ── -->
      <div class="ac-body">

        <!-- Matched Skills -->
        <div>
          <div class="ac-section-title">✓ Matched Skills</div>
          <div class="skill-chips">${matchedHTML}</div>
        </div>

        <!-- Missing Skills -->
        <div>
          <div class="ac-section-title">✕ Missing Skills</div>
          <div class="skill-chips">${missingHTML}</div>
        </div>

        <!-- Bonus Skills -->
        <div>
          <div class="ac-section-title">★ Bonus Skills (not in JD)</div>
          <div class="skill-chips">${bonusHTML}</div>
        </div>

        <!-- Impact Improvements -->
        ${a.impact_list && a.impact_list.length > 0 ? `
        <div>
          <div class="ac-section-title">📈 Top Improvement Opportunities</div>
          <div class="impact-list">${impactHTML}</div>
        </div>
        ` : ""}

      </div>

      <!-- ── Card Footer ── -->
      <div class="ac-footer">
        <span class="ac-footer-label">
          ${a.missing_skills && a.missing_skills.length > 0
            ? `Adding top skills could gain up to <strong>+${
                a.impact_list ? a.impact_list.slice(0,3).reduce((s,x)=>s+x.impact,0).toFixed(1) : 0
              }%</strong> match score`
            : "Strong match — focus on tailoring your resume language"}
        </span>
        ${a.missing_skills && a.missing_skills.length > 0
          ? `<button class="btn-whatif" data-idx="${i}">⚡ What-If Simulator</button>`
          : ""}
      </div>
    `;

    list.appendChild(card);
  });

  container.appendChild(list);

  // Animate rings and bars
  requestAnimationFrame(() => {
    animateCompositeRings(container);
    animateImpactBars(container);
  });

  // Wire up what-if buttons
  container.querySelectorAll(".btn-whatif").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx);
      openWhatIfModal(analyses[idx]);
    });
  });
}

function renderError(msg, container) {
  container.innerHTML = `
    <div class="state-card error-card">
      <div class="state-icon">✕</div>
      <div class="state-title">Something went wrong</div>
      <div class="state-msg">${esc(msg)}</div>
    </div>
  `;
}

/* ── Analyse Button ─────────────────────────────────────────────────── */

$("analyzeBtn").addEventListener("click", async () => {
  const jobText   = $("uploadJobText").value.trim();
  const resultsEl = $("uploadResults");
  const btn       = $("analyzeBtn");

  if (!jobText) { showToast("Please paste a job description."); $("uploadJobText").focus(); return; }
  if (selectedFiles.length === 0) { showToast("Please upload at least one PDF resume."); return; }

  setLoading(btn, true);
  resultsEl.innerHTML = "";

  const formData = new FormData();
  formData.append("job_text", jobText);
  selectedFiles.forEach(f => formData.append("resumes", f));

  try {
    const res  = await fetch(`${API_BASE}/analyze`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) { renderError(data.error || `Server error (${res.status})`, resultsEl); return; }
    renderAnalysis(data.analyses, resultsEl, data.parse_errors || []);
    showToast(`Analysed ${data.total_scored} resume${data.total_scored !== 1 ? "s" : ""} successfully.`);
  } catch (err) {
    console.error(err);
    renderError("Could not reach the server. Make sure Flask is running on port 5000.", resultsEl);
  } finally {
    setLoading(btn, false);
  }
});

/* ═══════════════════════════════════════════════════════════════════════
   WHAT-IF MODAL
   ═══════════════════════════════════════════════════════════════════════ */

let _modalAnalysis = null;   // currently open analysis object

function openWhatIfModal(analysis) {
  _modalAnalysis = analysis;

  $("modalSubtitle").textContent = analysis.id;

  // Render missing skill toggles
  const skillsEl = $("whatifSkills");
  skillsEl.innerHTML = "";

  if (!analysis.missing_skills || analysis.missing_skills.length === 0) {
    skillsEl.innerHTML = `<span style="color:var(--text-3);font-size:0.85rem">No missing skills — nothing to simulate.</span>`;
  } else {
    analysis.missing_skills.forEach(skill => {
      const tog = document.createElement("div");
      tog.className = "whatif-skill-toggle";
      tog.dataset.skill = skill;
      tog.innerHTML = `<div class="wst-check"></div>${esc(skill)}`;
      tog.addEventListener("click", () => {
        tog.classList.toggle("selected");
        tog.querySelector(".wst-check").textContent = tog.classList.contains("selected") ? "✓" : "";
        $("whatifResult").classList.remove("show");
      });
      skillsEl.appendChild(tog);
    });
  }

  $("whatifResult").innerHTML = "";
  $("whatifResult").classList.remove("show");
  $("modalOverlay").classList.add("open");
}

function closeModal() {
  $("modalOverlay").classList.remove("open");
  _modalAnalysis = null;
}

$("modalClose").addEventListener("click", closeModal);
$("modalCancel").addEventListener("click", closeModal);
$("modalOverlay").addEventListener("click", e => { if (e.target === $("modalOverlay")) closeModal(); });

$("simulateBtn").addEventListener("click", async () => {
  if (!_modalAnalysis) return;

  const selected = Array.from($("whatifSkills").querySelectorAll(".whatif-skill-toggle.selected"))
    .map(el => el.dataset.skill);

  if (selected.length === 0) { showToast("Select at least one skill to simulate."); return; }

  const btn = $("simulateBtn");
  setLoading(btn, true);

  // We need resume_text — stored on window by the analyze call
  const resumeText = _resumeTexts[_modalAnalysis.id] || "";
  const jobText    = $("uploadJobText").value.trim();

  try {
    const res = await fetch(`${API_BASE}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text:       resumeText,
        job_text:          jobText,
        add_skills:        selected,
        // Pass pre-computed signals from /analyze to avoid recomputing embeddings
        current_semantic:  _modalAnalysis._semantic  ?? -1,
        current_exp:       _modalAnalysis._exp       ?? -1,
        current_edu:       _modalAnalysis._edu       ?? -1,
      })
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Simulation failed."); return; }

    const current = _modalAnalysis.match_score ?? _modalAnalysis.composite_score ?? 0;
    const simScore = data.simulated_score ?? data.new_composite_score ?? current;
    const gained   = Math.max(data.delta ?? (simScore - current), 0).toFixed(1);
    const positive = simScore > current;
    const skillsAdded = data.skills_effective ?? data.skills_added ?? [];

    const resultEl = $("whatifResult");
    resultEl.style.background = positive ? "var(--green-bg)" : "var(--surface-2)";
    resultEl.style.border = `1px solid ${positive ? "var(--green-border)" : "var(--border)"}`;
    resultEl.innerHTML = `
      <div class="wr-grid">
        <div class="wr-metric">
          <div class="wr-label">Current Score</div>
          <div class="wr-val">${current}%</div>
        </div>
        <div class="wr-metric">
          <div class="wr-label">Simulated Score</div>
          <div class="wr-val ${positive ? "positive" : ""}">${simScore}%</div>
        </div>
      </div>
      <div class="wr-skills-added">
        ${positive && skillsAdded.length
          ? `✅ Adding <strong>${skillsAdded.join(", ")}</strong> improves your match score by <strong>+${gained}%</strong>`
          : `These skills aren't listed as requirements in this job description, so no score change.`}
      </div>
    `;
    resultEl.classList.add("show");

  } catch (err) {
    console.error(err);
    showToast("Could not reach server for simulation.");
  } finally {
    setLoading(btn, false);
  }
});

/* We need to store resume texts for the what-if API call.
   Intercept the analyze response and save them client-side. */
let _resumeTexts = {};
let _whatifBm25Max = 1;

// Patch the analyze button to also store texts
// We achieve this by storing before submitting via a FormData reader
const _origAnalyze = $("analyzeBtn").onclick;
$("analyzeBtn").addEventListener("click", () => {
  // Reset
  _resumeTexts = {};
  // Texts are extracted server-side; we store them after /analyze returns
  // by using a separate /analyze response field — already done below via
  // a patched fetch inside the analyze handler (see _storeResumeTexts)
});

// Patch fetch call to also store bm25_max and resume texts
// We do this cleanly by overriding the handler above — but since the
// analyze handler is already written, we use a global flag pattern instead.
// Simpler: store bm25_max from analyses[0].bm25_score / bm25_max ratio
// Actually: the /analyze response returns bm25_score per resume but not
// bm25_max directly. We infer it: bm25_max = max(bm25_score) across results.
// For resume_text, we re-read the files in the browser (FileReader API).

async function readFileAsText_unused() {} // placeholder

// On analyze success, read all selected files as text so whatif can use them
async function storeResumeTextsFromFiles() {
  // We don't need actual text on client for the whatif API call because
  // the server already has the parsed text — we just need to pass it back.
  // BUT: the server doesn't store state between requests.
  // Solution: store parsed text in the analyze response and cache it here.
  // We'll add "resume_texts" to the /analyze response (see app.py updated).
}

// REVISED APPROACH: The /analyze response now includes resume_texts map.
// We store that on success. See the modified analyzeBtn handler below.

// Remove the original listener and re-add with text caching
document.getElementById("analyzeBtn").removeEventListener("click", _origAnalyze);
// (The listener added above with addEventListener is already in place —
//  we just need to patch the fetch block. We do this by making analyzeBtn
//  use a named async function that we can fully control.)

// Full analyze click handler (replaces the one above)
// Note: The addEventListener above already registered; we use a flag to avoid double calls.
let _analyzeBound = false;
if (!_analyzeBound) {
  _analyzeBound = true;
  // Remove all previous listeners by cloning
  const oldBtn = $("analyzeBtn");
  const newBtn  = oldBtn.cloneNode(true);
  oldBtn.parentNode.replaceChild(newBtn, oldBtn);

  newBtn.addEventListener("click", async () => {
    const jobText   = $("uploadJobText").value.trim();
    const resultsEl = $("uploadResults");

    if (!jobText) { showToast("Please paste a job description."); $("uploadJobText").focus(); return; }
    if (selectedFiles.length === 0) { showToast("Please upload at least one PDF resume."); return; }

    setLoading(newBtn, true);
    resultsEl.innerHTML = "";
    _resumeTexts = {};

    const formData = new FormData();
    formData.append("job_text", jobText);
    selectedFiles.forEach(f => formData.append("resumes", f));

    try {
      const res  = await fetch(`${API_BASE}/analyze`, { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) { renderError(data.error || `Server error (${res.status})`, resultsEl); return; }

      // Cache resume texts and bm25_max for whatif
      if (data.resume_texts) {
        _resumeTexts = data.resume_texts;
      }
      if (data.analyses && data.analyses.length > 0) {
        _whatifBm25Max = Math.max(...data.analyses.map(a => a.bm25_score || 0), 1);
      }

      renderAnalysis(data.analyses, resultsEl, data.parse_errors || []);
      showToast(`Analysed ${data.total_scored} resume${data.total_scored !== 1 ? "s" : ""} successfully.`);
    } catch (err) {
      console.error(err);
      renderError("Could not reach the server. Make sure Flask is running on port 5000.", resultsEl);
    } finally {
      setLoading(newBtn, false);
    }
  });
}

// Clear button (re-wire to new btn reference if needed)
$("uploadClear").addEventListener("click", () => {
  selectedFiles = [];
  renderFileList();
  $("uploadJobText").value = "";
  $("uploadCharCount").textContent = "0 characters";
  $("uploadResults").innerHTML = "";
  _resumeTexts = {};
});

/* ═══════════════════════════════════════════════════════════════════════
   DATABASE MATCH TAB (unchanged logic)
   ═══════════════════════════════════════════════════════════════════════ */

function scoreColorClass(score) {
  if (score >= 5) return "ring-high";
  if (score >= 2) return "ring-mid";
  return "ring-low";
}

function buildDbScoreBadge(score, maxScore) {
  const pct = maxScore > 0 ? Math.min(score / maxScore, 1) : 0;
  const offset = 163 * (1 - pct);
  return `
    <div class="score-badge">
      <div class="score-ring">
        <svg width="62" height="62" viewBox="0 0 62 62">
          <circle class="ring-track" cx="31" cy="31" r="26"/>
          <circle class="ring-fill ${scoreColorClass(score)}" cx="31" cy="31" r="26"
            style="stroke-dashoffset:163"
            data-offset="${offset}"/>
        </svg>
        <div class="score-value">${score.toFixed(2)}</div>
      </div>
      <span class="score-label">Score</span>
    </div>
  `;
}

function animateDbRings(container) {
  container.querySelectorAll(".score-ring .ring-fill[data-offset]").forEach(ring => {
    const target = parseFloat(ring.dataset.offset);
    requestAnimationFrame(() => { ring.style.strokeDashoffset = target; });
  });
}

function renderDbResults(results, container, parseErrors = []) {
  container.innerHTML = "";

  if (parseErrors.length > 0) {
    const eb = document.createElement("div");
    eb.className = "parse-errors";
    eb.innerHTML = parseErrors.map(e => `<div class="parse-error-item">⚠️ <strong>${esc(e.file)}</strong> — ${esc(e.error)}</div>`).join("");
    container.appendChild(eb);
  }

  if (!results || results.length === 0) {
    container.innerHTML += `<div class="state-card"><div class="state-icon">🔍</div><div class="state-title">No matches found</div><div class="state-msg">Try a more detailed job description.</div></div>`;
    return;
  }

  const maxScore = results[0].score;
  const hdr = document.createElement("div");
  hdr.className = "results-header";
  hdr.innerHTML = `<span class="results-title">Results</span><span class="results-meta">${results.length} resume${results.length > 1 ? "s" : ""} matched</span>`;
  container.appendChild(hdr);

  const list = document.createElement("div");
  list.className = "result-list";

  results.forEach((r, i) => {
    const card = document.createElement("div");
    card.className = "result-card";
    card.style.animationDelay = `${i * 55}ms`;
    const terms = r.matched_terms && r.matched_terms.length > 0
      ? r.matched_terms.map(t => `<span class="term-chip">${esc(t)}</span>`).join("")
      : `<span style="color:var(--text-3);font-size:0.78rem">No overlapping terms</span>`;
    card.innerHTML = `
      <div class="result-rank">${String(i + 1).padStart(2, "0")}</div>
      <div class="result-body">
        <div class="result-id">${esc(r.id)}</div>
        <div class="match-count-label">${r.match_count} matching term${r.match_count !== 1 ? "s" : ""}</div>
        <div class="matched-terms">${terms}</div>
      </div>
      ${buildDbScoreBadge(r.score, maxScore)}
    `;
    list.appendChild(card);
  });

  container.appendChild(list);
  requestAnimationFrame(() => animateDbRings(container));
}

$("dbMatchBtn").addEventListener("click", async () => {
  const jobText   = $("dbJobText").value.trim();
  const resultsEl = $("dbResults");
  const btn       = $("dbMatchBtn");

  if (!jobText) { showToast("Please paste a job description."); $("dbJobText").focus(); return; }

  setLoading(btn, true);
  resultsEl.innerHTML = "";

  try {
    const res  = await fetch(`${API_BASE}/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_text: jobText, top_k: topK })
    });
    const data = await res.json();
    if (!res.ok) { renderError(data.error || `Server error (${res.status})`, resultsEl); return; }
    renderDbResults(data.results, resultsEl);
    showToast(`Top ${data.top_k} matches retrieved from database.`);
  } catch (err) {
    console.error(err);
    renderError("Could not reach the server. Make sure Flask is running on port 5000.", resultsEl);
  } finally {
    setLoading(btn, false);
  }
});

$("dbClear").addEventListener("click", () => {
  $("dbJobText").value = "";
  $("dbCharCount").textContent = "0 characters";
  $("dbResults").innerHTML = "";
});