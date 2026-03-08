/* ═══════════════════════════════════════════════
   pages/companies.js — Companies page
   ═══════════════════════════════════════════════ */

// ─── RENDER PAGE ────────────────────────────────
async function renderCompanies() {
  const pc = document.getElementById('page-content');

  pc.innerHTML = `
    <div style="display:flex;justify-content:flex-end;margin-bottom:20px">
      <button class="btn btn-primary" onclick="openAddCompanyModal()">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="white">
          <line x1="7" y1="2" x2="7" y2="12" stroke="white" stroke-width="2" stroke-linecap="round"/>
          <line x1="2" y1="7" x2="12" y2="7" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
        Add Company
      </button>
    </div>
    <div class="companies-grid" id="companies-grid">${skeletonCards(6)}</div>`;

  try {
    const companies  = await api('/companies');
    state.companies  = companies || [];
    const grid       = document.getElementById('companies-grid');

    if (!companies || !companies.length) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          ${svgEmptyInbox()}
          <h3>No companies yet</h3>
          <p>Add your first company to get started.</p>
          <button class="btn btn-primary" onclick="openAddCompanyModal()">Add Company</button>
        </div>`;
      return;
    }

    grid.innerHTML = companies.map((c, i) => {
      const name   = c.name || c.company_name || '?';
      const letter = name[0].toUpperCase();
      const bg     = hslFromName(name);

      return `
        <div class="card company-card"
             style="animation:fadeSlideIn 0.3s ease ${i * 50}ms both">
          <div class="company-avatar" style="background:${bg}">${letter}</div>
          <div class="company-name">${escHtml(name)}</div>
          <span class="company-industry">${escHtml(c.industry || 'Unknown')}</span>
          ${c.website ? `<div class="company-website">${escHtml(c.website)}</div>` : ''}
          <div class="company-date">${fmtDateShort(c.created_at || c.added_at) || ''}</div>
          <div class="company-footer">
            <span class="company-view-link"
                  onclick="viewCompanyJobs('${escHtml(name)}')">View Jobs →</span>
          </div>
        </div>`;
    }).join('');

  } catch (e) {
    document.getElementById('companies-grid').innerHTML =
      `<div class="error-banner" style="grid-column:1/-1">⚠ ${escHtml(e.message)}</div>`;
  }
}

// ─── Navigate to Jobs filtered by company ───────
function viewCompanyJobs(name) {
  navigate('jobs');
  setTimeout(() => {
    const s = document.getElementById('job-search');
    if (s) { s.value = name; filterJobs(); }
  }, 300);
}

// ═══════════════════════════════════════════════
// ADD COMPANY MODAL
// ═══════════════════════════════════════════════
function openAddCompanyModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id        = 'add-company-modal';
  overlay.innerHTML = `
    <div class="modal-box">
      <div class="modal-header">
        <span class="modal-title">Add New Company</span>
        <button class="modal-close" onclick="document.getElementById('add-company-modal').remove()">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none"
               stroke="currentColor" stroke-width="2">
            <line x1="4" y1="4" x2="14" y2="14"/>
            <line x1="14" y1="4" x2="4" y2="14"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label">Company Name *</label>
          <input class="form-input" id="ac-name" placeholder="e.g. Acme Corp">
        </div>
        <div class="form-group">
          <label class="form-label">Industry</label>
          <input class="form-input" id="ac-industry" placeholder="e.g. Technology, Finance">
        </div>
        <div class="form-group">
          <label class="form-label">Website</label>
          <input class="form-input" id="ac-website" type="url" placeholder="https://example.com">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost"
          onclick="document.getElementById('add-company-modal').remove()">Cancel</button>
        <button class="btn btn-primary" id="ac-submit" onclick="submitAddCompany()">
          Add Company
        </button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

async function submitAddCompany() {
  const name     = document.getElementById('ac-name').value.trim();
  const industry = document.getElementById('ac-industry').value.trim();
  const website  = document.getElementById('ac-website').value.trim();

  if (!name) { toast('warning', 'Name required', 'Please enter a company name.'); return; }

  const btn    = document.getElementById('ac-submit');
  btn.innerHTML = `<span class="spinner"></span>`;
  btn.disabled  = true;

  try {
    await api('/companies', { method: 'POST', body: { name, industry, website } });
    document.getElementById('add-company-modal')?.remove();
    toast('success', 'Company added', `${name} has been registered.`);
    renderCompanies();
  } catch (e) {
    toast('error', 'Failed', e.message);
    btn.innerHTML = 'Add Company';
    btn.disabled  = false;
  }
}
