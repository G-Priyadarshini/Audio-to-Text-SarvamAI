let mediaStream = null;
let mediaRecorder = null;
let audioContext = null;
let processor = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'OFFSCREEN_START_CAPTURE':
      startCapture(message.streamId);
      break;
    case 'OFFSCREEN_STOP_CAPTURE':
      stopCapture();
      break;
  }
});

async function startCapture(streamId) {
  try {
    // Get the tab's audio stream
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId,
        },
      },
    });

    // Create AudioContext to process audio and preserve playback
    audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(mediaStream);

    // Use a ScriptProcessorNode to capture PCM data
    processor = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0);
      // Convert Float32 to Int16 PCM
      const pcmData = float32ToInt16(inputData);

      // Send chunk to service worker
      chrome.runtime.sendMessage({
        type: 'TAB_AUDIO_CHUNK',
        audioData: Array.from(pcmData),
      });
    };

    source.connect(processor);
    // Connect to destination to keep tab audio playing for the user
    processor.connect(audioContext.destination);

    console.log('Tab audio capture started');
  } catch (error) {
    console.error('Failed to start tab capture:', error);
  }
}

function stopCapture() {
  if (processor) {
    processor.disconnect();
    processor = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  console.log('Tab audio capture stopped');
}

function float32ToInt16(float32Array) {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16Array;
}
