const API_BASE = 'http://localhost:8000';

console.debug('service-worker loaded, API_BASE=', API_BASE);

// State management
let recordingState = {
  isRecording: false,
  jobId: null,
  mode: null,     // 'mic', 'tab', 'file'
  transMode: null, // 'realtime', 'batch'
};

// Keep-alive mechanism
let keepAliveInterval = null;

function startKeepAlive() {
  if (keepAliveInterval) return;
  keepAliveInterval = setInterval(() => {
    if (recordingState.isRecording) {
      chrome.storage.local.set({ lastPing: Date.now() });
    }
  }, 25000);
}

function stopKeepAlive() {
  if (keepAliveInterval) {
    clearInterval(keepAliveInterval);
    keepAliveInterval = null;
  }
}

// Persist state for recovery
async function saveState() {
  await chrome.storage.local.set({ recordingState });
}

async function loadState() {
  const result = await chrome.storage.local.get('recordingState');
  if (result.recordingState) {
    recordingState = result.recordingState;
  }
}

// Initialize on startup
loadState();

// Offscreen document management
async function ensureOffscreenDocument() {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT'],
  });
  if (contexts.length === 0) {
    await chrome.offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['USER_MEDIA'],
      justification: 'Capture tab audio for transcription',
    });
  }
}

// Message handling
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender, sendResponse);
  return true; // Keep channel open for async response
});

async function handleMessage(message, sender, sendResponse) {
  try {
    switch (message.type) {
      case 'START_TAB_CAPTURE': {
        const tab = message.tab;
        const streamId = await chrome.tabCapture.getMediaStreamId({
          targetTabId: tab.id,
        });
        await ensureOffscreenDocument();
        chrome.runtime.sendMessage({
          type: 'OFFSCREEN_START_CAPTURE',
          streamId,
          jobId: message.jobId,
          language: message.language,
        });
        recordingState = {
          isRecording: true,
          jobId: message.jobId,
          mode: 'tab',
          transMode: message.transMode || 'batch',
        };
        startKeepAlive();
        await saveState();
        sendResponse({ success: true, streamId });
        break;
      }

      case 'STOP_TAB_CAPTURE': {
        chrome.runtime.sendMessage({ type: 'OFFSCREEN_STOP_CAPTURE' });
        recordingState.isRecording = false;
        stopKeepAlive();
        await saveState();
        sendResponse({ success: true });
        break;
      }

      case 'TAB_AUDIO_CHUNK': {
        // Forward chunk to extension page or backend
        if (recordingState.transMode === 'realtime') {
          await sendAudioChunkToBackend(
            recordingState.jobId,
            message.audioData
          );
        }
        // Also forward to extension page
        chrome.runtime.sendMessage({
          type: 'AUDIO_CHUNK_RECEIVED',
          audioData: message.audioData,
          jobId: recordingState.jobId,
        });
        sendResponse({ success: true });
        break;
      }

      case 'GET_STATE': {
        sendResponse({ ...recordingState });
        break;
      }

      case 'CREATE_JOB': {
        const job = await createJob(message.language, message.mode);
        sendResponse(job);
        break;
      }

      case 'UPLOAD_CHUNK': {
        const result = await uploadChunk(
          message.jobId,
          message.chunkIndex,
          message.chunkData
        );
        sendResponse(result);
        break;
      }

      default:
        sendResponse({ error: 'Unknown message type' });
    }
  } catch (error) {
    console.error('Service worker message error:', error);
    sendResponse({ error: error.message });
  }
}

// API helpers
async function createJob(language, mode) {
  const url = `${API_BASE}/api/jobs`;
  console.debug('createJob calling', url, { language, mode });
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language, mode }),
    });
    console.debug('createJob response', response.status);
    if (!response.ok) throw new Error(`Create job failed: ${response.status}`);
    return response.json();
  } catch (err) {
    console.error('createJob error for', url, err);
    throw err;
  }
}

async function sendAudioChunkToBackend(jobId, audioData) {
  const blob = new Blob([new Uint8Array(audioData)], { type: 'audio/wav' });
  const formData = new FormData();
  formData.append('file', blob, 'chunk.wav');
  const url = `${API_BASE}/api/jobs/${jobId}/stream/audio`;
  console.debug('sendAudioChunkToBackend posting to', url, 'size', blob.size);
  try {
    const response = await fetch(url, { method: 'POST', body: formData });
    console.debug('sendAudioChunkToBackend response', response.status);
    if (!response.ok) throw new Error(`Stream audio failed: ${response.status}`);
    return response.json();
  } catch (err) {
    console.error('sendAudioChunkToBackend error for', url, err);
    throw err;
  }
}

async function uploadChunk(jobId, chunkIndex, chunkData) {
  const blob = new Blob([new Uint8Array(chunkData)], {
    type: 'application/octet-stream',
  });
  const formData = new FormData();
  formData.append('file', blob, `chunk_${chunkIndex}`);

  const maxRetries = 3;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const url = `${API_BASE}/api/jobs/${jobId}/upload/chunks/${chunkIndex}`;
      console.debug('uploadChunk attempt', attempt + 1, 'posting to', url);
      const response = await fetch(url, { method: 'POST', body: formData });
      console.debug('uploadChunk response', response.status);
      if (response.ok) return response.json();
      if (response.status === 429) {
        await new Promise((r) => setTimeout(r, (attempt + 1) * 2000));
        continue;
      }
      throw new Error(`Upload chunk failed: ${response.status}`);
    } catch (e) {
      if (attempt === maxRetries - 1) throw e;
      await new Promise((r) =>
        setTimeout(r, Math.pow(2, attempt) * 1000)
      );
    }
  }
}
