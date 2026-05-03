/* ===== main.js — Shared utilities ===== */

// ── Toast Notifications ──────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', danger: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.4s'; }, 3000);
  setTimeout(() => toast.remove(), 3500);
}

// ── Tab Switching ────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const el = document.getElementById(target);
      if (el) el.classList.add('active');
    });
  });
}

// ── Modal ────────────────────────────────────────────────────────────────────
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('active');
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('active');
}
// Close on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
  }
});

// ── Form Validation Helpers ──────────────────────────────────────────────────
function validateRequired(input) {
  const val = input.value.trim();
  if (!val) { setInvalid(input, 'This field is required.'); return false; }
  setValid(input);
  return true;
}
function validateEmail(input) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!re.test(input.value.trim())) { setInvalid(input, 'Invalid email address.'); return false; }
  setValid(input);
  return true;
}
function validatePhone(input) {
  if (!/^\d{10}$/.test(input.value.trim())) { setInvalid(input, 'Phone must be exactly 10 digits.'); return false; }
  setValid(input);
  return true;
}
function validatePasswordMatch(p1, p2) {
  if (p1.value !== p2.value) { setInvalid(p2, 'Passwords do not match.'); return false; }
  setValid(p2);
  return true;
}
function setInvalid(input, msg) {
  input.classList.add('is-invalid');
  input.classList.remove('is-valid');
  let err = input.nextElementSibling;
  if (err && err.classList.contains('form-error')) { err.textContent = msg; err.style.display = 'block'; }
}
function setValid(input) {
  input.classList.remove('is-invalid');
  input.classList.add('is-valid');
  let err = input.nextElementSibling;
  if (err && err.classList.contains('form-error')) { err.style.display = 'none'; }
}

// ── SOS Button ───────────────────────────────────────────────────────────────
function triggerSOS() {
  const btn = document.getElementById('sos-btn');
  if (btn) { btn.disabled = true; btn.textContent = '🚨 Sending Alert...'; }
  fetch('/sos', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
    .then(r => r.json())
    .then(data => {
      showToast(data.message, 'danger');
      document.getElementById('sos-result').innerHTML =
        `<div class="alert alert-danger">🚨 ${data.message}</div>`;
      if (btn) { btn.textContent = '✅ Alert Sent!'; btn.style.background = '#10b981'; }
    })
    .catch(() => { showToast('Failed to send SOS. Try again.', 'danger'); if (btn) btn.disabled = false; });
}

// ── Share Location ───────────────────────────────────────────────────────────
function shareLocation() {
  const btn = document.getElementById('loc-btn');
  if (btn) { btn.disabled = true; btn.textContent = '📡 Sharing...'; }
  fetch('/share-location', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
    .then(r => r.json())
    .then(data => {
      showToast(data.message, 'success');
      document.getElementById('loc-result').innerHTML =
        `<div class="alert alert-success">📍 ${data.message}</div>`;
      if (btn) { btn.textContent = '✅ Location Shared'; }
    })
    .catch(() => { showToast('Failed to share location.', 'danger'); if (btn) btn.disabled = false; });
}

// ── Voice Input (Speech API) ─────────────────────────────────────────────────
function startVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { showToast('Voice input not supported in this browser.', 'danger'); return; }
  const recognition = new SpeechRecognition();
  recognition.lang = 'en-IN';
  recognition.continuous = false;
  recognition.interimResults = false;
  const btn = document.getElementById('voice-btn');
  if (btn) { btn.textContent = '🔴 Listening...'; btn.disabled = true; }
  recognition.start();
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    const desc = document.getElementById('description');
    if (desc) desc.value = (desc.value ? desc.value + ' ' : '') + transcript;
    showToast('Voice captured successfully!', 'success');
  };
  recognition.onerror = () => showToast('Voice input failed. Please try again.', 'danger');
  recognition.onend = () => {
    if (btn) { btn.textContent = '🎤 Voice Input'; btn.disabled = false; }
  };
}

// ── Confirm Action ────────────────────────────────────────────────────────────
function confirmAction(msg, formId) {
  if (confirm(msg)) { document.getElementById(formId).submit(); }
}
// ── Theme Toggle (Day/Night Mode) ─────────────────────────────────────────────
function initTheme() {
  const currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);

  // Inject toggle button into navbars dynamically
  const navbars = document.querySelectorAll('.navbar-links');
  navbars.forEach(nav => {
    if (!nav.querySelector('.theme-toggle')) {
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm theme-toggle';
      btn.style.background = 'transparent';
      btn.style.border = '1px solid var(--border)';
      btn.style.color = 'var(--text-primary)';
      btn.style.marginRight = '0.5rem';
      btn.innerHTML = currentTheme === 'light' ? '🌙 Night' : '☀️ Day';
      btn.onclick = toggleTheme;
      nav.insertBefore(btn, nav.firstChild);
    }
  });
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);

  document.querySelectorAll('.theme-toggle').forEach(btn => {
    btn.innerHTML = newTheme === 'light' ? '🌙 Night' : '☀️ Day';
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTabs();
  // Auto-dismiss flash alerts after 5s
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.5s'; setTimeout(() => el.remove(), 500); }, 5000);
  });
});
