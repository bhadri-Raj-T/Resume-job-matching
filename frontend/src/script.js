/* ══════════════════════════════════════════════════════════
   ResumeIQ — script.js
   Handles: tab navigation, drag-drop file upload, API calls,
            animated score rings, result rendering, toast alerts.
   ══════════════════════════════════════════════════════════ */

const API_BASE = "http://127.0.0.1:5000";

/* ── Helpers ────────────────────────────────────────────── */

function $(id) { return document.getElementById(id); }

function showToast(msg, duration = 3000) {
  const toast = $("toast");
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), duration);
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function setLoading(btn, isLoading) {
  if (isLoading) {
    btn.dataset.originalHtml = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span><span class="btn-text">Analysing…</span>`;
    btn.classList.add("loading");
  } else {
    btn.innerHTML = btn.dataset.originalHtml || btn.innerHTML;
    btn.classList.remove("loading");
  }
}

/* ── Tab Navigation ─────────────────────────────────────── */

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

/* ── Char counters ──────────────────────────────────────── */

function attachCharCounter(textareaId, counterId) {
  const ta = $(textareaId);
  const counter = $(counterId);
  ta.addEventListener("input", () => {
    const len = ta.value.length;
    counter.textContent = `${len.toLocaleString()} character${len !== 1 ? "s" : ""}`;
  });
}

attachCharCounter("uploadJobText", "uploadCharCount");
attachCharCounter("dbJobText", "dbCharCount");

/* ── File Management (Upload tab) ───────────────────────── */

let selectedFiles = [];   // Array of File objects (de-duplicated)

function renderFileList() {
  const list = $("fileList");
  list.innerHTML = "";
  selectedFiles.forEach((file, idx) => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `
      <div class="file-icon">PDF</div>
      <span class="file-name">${file.name}</span>
      <span class="file-size">${formatBytes(file.size)}</span>
      <button class="file-remove" data-idx="${idx}" title="Remove">✕</button>
    `;
    list.appendChild(item);
  });

  // Remove buttons
  list.querySelectorAll(".file-remove").forEach(btn => {
    btn.addEventListener("click", () => {
      selectedFiles.splice(parseInt(btn.dataset.idx), 1);
      renderFileList();
    });
  });
}

function addFiles(newFiles) {
  const existing = new Set(selectedFiles.map(f => f.name + f.size));
  Array.from(newFiles).forEach(f => {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      showToast(`"${f.name}" skipped — only PDF files are supported.`);
      return;
    }
    const key = f.name + f.size;
    if (!existing.has(key)) {
      selectedFiles.push(f);
      existing.add(key);
    }
  });
  renderFileList();
}

// File input change
$("resumeFiles").addEventListener("change", e => {
  addFiles(e.target.files);
  e.target.value = ""; // allow re-selecting same file
});

// Drag & Drop
const dropZone = $("dropZone");

dropZone.addEventListener("click", () => $("resumeFiles").click());

["dragenter", "dragover"].forEach(evt => {
  dropZone.addEventListener(evt, e => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach(evt => {
  dropZone.addEventListener(evt, () => dropZone.classList.remove("dragover"));
});

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  addFiles(e.dataTransfer.files);
});

// Clear button (upload tab)
$("uploadClear").addEventListener("click", () => {
  selectedFiles = [];
  renderFileList();
  $("uploadJobText").value = "";
  $("uploadCharCount").textContent = "0 characters";
  $("uploadResults").innerHTML = "";
});

// Clear button (db tab)
$("dbClear").addEventListener("click", () => {
  $("dbJobText").value = "";
  $("dbCharCount").textContent = "0 characters";
  $("dbResults").innerHTML = "";
});

/* ── Top-K Stepper ──────────────────────────────────────── */

let topK = 5;
const topKEl = $("topKVal");

$("stepUp").addEventListener("click", () => {
  topK = Math.min(topK + 1, 20);
  topKEl.textContent = topK;
});

$("stepDown").addEventListener("click", () => {
  topK = Math.max(topK - 1, 1);
  topKEl.textContent = topK;
});

/* ── Score Ring Renderer ─────────────────────────────────── */

function scoreColor(score) {
  if (score >= 5)  return "ring-high";
  if (score >= 2)  return "ring-mid";
  return "ring-low";
}

/**
 * BM25 scores don't have a fixed maximum — we normalise to the
 * highest score in the result set for the ring fill.
 */
function buildScoreBadge(score, maxScore) {
  const pct = maxScore > 0 ? Math.min(score / maxScore, 1) : 0;
  const circumference = 163;
  const offset = circumference * (1 - pct);
  const colorClass = scoreColor(score);

  return `
    <div class="score-badge">
      <div class="score-ring">
        <svg width="64" height="64" viewBox="0 0 64 64">
          <circle class="ring-track" cx="32" cy="32" r="26"/>
          <circle class="ring-fill ${colorClass}" cx="32" cy="32" r="26"
            style="stroke-dashoffset: ${circumference}"
            data-offset="${offset}"/>
        </svg>
        <div class="score-value">${score.toFixed(2)}</div>
      </div>
      <span class="score-label">Score</span>
    </div>
  `;
}

function animateRings(container) {
  container.querySelectorAll(".ring-fill").forEach(ring => {
    const target = parseFloat(ring.dataset.offset);
    requestAnimationFrame(() => {
      ring.style.strokeDashoffset = target;
    });
  });
}

/* ── Result Renderer ─────────────────────────────────────── */

function renderResults(results, container, parseErrors = []) {
  container.innerHTML = "";

  // Parse error warnings
  if (parseErrors.length > 0) {
    const errBlock = document.createElement("div");
    errBlock.className = "parse-errors";
    errBlock.innerHTML = parseErrors.map(e => `
      <div class="parse-error-item">
        ⚠️ <strong>${e.file}</strong> — ${e.error}
      </div>
    `).join("");
    container.appendChild(errBlock);
  }

  if (!results || results.length === 0) {
    container.innerHTML += `
      <div class="state-card">
        <div class="state-icon">🔍</div>
        <div class="state-title">No matches found</div>
        <div class="state-msg">Try a more detailed job description or check that the PDFs contain readable text.</div>
      </div>`;
    return;
  }

  const maxScore = results[0].score;  // sorted descending, first is highest

  const header = document.createElement("div");
  header.className = "results-header";
  header.innerHTML = `
    <span class="results-title">Results</span>
    <span class="results-meta">${results.length} resume${results.length > 1 ? "s" : ""} ranked</span>
  `;
  container.appendChild(header);

  const list = document.createElement("div");
  list.className = "result-list";

  results.forEach((r, i) => {
    const card = document.createElement("div");
    card.className = "result-card";
    card.style.animationDelay = `${i * 60}ms`;

    const terms = r.matched_terms && r.matched_terms.length > 0
      ? r.matched_terms.map(t => `<span class="term-chip">${t}</span>`).join("")
      : `<span style="color:var(--text-3);font-size:0.8rem">No overlapping terms found</span>`;

    card.innerHTML = `
      <div class="result-rank">${String(i + 1).padStart(2, "0")}</div>
      <div class="result-body">
        <div class="result-id">${r.id}</div>
        <div class="match-count-label">${r.match_count} matching term${r.match_count !== 1 ? "s" : ""}</div>
        <div class="matched-terms">${terms}</div>
      </div>
      ${buildScoreBadge(r.score, maxScore)}
    `;
    list.appendChild(card);
  });

  container.appendChild(list);

  // Trigger ring animations after DOM insertion
  requestAnimationFrame(() => animateRings(container));
}

function renderError(message, container) {
  container.innerHTML = `
    <div class="state-card error-card">
      <div class="state-icon">✕</div>
      <div class="state-title">Something went wrong</div>
      <div class="state-msg">${message}</div>
    </div>
  `;
}

/* ── Upload & Match ──────────────────────────────────────── */

$("uploadBtn").addEventListener("click", async () => {
  const jobText  = $("uploadJobText").value.trim();
  const resultsEl = $("uploadResults");
  const btn = $("uploadBtn");

  if (!jobText) {
    showToast("Please paste a job description.");
    $("uploadJobText").focus();
    return;
  }

  if (selectedFiles.length === 0) {
    showToast("Please upload at least one PDF resume.");
    return;
  }

  setLoading(btn, true);
  resultsEl.innerHTML = "";

  const formData = new FormData();
  formData.append("job_text", jobText);
  selectedFiles.forEach(f => formData.append("resumes", f));

  try {
    const response = await fetch(`${API_BASE}/upload_match`, {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      renderError(data.error || `Server error (${response.status})`, resultsEl);
      return;
    }

    renderResults(data.results, resultsEl, data.parse_errors || []);
    showToast(`Ranked ${data.total_scored} resume${data.total_scored !== 1 ? "s" : ""} successfully.`);
  } catch (err) {
    console.error(err);
    renderError("Could not reach the server. Make sure Flask is running on port 5000.", resultsEl);
  } finally {
    setLoading(btn, false);
  }
});

/* ── Database Match ──────────────────────────────────────── */

$("dbMatchBtn").addEventListener("click", async () => {
  const jobText   = $("dbJobText").value.trim();
  const resultsEl = $("dbResults");
  const btn = $("dbMatchBtn");

  if (!jobText) {
    showToast("Please paste a job description.");
    $("dbJobText").focus();
    return;
  }

  setLoading(btn, true);
  resultsEl.innerHTML = "";

  try {
    const response = await fetch(`${API_BASE}/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_text: jobText, top_k: topK })
    });

    const data = await response.json();

    if (!response.ok) {
      renderError(data.error || `Server error (${response.status})`, resultsEl);
      return;
    }

    renderResults(data.results, resultsEl);
    showToast(`Top ${data.top_k} matches retrieved from database.`);
  } catch (err) {
    console.error(err);
    renderError("Could not reach the server. Make sure Flask is running on port 5000.", resultsEl);
  } finally {
    setLoading(btn, false);
  }
});