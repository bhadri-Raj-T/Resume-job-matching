/* ═══════════════════════════════════════════════
   pages/jobs.js — Browse Jobs page
   ═══════════════════════════════════════════════ */

let jobsView   = 'grid';
let jobsFilter = { search: '', category: '' };

// ─── RENDER PAGE ────────────────────────────────
async function renderBrowseJobs(filterCompany) {
  const pc = document.getElementById('page-content');

  pc.innerHTML = `
    <div class="toolbar">
      <div class="toolbar-left">
        <div class="search-wrap">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
               stroke="currentColor" stroke-width="1.5">
            <circle cx="7" cy="7" r="5"/>
            <line x1="11" y1="11" x2="15" y2="15" stroke-linecap="round"/>
          </svg>
          <input class="form-input search-input" id="job-search"
                 placeholder="Search jobs or skills..." oninput="filterJobs()">
        </div>
        <select class="filter-select" id="job-cat-filter" onchange="filterJobs()">
          <option value="">All Categories</option>
        </select>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-primary btn-sm" onclick="openAddJobModal()">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="white">
            <line x1="7" y1="2" x2="7" y2="12" stroke="white" stroke-width="2" stroke-linecap="round"/>
            <line x1="2" y1="7" x2="12" y2="7" stroke="white" stroke-width="2" stroke-linecap="round"/>
          </svg>
          Add Job
        </button>
        <button class="view-toggle-btn ${jobsView === 'grid' ? 'active' : ''}"
                id="view-grid-btn" onclick="setJobView('grid')" title="Grid view">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <rect x="0" y="0" width="6" height="6" rx="1"/>
            <rect x="8" y="0" width="6" height="6" rx="1"/>
            <rect x="0" y="8" width="6" height="6" rx="1"/>
            <rect x="8" y="8" width="6" height="6" rx="1"/>
          </svg>
        </button>
        <button class="view-toggle-btn ${jobsView === 'list' ? 'active' : ''}"
                id="view-list-btn" onclick="setJobView('list')" title="List view">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <rect x="0" y="1"  width="14" height="2" rx="1"/>
            <rect x="0" y="6"  width="14" height="2" rx="1"/>
            <rect x="0" y="11" width="14" height="2" rx="1"/>
          </svg>
        </button>
      </div>
    </div>
    <div id="jobs-container">${skeletonCards(6)}</div>`;

  // Pre-fill search if navigated from company page
  if (filterCompany) {
    jobsFilter.search = filterCompany;
    const s = document.getElementById('job-search');
    if (s) s.value = filterCompany;
  }

  try {
    const [jobs, companies] = await Promise.all([
      api('/jobs'),
      api('/companies').catch(() => [])
    ]);
    state.jobs      = jobs      || [];
    state.companies = companies || [];

    // Populate category filter
    const cats   = [...new Set((jobs || []).map(j => (j.job_code || '').split('_')[0]).filter(Boolean))];
    const catSel = document.getElementById('job-cat-filter');
    cats.forEach(c => {
      const o = document.createElement('option');
      o.value = c; o.textContent = c;
      catSel.appendChild(o);
    });

    renderJobCards();
  } catch (e) {
    document.getElementById('jobs-container').innerHTML =
      `<div class="error-banner">⚠ ${escHtml(e.message)}</div>`;
  }
}

// ─── Filter jobs ─────────────────────────────────
function filterJobs() {
  jobsFilter.search   = (document.getElementById('job-search')?.value    || '').toLowerCase();
  jobsFilter.category =  document.getElementById('job-cat-filter')?.value || '';
  renderJobCards();
}

// ─── Toggle grid / list view ────────────────────
function setJobView(v) {
  jobsView = v;
  document.getElementById('view-grid-btn')?.classList.toggle('active', v === 'grid');
  document.getElementById('view-list-btn')?.classList.toggle('active', v === 'list');
  renderJobCards();
}

// ─── Render job cards ────────────────────────────
function renderJobCards() {
  const cont = document.getElementById('jobs-container');
  if (!cont) return;

  let jobs = state.jobs;
  if (jobsFilter.search) {
    jobs = jobs.filter(j =>
      (j.title        || '').toLowerCase().includes(jobsFilter.search) ||
      (j.description  || '').toLowerCase().includes(jobsFilter.search) ||
      (j.company_name || '').toLowerCase().includes(jobsFilter.search) ||
      (j.job_code     || '').toLowerCase().includes(jobsFilter.search)
    );
  }
  if (jobsFilter.category) {
    jobs = jobs.filter(j => (j.job_code || '').startsWith(jobsFilter.category));
  }

  if (!jobs.length) {
    cont.innerHTML = `
      <div class="empty-state">
        ${svgEmptyInbox()}
        <h3>No jobs found</h3>
        <p>Try a different search or add a new job posting.</p>
        <button class="btn btn-primary" onclick="openAddJobModal()">Add Job</button>
      </div>`;
    return;
  }

  cont.className = jobsView === 'grid' ? 'jobs-grid' : 'jobs-list';
  cont.innerHTML = jobs.map((j, i) => {
    const skills = extractSkills(j.description || '');
    return `
      <div class="card job-card"
           style="animation-delay:${i * 40}ms;animation:fadeSlideIn 0.3s ease both">
        <div class="job-card-top">
          <span class="job-code-badge">${escHtml(j.job_code || '')}</span>
          <span class="job-company">${escHtml(j.company_name || '')}</span>
        </div>
        <div class="job-title">${escHtml(j.title || j.job_code || 'Untitled')}</div>
        <div class="job-desc">${escHtml(j.description || 'No description available.')}</div>
        <div class="job-skills">
          ${skills.map(s => `<span class="tag tag-neutral">${escHtml(s)}</span>`).join('')}
        </div>
        <div class="job-card-footer">
          <span class="job-date">🕐 ${fmtDateShort(j.created_at || j.added_at) || 'Recently'}</span>
          <span class="job-match-btn" onclick="matchJob('${escHtml(j.job_code || '')}')">Match Resumes →</span>
        </div>
      </div>`;
  }).join('');
}

// ─── Navigate to Match page with this job pre-selected ──
function matchJob(code) {
  navigate('match');
  setTimeout(() => {
    setMatchMethod('code');
    const sel = document.getElementById('match-job-select');
    if (sel) { sel.value = code; onJobSelect(sel); }
  }, 400);
}

// ═══════════════════════════════════════════════
// ADD JOB MODAL
// ═══════════════════════════════════════════════
function openAddJobModal() {
  const companies = state.companies || [];

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id        = 'add-job-modal';
  overlay.innerHTML = `
    <div class="modal-box">
      <div class="modal-header">
        <span class="modal-title">Add New Job Posting</span>
        <button class="modal-close" onclick="document.getElementById('add-job-modal').remove()">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="4" x2="14" y2="14"/>
            <line x1="14" y1="4" x2="4" y2="14"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label">Job Code *</label>
          <input class="form-input" id="aj-code" placeholder="e.g. DEV_004">
          <div class="form-helper">Format: PREFIX_NUMBER (e.g. DS_005)</div>
        </div>
        <div class="form-group">
          <label class="form-label">Job Title</label>
          <input class="form-input" id="aj-title" placeholder="e.g. Senior Backend Developer">
        </div>
        <div class="form-group">
          <label class="form-label">Company</label>
          <select class="form-input" id="aj-company" onchange="onAJCompanyChange(this)">
            <option value="">-- Select company --</option>
            ${companies.map(c =>
              `<option value="${escHtml(c.name || c.company_name || '')}">
                ${escHtml(c.name || c.company_name || '')}
               </option>`
            ).join('')}
            <option value="__new__">New company...</option>
          </select>
        </div>
        <div class="form-group" id="aj-new-company-wrap" style="display:none">
          <label class="form-label">New Company Name</label>
          <input class="form-input" id="aj-new-company" placeholder="Company name">
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea class="form-input" id="aj-desc" style="height:140px"
            placeholder="Full job description..."></textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="document.getElementById('add-job-modal').remove()">Cancel</button>
        <button class="btn btn-primary" id="aj-submit" onclick="submitAddJob()">Add Job</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

function onAJCompanyChange(sel) {
  document.getElementById('aj-new-company-wrap').style.display =
    sel.value === '__new__' ? 'flex' : 'none';
}

async function submitAddJob() {
  const code  = document.getElementById('aj-code').value.trim();
  const title = document.getElementById('aj-title').value.trim();
  const desc  = document.getElementById('aj-desc').value.trim();
  let company = document.getElementById('aj-company').value;
  if (company === '__new__') company = document.getElementById('aj-new-company').value.trim();

  if (!code) { toast('warning', 'Job code required', 'Please enter a job code.'); return; }

  const btn   = document.getElementById('aj-submit');
  btn.innerHTML = `<span class="spinner"></span>`;
  btn.disabled  = true;

  try {
    await api('/jobs', { method: 'POST', body: { job_code: code, title, description: desc, company_name: company } });
    document.getElementById('add-job-modal')?.remove();
    toast('success', 'Job added', `${code} has been added.`);
    renderBrowseJobs();
  } catch (e) {
    toast('error', 'Failed to add job', e.message);
    btn.innerHTML = 'Add Job';
    btn.disabled  = false;
  }
}
