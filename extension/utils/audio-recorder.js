/**
 * AudioRecorder — handles microphone capture, PCM conversion, and waveform visualisation.
 * Output: WAV (PCM 16-bit LE, 16 kHz, mono)
 */
class AudioRecorder {
  constructor() {
    this.stream = null;
    this.audioCtx = null;
    this.source = null;
    this.processor = null;
    this.analyser = null;
    this.chunks = [];
    this.isRecording = false;
    this.onAudioChunk = null;   // callback(Float32Array) — for real-time streaming
  }

  /* ── Start microphone recording ── */
  async startMicrophone(canvas) {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    this.source = this.audioCtx.createMediaStreamSource(this.stream);

    // Analyser for waveform
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 2048;
    this.source.connect(this.analyser);

    // ScriptProcessor for raw PCM (deprecated but widest support)
    this.processor = this.audioCtx.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (e) => {
      if (!this.isRecording) return;
      const data = e.inputBuffer.getChannelData(0);
      const copy = new Float32Array(data.length);
      copy.set(data);
      this.chunks.push(copy);
      if (this.onAudioChunk) this.onAudioChunk(copy);
    };

    this.source.connect(this.processor);
    this.processor.connect(this.audioCtx.destination); // required for onaudioprocess

    this.isRecording = true;
    this.chunks = [];

    if (canvas) this._visualize(canvas);
  }

  /* ── Stop recording ── */
  stop() {
    this.isRecording = false;
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
    this.analyser = null;
  }

  /* ── Get combined WAV Blob ── */
  getRecordedBlob() {
    if (this.chunks.length === 0) return null;
    const totalLength = this.chunks.reduce((s, c) => s + c.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of this.chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    return AudioRecorder.createWavBlob(merged, 16000);
  }

  /* ── Float32 → Int16 PCM ── */
  static float32ToInt16(float32) {
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16;
  }

  /* ── Create WAV Blob from Float32 ── */
  static createWavBlob(float32Array, sampleRate) {
    const pcm = AudioRecorder.float32ToInt16(float32Array);
    const buffer = new ArrayBuffer(44 + pcm.length * 2);
    const view = new DataView(buffer);

    // RIFF header
    AudioRecorder._writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + pcm.length * 2, true);
    AudioRecorder._writeString(view, 8, 'WAVE');

    // fmt sub-chunk
    AudioRecorder._writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);           // sub-chunk size
    view.setUint16(20, 1, true);            // PCM
    view.setUint16(22, 1, true);            // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true);            // block align
    view.setUint16(34, 16, true);           // bits per sample

    // data sub-chunk
    AudioRecorder._writeString(view, 36, 'data');
    view.setUint32(40, pcm.length * 2, true);

    const output = new Int16Array(buffer, 44);
    output.set(pcm);

    return new Blob([buffer], { type: 'audio/wav' });
  }

  static _writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  /* ── Waveform visualisation ── */
  _visualize(canvas) {
    const ctx = canvas.getContext('2d');
    const analyser = this.analyser;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      if (!this.isRecording) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
      }
      requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(dataArray);

      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;

      ctx.fillStyle = '#0f0e17';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.lineWidth = 2;
      ctx.strokeStyle = '#e94560';
      ctx.beginPath();

      const sliceWidth = canvas.width / bufferLength;
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    };
    draw();
  }
}

if (typeof window !== 'undefined') window.AudioRecorder = AudioRecorder;
