/**
 * TranscriptStreamer — SSE client for real-time transcript updates.
 * Connects to /api/stream?job_id=... and emits events.
 */
class TranscriptStreamer {
  constructor(jobId, options = {}) {
    this.jobId = jobId;
    this.url = `http://127.0.0.1:8000/api/stream?job_id=${jobId}`;
    this.eventSource = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
    this.onPartial = options.onPartial || null;   // (text)
    this.onComplete = options.onComplete || null;  // (finalText)
    this.onError = options.onError || null;        // (error)
    this.onStatus = options.onStatus || null;      // (status)
  }

  /* ── Connect ── */
  connect() {
    if (this.eventSource) this.disconnect();

    this.eventSource = new EventSource(this.url);

    this.eventSource.addEventListener('partial', (e) => {
      this.reconnectAttempts = 0;
      try {
        const data = JSON.parse(e.data);
        if (this.onPartial) this.onPartial(data.text || e.data);
      } catch {
        if (this.onPartial) this.onPartial(e.data);
      }
    });

    this.eventSource.addEventListener('complete', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (this.onComplete) this.onComplete(data.text || e.data);
      } catch {
        if (this.onComplete) this.onComplete(e.data);
      }
      this.disconnect();
    });

    this.eventSource.addEventListener('error_event', (e) => {
      if (this.onError) this.onError(e.data);
      this.disconnect();
    });

    this.eventSource.addEventListener('status', (e) => {
      if (this.onStatus) this.onStatus(e.data);
    });

    this.eventSource.addEventListener('sarvam_job_submitted', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (this.onStatus) this.onStatus(data.message || 'Finalizing transcript...');
      } catch {
        if (this.onStatus) this.onStatus('Finalizing transcript...');
      }
    });

    this.eventSource.onerror = () => {
      this.eventSource.close();
      this.eventSource = null;
      this._reconnect();
    };

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
    };
  }

  /* ── Reconnect with exponential backoff ── */
  _reconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      if (this.onError) this.onError('Max reconnection attempts reached');
      return;
    }
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    setTimeout(() => this.connect(), delay);
  }

  /* ── Disconnect ── */
  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.reconnectAttempts = 0;
  }
}

if (typeof window !== 'undefined') window.TranscriptStreamer = TranscriptStreamer;
