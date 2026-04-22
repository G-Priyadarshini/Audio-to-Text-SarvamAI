const API_BASE = 'http://localhost:8000';

console.debug('popup.js loaded, API_BASE=', API_BASE);

document.getElementById('openApp').addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('extension-page.html') });
  window.close();
});

document.getElementById('openHistory').addEventListener('click', () => {
  chrome.tabs.create({
    url: chrome.runtime.getURL('extension-page.html#history'),
  });
  window.close();
});

// Check backend health
async function checkHealth() {
  const statusEl = document.getElementById('status');
  try {
    const bases = [
      'http://127.0.0.1:8000',
      'http://localhost:8000',
      'http://127.0.0.1:5000',
      'http://localhost:5000',
    ];
    let ok = false;
    for (const b of bases) {
      const url = `${b}/health`;
      console.debug('popup checkHealth trying', url);
      try {
        const response = await fetch(url, { method: 'GET' });
        console.debug('popup health response', url, response.status);
        if (response.ok) { ok = true; break; }
      } catch (err) {
        console.warn('popup health fetch failed for', url, err);
      }
    }
    if (ok) {
      statusEl.textContent = '● Backend connected';
      statusEl.className = 'status connected';
    } else {
      statusEl.textContent = '● Backend error/offline';
      statusEl.className = 'status disconnected';
    }
  } catch (err) {
    console.error('popup checkHealth unexpected error:', err, err && err.stack);
    statusEl.textContent = '● Backend offline — start the server';
    statusEl.className = 'status disconnected';
  }
}

checkHealth();
