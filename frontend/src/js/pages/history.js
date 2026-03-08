/* ═══════════════════════════════════════════════
   pages/history.js — Match History page
   ═══════════════════════════════════════════════ */

let histPage = { offset: 0, total: 0, limit: 50 };

// ─── RENDER PAGE ────────────────────────────────
async function renderMatchHistory() {
  const pc = document.getElementById('page-content');

  pc.innerHTML = `
    <!-- Filters bar -->
    <div class="filters-bar">
      <input class="form-input" id="hist-search" style="width:260px"
             placeholder="Filter by resume or job..." oninput="applyHistFilters()">
      <input class="filter-input-sm" type="number" id="hist-jobid"    placeholder="Job ID"    oninput="applyHistFilters()">
      <input class="filter-input-sm" type="number" id="hist-resumeid" placeholder="Resume ID" oninput="applyHistFilters()">
      <select class="filter-select" id="hist-limit" onchange="applyHistFilters()">
        <option value="10">10 / page</option>
        <option value="25">25 / page</option>
        <option value="50" selected>50 / page</option>
        <option value="100">100 / page</option>
      </select>
      <button class="btn btn-ghost btn-sm" onclick="clearHistFilters()">Clear</button>
    </div>

    <!-- Table -->
    <div class="data-table" id="hist-table">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Resume File</th>
            <th>Job</th>
            <th>Company</th>
            <th>BM25 Score</th>
            <th>Terms Matched</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody id="hist-tbody">${skeletonRows(8, 7)}</tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination" id="hist-pagination"></div>`;

  loadHistory();
}

// ─── Load history from API ───────────────────────
async function loadHistory() {
  const jobId    = document.getElementById('hist-jobid')?.value    || '';
  const resumeId = document.getElementById('hist-resumeid')?.value || '';
  const limit    = parseInt(document.getElementById('hist-limit')?.value || '50');
  histPage.limit = limit;

  const tbody = document.getElementById('hist-tbody');
  if (tbody) tbody.innerHTML = skeletonRows(5, 7);

  try {
    let url = `/history?limit=${limit}`;
    if (jobId)    url += `&job_id=${jobId}`;
    if (resumeId) url += `&resume_id=${resumeId}`;

    const data = await api(url);
    const rows = Array.isArray(data) ? data : (data.results || []);
    state.history  = rows;
    histPage.total = data.total || rows.length;

    if (!tbody) return;

    if (!rows.length) {
      tbody.innerHTML = `
        <tr><td colspan="7">
          <div class="empty-state">
            ${svgEmptyClipboard()}
            <h3>No match history yet</h3>
            <p>Run a match to see results here.</p>
          </div>
        </td></tr>`;
    } else {
      // Apply local search filter on top
      const search   = (document.getElementById('hist-search')?.value || '').toLowerCase();
      const filtered = search
        ? rows.filter(r =>
            (r.resume_file || '').toLowerCase().includes(search) ||
            (r.job_code    || '').toLowerCase().includes(search))
        : rows;

      tbody.innerHTML = filtered.map((r, i) => `
        <tr>
          <td style="color:var(--text-muted)">${i + 1}</td>
          <td>
            <span title="${escHtml(r.resume_file || '')}" style="cursor:help">
              ${escHtml((r.resume_file || '').substring(0, 24))}${(r.resume_file || '').length > 24 ? '…' : ''}
            </span>
          </td>
          <td style="font-size:12px">${escHtml(r.job_code || r.job_title || '—')}</td>
          <td style="font-size:12px;color:var(--text-muted)">${escHtml(r.company_name || '—')}</td>
          <td><span class="score-badge ${scoreClass(r.bm25_score)}">${fmt4(r.bm25_score)}</span></td>
          <td style="color:var(--text-secondary)">${r.match_count || '—'} terms</td>
          <td style="font-size:12px;color:var(--text-muted)">${fmtDate(r.matched_at)}</td>
        </tr>`).join('');
    }

    // Pagination info
    const pag = document.getElementById('hist-pagination');
    if (pag) {
      pag.innerHTML = `
        <span class="pagination-info">Showing ${rows.length} of ${histPage.total} results</span>
        <div class="pagination-btns">
          <button class="btn btn-ghost btn-sm" disabled>← Prev</button>
          <button class="btn btn-ghost btn-sm" ${rows.length < limit ? 'disabled' : ''}>Next →</button>
        </div>`;
    }

  } catch (e) {
    if (tbody) {
      tbody.innerHTML = `
        <tr><td colspan="7">
          <div class="error-banner">⚠ ${escHtml(e.message)}</div>
        </td></tr>`;
    }
  }
}

// ─── Filter with debounce ────────────────────────
function applyHistFilters() {
  clearTimeout(window._histTimer);
  window._histTimer = setTimeout(loadHistory, 300);
}

// ─── Clear all filters ───────────────────────────
function clearHistFilters() {
  ['hist-search', 'hist-jobid', 'hist-resumeid'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const limitSel = document.getElementById('hist-limit');
  if (limitSel) limitSel.value = '50';
  loadHistory();
}
