/**
 * extension-page.js — Main application logic for the Audio to Text extension page.
 * Orchestrates UI, uploading, and history.
 */

/* ====================================================================
   State
   ==================================================================== */
const state = {
  currentSource: 'file',
  mode: 'batch',
  currentJobId: null,
  isEditing: false,
  uploader: null,
  backendOnline: false,
  selectedFile: null,
};

/* ====================================================================
   DOM References
   ==================================================================== */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  // Header
  languageSelect: $('#languageSelect'),
  statusDot: $('#statusDot'),
  statusText: $('#statusText'),

  // File
  uploadZone: $('#uploadZone'),
  fileInput: $('#fileInput'),
  fileInfo: $('#fileInfo'),
  fileName: $('#fileName'),
  fileSize: $('#fileSize'),
  fileDuration: $('#fileDuration'),
  progressFill: $('#progressFill'),
  progressText: $('#progressText'),
  uploadStartBtn: $('#uploadStartBtn'),

  // Job
  jobStatus: $('#jobStatus'),
  statusBadge: $('#statusBadge'),

  // Transcript
  editBtn: $('#editToggle'),
  saveBtn: $('#saveEdit'),
  cancelBtn: $('#cancelEdit'),
  emptyState: $('#emptyState'),
  liveTranscript: $('#liveTranscript'),
  editArea: $('#editArea'),
  downloadTxt: $('#downloadTxt'),

  // History
  historyToggle: $('#historyToggle'),
  historySidebar: $('#historySidebar'),
  closeHistory: $('#closeHistory'),
  historyList: $('#historyList'),
};

/* ====================================================================
   Initialise
   ==================================================================== */
document.addEventListener('DOMContentLoaded', init);

async function init() {
  checkHealth();
  setInterval(checkHealth, 15000);
  try { bindEvents(); } catch (e) { console.error('bindEvents error:', e); }
}

/* ====================================================================
   Health Check
   ==================================================================== */
async function checkHealth() {
  const ok = await API.checkHealth();
  state.backendOnline = ok;
  dom.statusDot.className = `status-dot ${ok ? 'connected' : 'disconnected'}`;
  dom.statusText.textContent = ok ? 'Online' : 'Offline';
}

/* ====================================================================
   Event Binding
   ==================================================================== */
function bindEvents() {
  // File upload — click to browse
  dom.uploadZone?.addEventListener('click', () => dom.fileInput?.click());
  dom.uploadZone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.uploadZone.classList.add('drag-over');
  });
  dom.uploadZone?.addEventListener('dragleave', () => {
    dom.uploadZone.classList.remove('drag-over');
  });
  dom.uploadZone?.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.uploadZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
  });
  dom.fileInput?.addEventListener('change', (e) => {
    if (e.target.files.length) handleFileSelect(e.target.files[0]);
  });

  // File upload start button
  dom.uploadStartBtn?.addEventListener('click', async () => {
    if (!state.selectedFile) return alert('No file selected');
    if (!state.backendOnline) return alert('Backend is offline');
    try {
      const lang = dom.languageSelect.value;
      const job = await API.createJob({
        language: lang === 'auto' ? null : lang,
        mode: 'batch',
      });
      state.currentJobId = job.id;
      updateJobStatus(job.status);
      showLiveTranscript();
      await uploadBlob(state.selectedFile);
    } catch (err) {
      console.error('File upload error:', err);
      alert('Upload failed: ' + (err && err.message));
      resetFilePanel();
    }
  });

  // Transcript editing
  dom.editBtn?.addEventListener('click', startEdit);
  dom.saveBtn?.addEventListener('click', saveEdit);
  dom.cancelBtn?.addEventListener('click', cancelEdit);

  // Downloads
  dom.downloadTxt?.addEventListener('click', () => downloadTranscript('txt'));

  // History
  dom.historyToggle?.addEventListener('click', toggleHistory);
  dom.closeHistory?.addEventListener('click', toggleHistory);
}

/* ====================================================================
   File Upload
   ==================================================================== */
async function handleFileSelect(file) {
  const maxSize = 500 * 1024 * 1024;
  const allowed = ['audio/wav', 'audio/x-wav', 'audio/wave', 'audio/mpeg', 'audio/mp3',
    'audio/ogg', 'audio/flac', 'audio/webm', 'audio/mp4', 'audio/x-m4a'];

  if (!allowed.some(t => file.type.startsWith(t.split('/')[0])) && !file.name.match(/\.(wav|mp3|ogg|flac|webm|m4a)$/i)) {
    return alert('Unsupported file format. Use WAV, MP3, OGG, FLAC, WebM, or M4A.');
  }
  if (file.size > maxSize) {
    return alert('File too large. Maximum is 500 MB.');
  }

  dom.uploadZone.classList.add('hidden');
  dom.fileInfo.classList.remove('hidden');
  dom.fileName.textContent = file.name;
  dom.fileSize.textContent = formatBytes(file.size);
  dom.fileDuration.textContent = '—';
  // Store selected file and enable manual Start button
  state.selectedFile = file;
  dom.uploadStartBtn?.removeAttribute('disabled');
  dom.progressFill.style.width = '0%';
  dom.progressText.textContent = '0%';
}

function resetFilePanel() {
  dom.uploadZone.classList.remove('hidden');
  dom.fileInfo.classList.add('hidden');
  dom.progressFill.style.width = '0%';
  dom.progressText.textContent = '0%';
  state.selectedFile = null;
  dom.uploadStartBtn?.setAttribute('disabled', 'true');
}

/* ====================================================================
   Upload Blob
   ==================================================================== */
async function uploadBlob(blob) {
  const uploader = new ChunkedUploader(state.currentJobId, blob, {
    onProgress: (pct) => {
      dom.progressFill.style.width = pct + '%';
      dom.progressText.textContent = pct + '%';
    },
    onComplete: () => {
      updateJobStatus('queued');
      pollJobStatus(state.currentJobId);
    },
    onError: (err) => {
      console.error('Upload error:', err);
      alert('Upload failed: ' + err.message);
    },
  });
  state.uploader = uploader;
  await uploader.start();
}

/* ====================================================================
   Job Status Polling
   ==================================================================== */
function pollJobStatus(jobId) {
  let attempts = 0;
  const maxAttempts = 20; // after ~60s show queued hint, but keep polling
  const interval = setInterval(async () => {
    attempts++;
    try {
      const data = await API.getJobStatus(jobId);
      updateJobStatus(data.status);

      // Show progress messages for Sarvam job states
      const statusMessage = getStatusMessage(data.status);
      if (statusMessage && !isTerminalStatus(data.status)) {
        dom.liveTranscript.textContent = statusMessage;
      }

      if (data.status === 'completed') {
        clearInterval(interval);
        loadTranscript(jobId);
      } else if (data.status === 'failed') {
        clearInterval(interval);
        dom.liveTranscript.textContent = data.error_message || 'Transcription failed. Please try again.';
      } else {
        // If still queued after some attempts, show helpful hint
        if (attempts === maxAttempts && data.status === 'queued') {
          dom.liveTranscript.textContent = 'Transcription queued — worker not running or busy. Start the background worker to process jobs.';
        }
      }
    } catch (err) {
      // keep polling, but stop if repeated errors
      if (attempts > 5) {
        clearInterval(interval);
        console.error('Polling failed repeatedly:', err);
      }
    }
  }, 3000);
}

function getStatusMessage(status) {
  switch (status) {
    case 'queued':                return 'Waiting in queue...';
    case 'processing':            return 'Processing...';
    case 'uploading_to_sarvam':   return 'Uploading to Sarvam AI...';
    case 'sarvam_processing':     return 'Sarvam AI is transcribing...';
    case 'downloading_result':    return 'Downloading transcript...';
    case 'completed':             return 'Transcription complete!';
    case 'failed':                return 'Transcription failed.';
    default:                      return '';
  }
}

function isTerminalStatus(status) {
  return status === 'completed' || status === 'failed';
}

function updateJobStatus(status) {
  if (!status) return;
  dom.jobStatus.classList.remove('hidden');
  dom.statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
  dom.statusBadge.className = `status-badge ${status}`;
}

/* ====================================================================
   Transcript Display
   ==================================================================== */
function showLiveTranscript() {
  dom.emptyState.classList.add('hidden');
  dom.liveTranscript.classList.remove('hidden');
  dom.liveTranscript.textContent = '';
}

function showFinalTranscript(text) {
  dom.liveTranscript.textContent = text;
  enableDownloads();
}

async function loadTranscript(jobId) {
  try {
    const data = await API.getTranscript(jobId);
    dom.emptyState.classList.add('hidden');
    dom.liveTranscript.classList.remove('hidden');

    const text = data.full_text || '';

    // If the response looks like HTML (ICEPOT report), render as HTML
    if (text.trimStart().startsWith('<')) {
      dom.liveTranscript.classList.add('html-content');
      dom.liveTranscript.innerHTML = text;
    } else if (data.diarized_json) {
      dom.liveTranscript.classList.remove('html-content');
      const segments = typeof data.diarized_json === 'string'
        ? JSON.parse(data.diarized_json) : data.diarized_json;
      dom.liveTranscript.innerHTML = '';
      segments.forEach(seg => {
        const label = document.createElement('span');
        label.className = 'speaker-label';
        label.textContent = `[${seg.speaker || 'Speaker'}] `;
        dom.liveTranscript.appendChild(label);
        dom.liveTranscript.appendChild(document.createTextNode(seg.text + '\n'));
      });
    } else {
      dom.liveTranscript.classList.remove('html-content');
      dom.liveTranscript.textContent = text;
    }
    enableDownloads();
  } catch (err) {
    console.error('Load transcript error:', err);
  }
}

/* ====================================================================
   Editing
   ==================================================================== */
function startEdit() {
  state.isEditing = true;
  dom.editArea.value = dom.liveTranscript.textContent;
  dom.liveTranscript.classList.add('hidden');
  dom.editArea.classList.remove('hidden');
  dom.editBtn.hidden = true;
  dom.saveBtn.hidden = false;
  dom.cancelBtn.hidden = false;
}

async function saveEdit() {
  if (!state.currentJobId) return;
  try {
    await API.updateTranscript(state.currentJobId, dom.editArea.value);
    dom.liveTranscript.textContent = dom.editArea.value;
  } catch (err) {
    alert('Save failed: ' + err.message);
    return;
  }
  finishEdit();
}

function cancelEdit() {
  finishEdit();
}

function finishEdit() {
  state.isEditing = false;
  dom.liveTranscript.classList.remove('hidden');
  dom.editArea.classList.add('hidden');
  dom.editBtn.hidden = false;
  dom.saveBtn.hidden = true;
  dom.cancelBtn.hidden = true;
}

/* ====================================================================
   Downloads
   ==================================================================== */
function enableDownloads() {
  dom.downloadTxt.disabled = false;
  dom.downloadSrt.disabled = false;
  dom.downloadVtt.disabled = false;
  dom.editBtn.disabled = false;
}

async function downloadTranscript(format) {
  if (!state.currentJobId) return;
  try {
    await API.downloadTranscript(state.currentJobId, format);
  } catch (err) {
    alert('Download failed: ' + err.message);
  }
}

/* ====================================================================
   History Sidebar
   ==================================================================== */
function toggleHistory() {
  dom.historySidebar.classList.toggle('hidden');
  if (!dom.historySidebar.classList.contains('hidden')) loadHistory();
}

async function loadHistory() {
  dom.historyList.innerHTML = '<p class="loading">Loading...</p>';
  try {
    const data = await API.listJobs(0, 50);
    const jobs = data.jobs || [];
    if (jobs.length === 0) {
      dom.historyList.innerHTML = '<p class="loading">No transcription history yet.</p>';
      return;
    }
    dom.historyList.innerHTML = '';
    jobs.forEach(job => {
      const el = document.createElement('div');
      el.className = 'history-item';
      el.innerHTML = `
        <div class="history-item-header">
          <span class="history-date">${formatDate(job.created_at)}</span>
          <span class="history-badge ${job.status}">${job.status}</span>
        </div>
        <div class="history-meta">
          <span>${job.language || 'auto'}</span>
          <span>${job.mode}</span>
          ${job.duration_seconds ? `<span>${Math.round(job.duration_seconds)}s</span>` : ''}
        </div>
        <button class="history-delete" data-id="${job.id}" title="Delete">&times;</button>
      `;
      el.addEventListener('click', (e) => {
        if (e.target.classList.contains('history-delete')) return;
        loadJobFromHistory(job.id);
      });
      el.querySelector('.history-delete').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm('Delete this job?')) {
          await API.deleteJob(job.id);
          loadHistory();
        }
      });
      dom.historyList.appendChild(el);
    });
  } catch (err) {
    dom.historyList.innerHTML = '<p class="loading">Failed to load history.</p>';
  }
}

async function loadJobFromHistory(jobId) {
  state.currentJobId = jobId;
  try {
    const job = await API.getJob(jobId);
    updateJobStatus(job.status);
    if (job.status === 'completed') {
      await loadTranscript(jobId);
    }
  } catch (err) {
    console.error('Load history job error:', err);
  }
  dom.historySidebar.classList.add('hidden');
}

/* ====================================================================
   Helpers
   ==================================================================== */
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
