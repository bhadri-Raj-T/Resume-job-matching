/* ═══════════════════════════════════════════════
   pages/dashboard.js — Dashboard page
   ═══════════════════════════════════════════════ */

async function renderDashboard() {
  const pc = document.getElementById('page-content');

  // Show skeleton immediately
  pc.innerHTML = `
    <div class="stat-grid" id="stat-grid">${skeletonCards(4)}</div>
    <div class="dashboard-row2">
      <div class="card dash-card" id="dash-history">
        <div class="card-header">
          <span class="card-title">Recent Matches</span>
          <a href="#" style="color:var(--primary);font-size:13px"
             onclick="navigate('history');return false">View All →</a>
        </div>
        <div style="text-align:center;padding:20px">
          <div class="spinner spinner-dark"></div>
        </div>
      </div>

      <div class="card dash-card" id="dash-quick">
        <div class="card-header"><span class="card-title">Quick Match</span></div>
        <div class="form-group" style="margin-bottom:12px">
          <textarea id="qm-text" class="form-input" style="height:120px"
            placeholder="Paste a job description here..."></textarea>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <label style="font-size:13px;color:var(--text-secondary)">Number of results</label>
          <input id="qm-topk" type="number" class="form-input"
            style="width:80px;text-align:center" value="5" min="1" max="20">
        </div>
        <button class="btn btn-primary btn-full" id="qm-btn" onclick="quickMatch()">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="white">
            <path d="M3 2l8 5-8 5V2z"/>
          </svg>
          Find Matches
        </button>
        <div id="qm-results"></div>
      </div>
    </div>`;

  // Fetch all data in parallel
  try {
    const [statsData, companiesData, histData] = await Promise.all([
      api('/').catch(() => ({ warehouse_resumes: 0, warehouse_jobs: 0, matcher_ready: false })),
      api('/companies').catch(() => []),
      api('/history?limit=5').catch(() => [])
    ]);

    const ready = statsData.matcher_ready;

    document.getElementById('stat-grid').innerHTML = `
      ${statCard('#EEF2FF', 'var(--primary)',  svgDocs(),      statsData.warehouse_resumes || 0, 'Resumes in Warehouse', ready ? 'green' : null, ready ? '+New' : null)}
      ${statCard('#ECFDF5', '#059669',          svgBriefcase(), statsData.warehouse_jobs    || 0, 'Job Postings',         null, null)}
      ${statCard('#FFF7ED', '#D97706',          svgBuilding(),  (companiesData || []).length,     'Companies Registered', null, null)}
      ${statCard('#FDF2F8', '#9333EA',          svgClock(),     (histData      || []).length,     'Total Matches Run',    null, null)}`;

    renderRecentHistory(histData || []);
  } catch (e) {
    document.getElementById('stat-grid').innerHTML =
      `<div class="error-banner" style="grid-column:1/-1">⚠ ${escHtml(e.message)}</div>`;
  }
}

// ─── Stat card HTML builder ─────────────────────
function statCard(iconBg, iconColor, icon, num, label, badgeType, badgeText) {
  return `
    <div class="card stat-card">
      <div class="stat-card-top">
        <div class="stat-icon" style="background:${iconBg};color:${iconColor}">${icon}</div>
        ${badgeText ? `<span class="trend-badge ${badgeType}">${badgeText}</span>` : ''}
      </div>
      <div class="stat-number">${(+num).toLocaleString()}</div>
      <div class="stat-label">${label}</div>
    </div>`;
}

// ─── Recent history table ───────────────────────
function renderRecentHistory(rows) {
  const el = document.getElementById('dash-history');
  if (!el) return;

  const header = `
    <div class="card-header">
      <span class="card-title">Recent Matches</span>
      <a href="#" style="color:var(--primary);font-size:13px"
         onclick="navigate('history');return false">View All →</a>
    </div>`;

  if (!rows.length) {
    el.innerHTML = header + `
      <div class="empty-state">
        ${svgEmptyInbox()}
        <h3>No matches yet</h3>
        <p>Run your first match to see results!</p>
      </div>`;
    return;
  }

  el.innerHTML = header + `
    <div style="overflow-x:auto">
      <table class="data-table">
        <thead>
          <tr>
            <th>Resume</th><th>Job</th><th>Company</th><th>Score</th><th>Date</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td class="truncate" style="max-width:140px" title="${escHtml(r.resume_file || '')}">
                <strong>${escHtml((r.resume_file || '').substring(0, 24))}${(r.resume_file || '').length > 24 ? '…' : ''}</strong>
              </td>
              <td style="font-size:12px">${escHtml(r.job_code || r.job_title || '')}</td>
              <td style="font-size:12px;color:var(--text-muted)">${escHtml(r.company_name || '—')}</td>
              <td><span class="score-badge ${scoreClass(r.bm25_score)}">${fmt4(r.bm25_score)}</span></td>
              <td style="font-size:12px;color:var(--text-muted)">${fmtDateShort(r.matched_at)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

// ─── Quick Match ────────────────────────────────
async function quickMatch() {
  const text = document.getElementById('qm-text').value.trim();
  if (!text) { toast('warning', 'Input needed', 'Please paste a job description.'); return; }

  const topk = parseInt(document.getElementById('qm-topk').value) || 5;
  const btn  = document.getElementById('qm-btn');

  btn.innerHTML = `<span class="spinner"></span> Matching...`;
  btn.disabled  = true;
  document.getElementById('qm-results').innerHTML = '';

  try {
    const data    = await api('/match', { method: 'POST', body: { job_text: text, top_k: topk } });
    const results = data.results || data || [];

    if (!results.length) {
      document.getElementById('qm-results').innerHTML =
        '<div class="empty-state" style="padding:20px"><p>No matches found. Upload more resumes.</p></div>';
    } else {
      document.getElementById('qm-results').innerHTML = results.map(r => `
        <div class="qm-result">
          <div>
            <div class="qm-filename" title="${escHtml(r.filename || r.resume_file || '')}">
              ${escHtml((r.filename || r.resume_file || '').substring(0, 30))}
            </div>
            <div class="qm-tags">${renderTags((r.matched_terms || []).slice(0, 5), 5)}</div>
          </div>
          <div class="qm-score">
            <div class="qm-score-num" style="color:${scoreColor(r.score || r.bm25_score)}">
              ${fmt4(r.score || r.bm25_score)}
            </div>
            <div class="qm-match-count">${r.match_count || r.matched_terms?.length || 0} terms</div>
          </div>
        </div>`).join('');
    }
    animateBars();
  } catch (e) {
    toast('error', 'Match failed', e.message);
  } finally {
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 14 14" fill="white"><path d="M3 2l8 5-8 5V2z"/></svg> Find Matches`;
    btn.disabled  = false;
  }
}
