/**
 * ChunkedUploader — splits a Blob into chunks and uploads them sequentially
 * with retry & resume support.
 */
class ChunkedUploader {
  constructor(jobId, blob, options = {}) {
    this.jobId = jobId;
    this.blob = blob;
    this.chunkSize = options.chunkSize || 5 * 1024 * 1024; // 5 MB
    this.maxRetries = options.maxRetries || 3;
    this.onProgress = options.onProgress || null;  // (pct, chunkIndex, totalChunks)
    this.onComplete = options.onComplete || null;
    this.onError = options.onError || null;
    this.aborted = false;
    this.totalChunks = Math.ceil(blob.size / this.chunkSize);
  }

  /* ── Main upload flow ── */
  async start() {
    try {
      // 1. Init upload on server
      await API.initUpload(this.jobId, this.totalChunks, this.blob.size);

      // 2. Check resume state
      let startIndex = 0;
      try {
        const status = await API.getUploadStatus(this.jobId);
        if (status && status.received_chunks) {
          startIndex = status.received_chunks.length;
        }
      } catch { /* first upload, start from 0 */ }

      // 3. Upload each chunk
      for (let i = startIndex; i < this.totalChunks; i++) {
        if (this.aborted) throw new Error('Upload aborted');

        const start = i * this.chunkSize;
        const end = Math.min(start + this.chunkSize, this.blob.size);
        const chunkBlob = this.blob.slice(start, end);
        const chunkData = await chunkBlob.arrayBuffer();

        await this._uploadWithRetry(i, chunkData);

        const pct = Math.round(((i + 1) / this.totalChunks) * 100);
        if (this.onProgress) this.onProgress(pct, i + 1, this.totalChunks);
      }

      // 4. Complete
      const result = await API.completeUpload(this.jobId);
      if (this.onComplete) this.onComplete(result);
      return result;
    } catch (err) {
      if (this.onError) this.onError(err);
      throw err;
    }
  }

  /* ── Upload single chunk with retry ── */
  async _uploadWithRetry(chunkIndex, chunkData) {
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        await API.uploadChunk(this.jobId, chunkIndex, chunkData);
        return;
      } catch (err) {
        if (attempt === this.maxRetries - 1) throw err;
        const wait = Math.pow(2, attempt) * 1000;
        await new Promise(r => setTimeout(r, wait));
      }
    }
  }

  /* ── Abort ── */
  abort() {
    this.aborted = true;
  }
}

if (typeof window !== 'undefined') window.ChunkedUploader = ChunkedUploader;
