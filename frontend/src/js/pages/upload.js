/* ═══════════════════════════════════════════════
   pages/upload.js — Upload Resume page
   ═══════════════════════════════════════════════ */

let uploadFile = null; // currently selected file

// ─── RENDER PAGE ────────────────────────────────
async function renderUploadResume() {
  uploadFile = null;
  const pc = document.getElementById('page-content');

  pc.innerHTML = `
    <div class="upload-layout">

      <!-- Drop zone -->
      <div class="dropzone" id="dropzone"
           onclick="document.getElementById('file-input').click()">
        <input type="file" id="file-input" accept=".pdf" style="display:none"
               onchange="onFileChosen(this.files[0])">
        <div id="dropzone-content">${dropzoneDefaultHTML()}</div>
      </div>

      <!-- Upload button (shown after file selected) -->
      <div id="upload-btn-wrap" style="display:none;text-align:center">
        <button class="btn btn-primary btn-lg" id="upload-btn"
                style="width:100%;max-width:320px" onclick="doUpload()">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="white">
            <path d="M8 1v10M4 4l4-4 4 4"/>
            <rect x="1" y="12" width="14" height="3" rx="1"
                  stroke="white" stroke-width="1.5" fill="none"/>
          </svg>
          Upload to Warehouse
        </button>
      </div>

      <!-- Upload result (shown after API response) -->
      <div id="upload-result"></div>

      <!-- Warehouse list (always visible) -->
      <div class="card warehouse-card">
        <div class="warehouse-card-header">
          <div style="display:flex;align-items:center;gap:8px">
            <span class="card-title">Warehouse Resumes</span>
            <span id="warehouse-count-badge" class="results-count-badge">—</span>
          </div>
          <button class="icon-btn" onclick="loadWarehouseList()" title="Refresh">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
                 stroke="currentColor" stroke-width="1.5">
              <path d="M14 8A6 6 0 112 8" stroke-linecap="round"/>
              <path d="M14 3v5h-5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
        <div id="warehouse-list">
          <div style="padding:20px;text-align:center">
            <div class="spinner spinner-dark"></div>
          </div>
        </div>
      </div>

    </div>`;

  // Drag-and-drop events
  const dz = document.getElementById('dropzone');
  dz.addEventListener('dragover',  e => { e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', ()  => dz.classList.remove('dragover'));
  dz.addEventListener('drop', e => {
    e.preventDefault();
    dz.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) onFileChosen(f);
  });

  loadWarehouseList();
}

// ─── Dropzone default HTML ───────────────────────
function dropzoneDefaultHTML() {
  return `
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <circle cx="32" cy="32" r="30" stroke="#EEF2FF" stroke-width="3"/>
      <path d="M32 22v18M24 28l8-8 8 8" stroke="#6366F1" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M20 42h24" stroke="#A5B4FC" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <h3>Drop your PDF resume here</h3>
    <p>or click to browse files</p>
    <small>Supports: PDF only • Max 10MB</small>`;
}

// ─── File chosen ─────────────────────────────────
function onFileChosen(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    toast('warning', 'PDF only', 'Please select a PDF file.');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    toast('warning', 'Too large', 'File must be under 10MB.');
    return;
  }

  uploadFile = file;
  const sizeMb = (file.size / 1024 / 1024).toFixed(2);

  document.getElementById('dropzone-content').innerHTML = `
    <div class="file-preview">
      <div class="pdf-icon">PDF</div>
      <div class="file-preview-info">
        <div class="file-preview-name">${escHtml(file.name)}</div>
        <div class="file-preview-size">${sizeMb} MB</div>
      </div>
      <div class="file-remove" onclick="clearFile(event)">✕</div>
    </div>`;

  document.getElementById('upload-btn-wrap').style.display = 'block';
}

// ─── Clear selected file ─────────────────────────
function clearFile(e) {
  if (e) e.stopPropagation();
  uploadFile = null;
  document.getElementById('dropzone-content').innerHTML = dropzoneDefaultHTML();
  document.getElementById('upload-btn-wrap').style.display = 'none';
  document.getElementById('file-input').value = '';
}

// ─── Upload file ─────────────────────────────────
async function doUpload() {
  if (!uploadFile) return;

  const btn = document.getElementById('upload-btn');
  btn.innerHTML = `<span class="spinner"></span> Uploading...`;
  btn.disabled  = true;

  const fd = new FormData();
  fd.append('resume', uploadFile);

  const filename = uploadFile.name; // save before clearFile resets it

  try {
    const data  = await api('/upload_resume', { method: 'POST', body: fd });
    const isNew = data.is_new !== false;

    document.getElementById('upload-result').innerHTML = buildUploadResultHTML(isNew, data, filename);
    clearFile();
    loadWarehouseList();
    checkApiStatus();
    toast(isNew ? 'success' : 'info',
          isNew ? 'Upload successful!' : 'Already in warehouse',
          isNew ? `${filename} has been indexed.` : 'No duplicate stored.');
  } catch (e) {
    document.getElementById('upload-result').innerHTML = `
      <div class="upload-result-card error">
        <div class="upload-result-icon error">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="white">
            <path d="M4 4l10 10M14 4L4 14" stroke="white" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="upload-result-body">
          <div class="upload-result-title">Upload Failed</div>
          <div class="upload-result-msg">${escHtml(e.message)}</div>
          <div class="upload-detail-pills" style="margin-top:12px">
            <button class="btn btn-ghost btn-sm"
              onclick="document.getElementById('upload-result').innerHTML=''">Try Again</button>
          </div>
        </div>
      </div>`;
    toast('error', 'Upload failed', e.message);
  } finally {
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="white">
      <path d="M8 1v10M4 4l4-4 4 4"/>
      <rect x="1" y="12" width="14" height="3" rx="1" stroke="white" stroke-width="1.5" fill="none"/>
    </svg> Upload to Warehouse`;
    btn.disabled = false;
  }
}

// ─── Build upload result card HTML ───────────────
function buildUploadResultHTML(isNew, data, fname) {
  const icon = isNew
    ? `<svg width="18" height="18" viewBox="0 0 18 18" fill="white">
         <path d="M3 9l4 4 8-8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
       </svg>`
    : `<svg width="18" height="18" viewBox="0 0 18 18" fill="white">
         <circle cx="9" cy="5" r="1" fill="white"/>
         <line x1="9" y1="8" x2="9" y2="14" stroke="white" stroke-width="2" stroke-linecap="round"/>
       </svg>`;

  const title = isNew ? 'Successfully uploaded!' : 'Already in Warehouse';
  const msg   = isNew
    ? `${escHtml(fname)} has been stored and indexed in the warehouse.`
    : 'This resume was already uploaded. No duplicate stored.';

  const pills = isNew
    ? `<span class="upload-detail-pill">Resume ID: #${data.resume_id || data.id || '?'}</span>
       <span class="upload-detail-pill" style="color:var(--success)">✓ Ready for matching</span>`
    : '';

  return `
    <div class="upload-result-card ${isNew ? 'success' : ''}">
      <div class="upload-result-icon ${isNew ? 'success' : 'info'}">${icon}</div>
      <div class="upload-result-body">
        <div class="upload-result-title">${title}</div>
        <div class="upload-result-msg">${msg}</div>
        <div class="upload-detail-pills">
          ${pills}
          <button class="btn btn-ghost btn-sm"
            onclick="document.getElementById('upload-result').innerHTML='';clearFile()">
            Upload Another
          </button>
        </div>
      </div>
    </div>`;
}

// ─── Load warehouse resume list ──────────────────
async function loadWarehouseList() {
  const el = document.getElementById('warehouse-list');
  if (!el) return;

  el.innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner spinner-dark"></div></div>';

  try {
    const resumes = await api('/resumes');
    state.resumes = resumes || [];

    const badge = document.getElementById('warehouse-count-badge');
    if (badge) badge.textContent = (resumes || []).length;

    if (!resumes || !resumes.length) {
      el.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 48 48">
            <rect x="8" y="8" width="32" height="36" rx="3" fill="#EEF2FF"/>
            <rect x="14" y="16" width="20" height="3" rx="1" fill="#A5B4FC"/>
            <rect x="14" y="22" width="14" height="3" rx="1" fill="#C7D2FE"/>
          </svg>
          <h3>No resumes uploaded yet</h3>
        </div>`;
      return;
    }

    el.innerHTML = `
      <div style="overflow-x:auto">
        <table class="data-table">
          <thead>
            <tr><th>#</th><th>Filename</th><th>Uploaded At</th><th>Actions</th></tr>
          </thead>
          <tbody>
            ${resumes.map((r, i) => `
              <tr>
                <td style="color:var(--text-muted)">${i + 1}</td>
                <td><strong>${escHtml(r.filename || r.file_name || '')}</strong></td>
                <td style="color:var(--text-secondary);font-size:12px">
                  ${fmtDate(r.uploaded_at || r.created_at)}
                </td>
                <td>
                  <button class="btn btn-ghost btn-sm"
                    onclick="matchResume('${escHtml(r.filename || r.file_name || '')}')">
                    Match ▶
                  </button>
                </td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="error-banner">⚠ ${escHtml(e.message)}</div>`;
  }
}

// ─── Quick-navigate to Match page ───────────────
function matchResume(filename) {
  navigate('match');
  setTimeout(() => {
    const ta = document.getElementById('match-jd');
    if (ta) ta.value = `Looking for resume: ${filename}`;
  }, 300);
}
