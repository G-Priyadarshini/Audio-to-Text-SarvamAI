/**
 * API utility — wraps all backend HTTP calls with fallback hosts.
 */
const API_BASES = [
  'http://127.0.0.1:8000/api',
  'http://localhost:8000/api',
  'http://127.0.0.1:5000/api',
  'http://localhost:5000/api',
];

console.debug('API_BASES:', API_BASES);

const HEALTH_BASES = [
  'http://127.0.0.1:8000',
  'http://localhost:8000',
  'http://127.0.0.1:5000',
  'http://localhost:5000',
];

async function fetchWithFallback(bases, path, options = {}) {
  let lastErr = null;
  for (const base of bases) {
    const url = `${base}${path}`;
    console.debug('fetchWithFallback trying', url);
    try {
      const headers = { ...(options.headers || {}) };
      if (!(options.body instanceof FormData)) headers['Content-Type'] = headers['Content-Type'] || 'application/json';
      const res = await fetch(url, {
        headers,
        ...options,
      });
      console.debug('fetchWithFallback response', url, res.status);
      return res;
    } catch (err) {
      lastErr = err;
      console.warn(`Fetch failed for ${url}:`, err);
    }
  }
  throw lastErr || new Error('All backend endpoints failed');
}

class API {
  /* ── Generic request with retry ── */
  static async request(path, options = {}, retries = 2) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const res = await fetchWithFallback(API_BASES, path, options);
        if (res.status === 429) {
          const wait = Math.pow(2, attempt) * 1000;
          await new Promise(r => setTimeout(r, wait));
          continue;
        }
        if (!res.ok) {
          const body = await res.text();
          throw new Error(`HTTP ${res.status}: ${body}`);
        }
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')) return res.json();
        return res;
      } catch (err) {
        if (attempt === retries) throw err;
        await new Promise(r => setTimeout(r, 1000));
      }
    }
  }

  /* ── Health ── */
  static async checkHealth() {
    try {
      const res = await fetchWithFallback(HEALTH_BASES, '/health', { signal: AbortSignal.timeout(3000) });
      return res && res.ok;
    } catch (err) {
      console.warn('Health check failed:', err);
      return false;
    }
  }

  /* ── Jobs ── */
  static createJob(data) {
    return API.request('/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static getJob(jobId) {
    return API.request(`/jobs/${jobId}`);
  }

  static getJobStatus(jobId) {
    return API.request(`/jobs/${jobId}/status`);
  }

  static listJobs(skip = 0, limit = 20) {
    return API.request(`/jobs?skip=${skip}&limit=${limit}`);
  }

  static deleteJob(jobId) {
    return API.request(`/jobs/${jobId}`, { method: 'DELETE' });
  }

  /* ── Uploads ── */
  static initUpload(jobId, totalChunks, totalSize) {
    return API.request(`/jobs/${jobId}/upload/init`, {
      method: 'POST',
      body: JSON.stringify({ total_chunks: totalChunks, file_size: totalSize }),
    });
  }

  static async uploadChunk(jobId, chunkIndex, chunkData) {
    const formData = new FormData();
    formData.append('file', new Blob([chunkData]), `chunk_${chunkIndex}.wav`);
    return API.request(`/jobs/${jobId}/upload/chunks/${chunkIndex}`, {
      method: 'POST',
      headers: {},          // let browser set multipart boundary
      body: formData,
    });
  }

  static getUploadStatus(jobId) {
    return API.request(`/jobs/${jobId}/upload/status`);
  }

  static completeUpload(jobId) {
    return API.request(`/jobs/${jobId}/upload/complete`, { method: 'POST' });
  }

  /* ── Transcripts ── */
  static getTranscript(jobId) {
    return API.request(`/jobs/${jobId}/transcript`);
  }

  static updateTranscript(jobId, fullText) {
    return API.request(`/jobs/${jobId}/transcript`, {
      method: 'PUT',
      body: JSON.stringify({ full_text: fullText }),
    });
  }

  static async downloadTranscript(jobId, format = 'txt') {
    const res = await API.request(`/jobs/${jobId}/transcript/download?format=${format}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript_${jobId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /* ── Settings ── */
  static updateSettings(data) {
    return API.request('/settings', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static getSettings() {
    return API.request('/settings');
  }

  /* ── Stream (real-time) ── */
  static sendStreamAudio(jobId, audioData) {
    const formData = new FormData();
    formData.append('file', new Blob([audioData], { type: 'audio/wav' }), 'chunk.wav');
    return API.request(`/jobs/${jobId}/stream/audio`, {
      method: 'POST',
      headers: {},
      body: formData,
    });
  }

  static endStream(jobId) {
    return API.request(`/jobs/${jobId}/stream/end`, { method: 'POST' });
  }

  /* ── Convenience: upload single file (init) ── */
  static async uploadFile(file) {
    console.debug('API.uploadFile called:', file && file.name);
    const form = new FormData();
    form.append('file', file);
    // Create job, init single-chunk upload, upload chunk, complete
    const job = await API.createJob({});
    const jobId = job.id;
    const fileSize = file.size || 0;
    await API.initUpload(jobId, 1, fileSize);
    const chunkForm = new FormData();
    chunkForm.append('file', file);
    await fetchWithFallback(API_BASES, `/jobs/${jobId}/upload/chunks/0`, { method: 'POST', body: chunkForm });
    await API.completeUpload(jobId);
    return { job_id: jobId };
  }
}

// Export for module / script usage
if (typeof window !== 'undefined') window.API = API;
