/* ═══════════════════════════════════════════════
   pages/match.js — Match Resume page
   ═══════════════════════════════════════════════ */

async function renderMatchResume() {
  const pc = document.getElementById('page-content');

  pc.innerHTML = `
    <div class="match-layout">

      <!-- LEFT: Configuration panel -->
      <div class="match-left">
        <div class="card" style="padding:24px">
          <div class="card-header"><span class="card-title">Match Configuration</span></div>
          <div class="match-config-section">

            <!-- Method toggle -->
            <div class="form-group">
              <label class="form-label">Match Method</label>
              <div class="toggle-group">
                <div class="toggle-btn active" id="toggle-text" onclick="setMatchMethod('text')">By Job Description</div>
                <div class="toggle-btn"        id="toggle-code" onclick="setMatchMethod('code')">By Job Code</div>
              </div>
            </div>

            <!-- Text input (default visible) -->
            <div class="form-group" id="method-text-wrap">
              <label class="form-label">Job Description</label>
              <textarea id="match-jd" class="form-input" style="height:200px"
                placeholder="Paste the full job description here. Include skills, requirements, and responsibilities for best results."
                oninput="document.getElementById('match-charcount').textContent = this.value.length + ' / 2000'">
              </textarea>
              <div class="char-counter" id="match-charcount">0 / 2000</div>
            </div>

            <!-- Job code select (hidden by default) -->
            <div class="form-group" id="method-code-wrap" style="display:none">
              <label class="form-label">Select Job</label>
              <select class="form-input" id="match-job-select" onchange="onJobSelect(this)">
                <option value="">-- Select a job posting --</option>
              </select>
              <div id="job-preview-box" class="job-preview" style="display:none"></div>
            </div>

            <!-- Top K slider -->
            <div class="form-group">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
                <label class="form-label">Top K Results</label>
                <span class="slider-val" id="topk-val">5 results</span>
              </div>
              <input type="range" id="match-topk" min="1" max="20" value="5"
                style="width:100%;accent-color:var(--primary)"
                oninput="document.getElementById('topk-val').textContent = this.value + ' results'">
            </div>

            <!-- Run button -->
            <button class="btn btn-primary btn-full btn-lg" id="match-run-btn" onclick="runMatch()">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="white">
                <path d="M4 2.5l9 5.5-9 5.5V2.5z"/>
              </svg>
              Run Matching
            </button>

          </div>
        </div>
      </div>

      <!-- RIGHT: Results area -->
      <div class="match-right" id="match-right">
        <div class="match-empty">
          <svg width="120" height="120" viewBox="0 0 120 120" fill="none">
            <circle cx="52" cy="52" r="36" stroke="#EEF2FF" stroke-width="6"/>
            <circle cx="52" cy="52" r="26" stroke="#C7D2FE" stroke-width="4"/>
            <line x1="79" y1="79" x2="100" y2="100" stroke="#C7D2FE" stroke-width="7" stroke-linecap="round"/>
            <rect x="38" y="44" width="28" height="4" rx="2" fill="#A5B4FC"/>
            <rect x="38" y="52" width="20" height="4" rx="2" fill="#C7D2FE"/>
            <rect x="38" y="60" width="24" height="4" rx="2" fill="#C7D2FE"/>
          </svg>
          <h3 style="font-size:18px;color:var(--text-secondary);font-weight:700">Configure and run a match</h3>
          <p style="font-size:14px;color:var(--text-muted)">Results will appear here</p>
        </div>
      </div>

    </div>`;

  // Load jobs for the dropdown
  try {
    const jobs  = await api('/jobs');
    state.jobs  = jobs || [];
    populateJobSelect(jobs || []);
  } catch { /* dropdown stays empty */ }
}

// ─── Toggle between text / code methods ─────────
function setMatchMethod(m) {
  document.getElementById('toggle-text').classList.toggle('active', m === 'text');
  document.getElementById('toggle-code').classList.toggle('active', m === 'code');
  document.getElementById('method-text-wrap').style.display = m === 'text' ? 'flex' : 'none';
  document.getElementById('method-code-wrap').style.display = m === 'code' ? 'flex' : 'none';
  document.getElementById('match-run-btn').dataset.method   = m;
}

// ─── Populate job select dropdown ───────────────
function populateJobSelect(jobs) {
  const sel = document.getElementById('match-job-select');
  if (!sel) return;

  // Group by code prefix
  const groups = {};
  jobs.forEach(j => {
    const prefix = (j.job_code || '').split('_')[0] || 'Other';
    if (!groups[prefix]) groups[prefix] = [];
    groups[prefix].push(j);
  });

  let html = '<option value="">-- Select a job posting --</option>';
  Object.entries(groups).forEach(([g, items]) => {
    html += `<optgroup label="${escHtml(g)}">`;
    items.forEach(j => {
      html += `<option value="${escHtml(j.job_code)}">${escHtml(j.job_code)} – ${escHtml(j.title || '')}</option>`;
    });
    html += '</optgroup>';
  });
  sel.innerHTML = html;
}

// ─── Job select preview ─────────────────────────
function onJobSelect(sel) {
  const code = sel.value;
  const box  = document.getElementById('job-preview-box');
  if (!code) { box.style.display = 'none'; return; }

  const job = state.jobs.find(j => j.job_code === code);
  if (!job)  { box.style.display = 'none'; return; }

  box.style.display = 'block';
  box.innerHTML = `
    <div class="job-preview-title">${escHtml(job.title || job.job_code)}</div>
    <div class="job-preview-company">${escHtml(job.company_name || '')}</div>
    <div style="font-size:12px;color:var(--text-secondary)">
      ${escHtml((job.description || '').substring(0, 150))}${(job.description || '').length > 150 ? '…' : ''}
    </div>`;
}

// ─── Run matching ────────────────────────────────
async function runMatch() {
  const btn    = document.getElementById('match-run-btn');
  const method = btn.dataset.method || 'text';
  const topk   = parseInt(document.getElementById('match-topk').value) || 5;
  const right  = document.getElementById('match-right');

  btn.innerHTML = `<span class="spinner"></span> Analysing resumes...`;
  btn.disabled  = true;
  right.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:center;height:200px">
      <div class="spinner spinner-dark" style="width:32px;height:32px;border-width:3px"></div>
    </div>`;

  try {
    let results, jobLabel = '';

    if (method === 'code') {
      const code = document.getElementById('match-job-select').value;
      if (!code) {
        toast('warning', 'Select a job', 'Please choose a job from the dropdown.');
        throw new Error('no code');
      }
      const data = await api(`/match/job/${encodeURIComponent(code)}?top_k=${topk}`);
      results    = data.results || data || [];
      const job  = state.jobs.find(j => j.job_code === code);
      jobLabel   = job ? (job.title || code) : code;

    } else {
      const text = document.getElementById('match-jd').value.trim();
      if (!text) {
        toast('warning', 'Input needed', 'Please paste a job description.');
        throw new Error('no text');
      }
      const data = await api('/match', { method: 'POST', body: { job_text: text, top_k: topk } });
      results    = data.results || data || [];
      jobLabel   = text.substring(0, 60) + (text.length > 60 ? '…' : '');
    }

    state.lastMatchResults = results;
    renderMatchResults(results, jobLabel);

  } catch (e) {
    if (e.message !== 'no code' && e.message !== 'no text') {
      toast('error', 'Match failed', e.message);
    }
    right.innerHTML = `
      <div class="match-empty">
        <svg width="80" height="80" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="32" fill="#FEE2E2"/>
          <text x="40" y="48" text-anchor="middle" font-size="24" fill="#EF4444">⚠</text>
        </svg>
        <h3>Match failed</h3>
        <p>${escHtml(e.message)}</p>
      </div>`;
  } finally {
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="white"><path d="M4 2.5l9 5.5-9 5.5V2.5z"/></svg> Run Matching`;
    btn.disabled  = false;
  }
}

// ─── Render result cards ─────────────────────────
function renderMatchResults(results, jobLabel) {
  const right = document.getElementById('match-right');

  if (!results.length) {
    right.innerHTML = `
      <div class="match-empty">
        ${svgEmptyInbox()}
        <h3>No matching resumes found</h3>
        <p>Try uploading more resumes or adjusting your job description.</p>
      </div>`;
    return;
  }

  right.innerHTML = `
    <div class="results-header">
      <div>
        <div style="display:flex;align-items:center">
          <span class="results-title">Match Results</span>
          <span class="results-count-badge">${results.length} results</span>
        </div>
        <div class="results-subtitle">${escHtml(jobLabel)}</div>
      </div>
      <div class="results-sort">
        <select class="filter-select" id="results-sort-sel"
          onchange="sortResults(this.value)" style="font-size:13px">
          <option value="score">Sort by Score ▾</option>
          <option value="name">Sort by Name</option>
        </select>
      </div>
    </div>
    <div class="results-stack" id="results-stack">
      ${buildResultCards(results)}
    </div>`;

  animateBars();
}

function buildResultCards(results) {
  return results.map((r, i) => {
    const score      = r.score ?? r.bm25_score ?? 0;
    const fname      = r.filename || r.resume_file || 'Unknown';
    const terms      = r.matched_terms || [];
    const matchCount = r.match_count ?? terms.length;

    return `
      <div class="card result-card">
        <div class="result-card-top">
          <div style="display:flex;align-items:center;min-width:0">
            <div class="rank-badge ${i < 3 ? 'top' : ''}">${i + 1}</div>
            <span class="result-filename" title="${escHtml(fname)}">${escHtml(fname)}</span>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div class="result-score-num" style="color:${scoreColor(score)}">${fmt4(score)}</div>
            <div class="result-score-label">BM25 Score</div>
          </div>
        </div>
        <div class="result-middle">${scoreBarHtml(score)}</div>
        <div class="result-bottom">
          <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px">
            <span class="result-terms-label">Matched:</span>
            <div class="result-tags">${renderTags(terms)}</div>
          </div>
          <span class="result-match-count">${matchCount} terms matched</span>
        </div>
      </div>`;
  }).join('');
}

// ─── Sort results ────────────────────────────────
function sortResults(by) {
  if (!state.lastMatchResults) return;
  const sorted = [...state.lastMatchResults].sort((a, b) => {
    if (by === 'score') return (b.score ?? b.bm25_score ?? 0) - (a.score ?? a.bm25_score ?? 0);
    return (a.filename || a.resume_file || '').localeCompare(b.filename || b.resume_file || '');
  });
  document.getElementById('results-stack').innerHTML = buildResultCards(sorted);
  animateBars();
}
