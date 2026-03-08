/* ═══════════════════════════════════════════════
   app.js — Navigation, toasts, sidebar, init
   ═══════════════════════════════════════════════ */

const PAGE_META = {
  dashboard: { title: 'Dashboard',      subtitle: 'Overview of your resume matching system' },
  match:     { title: 'Match Resume',   subtitle: 'Find best-matching resumes for a job description' },
  upload:    { title: 'Upload Resume',  subtitle: 'Add PDF resumes to the matching warehouse' },
  jobs:      { title: 'Browse Jobs',    subtitle: 'Explore and manage job postings' },
  companies: { title: 'Companies',      subtitle: 'Manage registered companies' },
  history:   { title: 'Match History',  subtitle: 'View all past resume matching runs' }
};

function navigate(page) {
  state.currentPage = page;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });
  const meta = PAGE_META[page];
  document.getElementById('page-title').textContent    = meta.title;
  document.getElementById('page-subtitle').textContent = meta.subtitle;
  const renders = {
    dashboard: renderDashboard,
    match:     renderMatchResume,
    upload:    renderUploadResume,
    jobs:      renderBrowseJobs,
    companies: renderCompanies,
    history:   renderMatchHistory
  };
  renders[page]?.();
  const sb = document.getElementById('sidebar');
  if (sb.classList.contains('open')) toggleSidebar();
}

document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', function(e) {
    const ripple = document.createElement('span');
    ripple.classList.add('ripple');
    const rect = this.getBoundingClientRect();
    ripple.style.left = (e.clientX - rect.left - 10) + 'px';
    ripple.style.top  = (e.clientY - rect.top  - 10) + 'px';
    this.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
    navigate(this.dataset.page);
  });
});

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-backdrop').classList.toggle('open');
}

const TOAST_ICONS = {
  success: `<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" stroke="#10B981" stroke-width="1.5"/><path d="M6 10l3 3 5-5" stroke="#10B981" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  error:   `<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" stroke="#EF4444" stroke-width="1.5"/><path d="M7 7l6 6M13 7l-6 6" stroke="#EF4444" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  info:    `<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" stroke="#4F46E5" stroke-width="1.5"/><line x1="10" y1="9" x2="10" y2="14" stroke="#4F46E5" stroke-width="1.5" stroke-linecap="round"/><circle cx="10" cy="6.5" r="0.75" fill="#4F46E5"/></svg>`,
  warning: `<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2l8 15H2L10 2z" stroke="#F59E0B" stroke-width="1.5" stroke-linejoin="round"/><line x1="10" y1="9" x2="10" y2="13" stroke="#F59E0B" stroke-width="1.5" stroke-linecap="round"/><circle cx="10" cy="15.5" r="0.75" fill="#F59E0B"/></svg>`
};

function toast(type, title, message) {
  const container = document.getElementById('toast-container');
  const div = document.createElement('div');
  div.className = `toast ${type}`;
  div.innerHTML = `
    <div class="toast-icon">${TOAST_ICONS[type]}</div>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      ${message ? `<div class="toast-msg">${message}</div>` : ''}
    </div>
    <span class="toast-close" onclick="this.parentElement.remove()">×</span>
  `;
  container.appendChild(div);
  setTimeout(() => {
    div.style.animation = 'toastOut 0.3s ease forwards';
    setTimeout(() => div.remove(), 300);
  }, 4000);
}

(async function init() {
  await checkApiStatus();
  setInterval(checkApiStatus, 30000);
  navigate('dashboard');
})();