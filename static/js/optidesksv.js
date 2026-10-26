/* ============================================================
   OptiDesk Core JavaScript
   Live clock, toast management, connectivity indicator.
   No external dependencies beyond Bootstrap 5.
   ============================================================ */

'use strict';

/* ── Toast initialisation ─────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toast').forEach(el => {
    const toast = new bootstrap.Toast(el);
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
  });
});

/* ── Live Clock ────────────────────────────────────────────── */
(function initClock() {
  const display = document.getElementById('clockDisplay');
  if (!display) return;

  // Server time offset (set by inline script from context_processors)
  let serverOffset = window.OD_SERVER_OFFSET_MS || 0;
  let lastSync = Date.now();
  const STALE_MS = 5 * 60 * 1000; // 5 minutes without sync = stale

  function tick() {
    const now = new Date(Date.now() + serverOffset);
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    display.textContent = `${h}:${m}:${s}`;
  }

  tick();
  setInterval(tick, 1000);

  // Re-sync server time every 5 minutes
  function syncServerTime() {
    fetch('/api/time/', { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        const serverMs = data.unix_ms;
        serverOffset = serverMs - Date.now();
        lastSync = Date.now();
        setConnectivity('online');
      })
      .catch(() => {
        if (Date.now() - lastSync > STALE_MS) {
          setConnectivity('stale');
        }
      });
  }

  setInterval(syncServerTime, 5 * 60 * 1000);
  syncServerTime();
})();

/* ── Connectivity Indicator ────────────────────────────────── */
function setConnectivity(state) {
  const badge = document.getElementById('connBadge');
  const icon  = document.getElementById('connIcon');
  const text  = document.getElementById('connText');
  if (!badge) return;

  badge.className = 'badge';
  if (state === 'online') {
    badge.classList.add('od-badge-online');
    icon.className = 'bi bi-wifi';
    text.textContent = 'Online';
  } else if (state === 'offline') {
    badge.classList.add('od-badge-offline');
    icon.className = 'bi bi-wifi-off';
    text.textContent = 'Offline';
  } else {
    badge.classList.add('od-badge-stale');
    icon.className = 'bi bi-exclamation-triangle';
    text.textContent = 'Stale';
  }
}

window.addEventListener('online',  () => setConnectivity('online'));
window.addEventListener('offline', () => setConnectivity('offline'));

/* ── CSRF helper for fetch() ───────────────────────────────── */
function getCsrfToken() {
  return document.cookie.split(';')
    .map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] || '';
}

window.odFetch = function(url, options = {}) {
  return fetch(url, {
    credentials: 'same-origin',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
};