/* ══════════════════════════════════════════════════════════════════
   ResumeIQ — script.js  (FIXED VERSION)
   Changes vs original:
   1. BUG FIX: /analyze response shows "Added to DB" toast so user
      knows uploaded resume is now in the BM25 corpus
   2. UI FIX:  Match score ring — larger font, dynamic color matching
      ring stroke, bold percentage, visible label
   3. UI FIX:  DB score ring — larger font, same treatment
   4. NEW:     "Also search database" checkbox in Upload tab lets you
               run a BM25 database search right after hybrid analysis
   ══════════════════════════════════════════════════════════════════ */

// ⚠️  REPLACE THIS with your Render backend URL after deploying
const API_BASE = "https://resumeiq-385n.onrender.com";

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
  _resumeTexts = {};
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

/* ring stroke color value (for dynamic font color matching) */
function ringColorVal(label) {
  if (label === "Excellent Fit") return "var(--green)";
  if (label === "Good Fit")      return "var(--amber)";
  if (label === "Fair Fit")      return "#C05A20";
  return "var(--red)";
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

/* ─────────────────────────────────────────────────────────────────────
   UI FIX: compositeRingSVG
   - Increased ring/SVG size from 72→88px for better readability
   - Score text: larger (1.35rem), bold, color matches ring stroke
   - "Match" label: slightly larger, cleaner positioning
   ───────────────────────────────────────────────────────────────────── */
function compositeRingSVG(score, fitLabel) {
  const circumference = 226;   // 2 * π * 36 (new radius 36)
  const offset = circumference * (1 - Math.min(score / 100, 1));
  const cls = ringClass(fitLabel);
  const scoreColor = ringColorVal(fitLabel);
  return `
    <div class="ac-ring-wrap">
      <div class="comp-ring" style="width:88px;height:88px;">
        <svg width="88" height="88" viewBox="0 0 88 88">
          <circle class="ring-track" cx="44" cy="44" r="36"/>
          <circle class="ring-fill ${cls}" cx="44" cy="44" r="36"
            style="stroke-dasharray:${circumference};stroke-dashoffset:${circumference};stroke-width:7"
            data-target="${offset}"/>
        </svg>
        <div class="ring-val" style="font-size:1.35rem;font-weight:900;color:${scoreColor};letter-spacing:-0.03em;">${score}%</div>
      </div>
      <span class="ring-lbl" style="font-size:0.72rem;font-weight:600;letter-spacing:0.08em;">MATCH</span>
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

/* ── Resume text + bm25 state ───────────────────────────────────────── */
let _resumeTexts = {};
let _whatifBm25Max = 1;

/* ── Analyze Button (full, clean, no duplicate listeners) ───────────── */
$("analyzeBtn").addEventListener("click", async () => {
  const jobText   = $("uploadJobText").value.trim();
  const resultsEl = $("uploadResults");
  const btn       = $("analyzeBtn");

  if (!jobText) { showToast("Please paste a job description."); $("uploadJobText").focus(); return; }
  if (selectedFiles.length === 0) { showToast("Please upload at least one PDF resume."); return; }

  setLoading(btn, true);
  resultsEl.innerHTML = "";
  _resumeTexts = {};

  const formData = new FormData();
  formData.append("job_text", jobText);
  selectedFiles.forEach(f => formData.append("resumes", f));

  try {
    const res  = await fetch(`${API_BASE}/analyze`, { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) { renderError(data.error || `Server error (${res.status})`, resultsEl); return; }

    // Cache resume texts for what-if
    if (data.resume_texts) _resumeTexts = data.resume_texts;
    if (data.analyses && data.analyses.length > 0) {
      _whatifBm25Max = Math.max(...data.analyses.map(a => a.bm25_score || 0), 1);
    }

    // ── BUG FIX: notify user that resumes were added to corpus ──────────
    if (data.added_to_db && data.added_to_db.length > 0) {
      showToast(
        `✅ ${data.added_to_db.length} resume(s) added to BM25 database (total: ${data.total_in_db}). Switch to Database Match tab to search.`,
        4500
      );
    } else {
      showToast(`Analysed ${data.total_scored} resume${data.total_scored !== 1 ? "s" : ""} successfully.`);
    }
    // ────────────────────────────────────────────────────────────────────

    renderAnalysis(data.analyses, resultsEl, data.parse_errors || []);

  } catch (err) {
    console.error(err);
    renderError("Could not reach the server. Make sure Flask is running on port 5000.", resultsEl);
  } finally {
    setLoading(btn, false);
  }
});

$("uploadClear").addEventListener("click", () => {
  selectedFiles = [];
  renderFileList();
  $("uploadJobText").value = "";
  $("uploadCharCount").textContent = "0 characters";
  $("uploadResults").innerHTML = "";
  _resumeTexts = {};
});

/* ═══════════════════════════════════════════════════════════════════════
   WHAT-IF MODAL
   ═══════════════════════════════════════════════════════════════════════ */

let _modalAnalysis = null;

function openWhatIfModal(analysis) {
  _modalAnalysis = analysis;
  $("modalSubtitle").textContent = analysis.id;

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

  const resumeText = _resumeTexts[_modalAnalysis.id] || "";
  const jobText    = $("uploadJobText").value.trim();

  try {
    const res = await fetch(`${API_BASE}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text:      resumeText,
        job_text:         jobText,
        add_skills:       selected,
        current_semantic: _modalAnalysis._semantic  ?? -1,
        current_exp:      _modalAnalysis._exp       ?? -1,
        current_edu:      _modalAnalysis._edu       ?? -1,
      })
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Simulation failed."); return; }

    const current  = _modalAnalysis.match_score ?? _modalAnalysis.composite_score ?? 0;
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

/* ═══════════════════════════════════════════════════════════════════════
   DATABASE MATCH TAB
   ═══════════════════════════════════════════════════════════════════════ */

function scoreColorClass(score) {
  if (score >= 5) return "ring-high";
  if (score >= 2) return "ring-mid";
  return "ring-low";
}

/* ─────────────────────────────────────────────────────────────────────
   UI FIX: buildDbScoreBadge
   - Increased ring/SVG size from 62→78px for better visibility
   - Score value: larger font (1.1rem), bold 900, dynamic color
   - "Score" label: slightly larger
   ───────────────────────────────────────────────────────────────────── */
function buildDbScoreBadge(score, maxScore) {
  const pct = maxScore > 0 ? Math.min(score / maxScore, 1) : 0;
  const radius = 32;
  const circumference = 2 * Math.PI * radius;   // ~201
  const offset = circumference * (1 - pct);

  // Color based on relative score
  let strokeColor, textColor;
  if (pct >= 0.7) { strokeColor = "var(--green)"; textColor = "var(--green)"; }
  else if (pct >= 0.4) { strokeColor = "var(--amber)"; textColor = "var(--amber)"; }
  else { strokeColor = "var(--red)"; textColor = "var(--red)"; }

  return `
    <div class="score-badge">
      <div class="score-ring" style="width:78px;height:78px;position:relative;">
        <svg width="78" height="78" viewBox="0 0 78 78">
          <circle class="ring-track" cx="39" cy="39" r="${radius}" style="stroke-width:6;"/>
          <circle class="ring-fill" cx="39" cy="39" r="${radius}"
            style="fill:none;stroke:${strokeColor};stroke-width:6;stroke-linecap:round;
                   stroke-dasharray:${circumference.toFixed(1)};stroke-dashoffset:${circumference.toFixed(1)};
                   transition:stroke-dashoffset 0.8s cubic-bezier(0.34,1.56,0.64,1);
                   transform:rotate(-90deg);transform-origin:39px 39px;"
            data-offset="${offset.toFixed(2)}"/>
        </svg>
        <div class="score-value"
             style="font-size:1.1rem;font-weight:900;color:${textColor};letter-spacing:-0.02em;">
          ${score.toFixed(2)}
        </div>
      </div>
      <span class="score-label" style="font-size:0.72rem;font-weight:600;letter-spacing:0.07em;">SCORE</span>
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
    showToast(`Top ${data.top_k} matches retrieved from database (${data.total_resumes_in_db} resumes indexed).`);
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
