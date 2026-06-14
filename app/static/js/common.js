const API = {
  token: localStorage.getItem('edustream_token'),
  user: JSON.parse(localStorage.getItem('edustream_user') || 'null'),

  setAuth(token, user) {
    this.token = token;
    this.user = user;
    localStorage.setItem('edustream_token', token);
    localStorage.setItem('edustream_user', JSON.stringify(user));
  },

  clearAuth() {
    this.token = null;
    this.user = null;
    localStorage.removeItem('edustream_token');
    localStorage.removeItem('edustream_user');
  },

  async request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const res = await fetch(path, { ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.message || 'Request failed');
    return data;
  },

  logout() {
    this.clearAuth();
    window.location.href = '/login';
  }
};

function initTheme() {
  const saved = localStorage.getItem('edustream_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('edustream_theme', next);
}

function toast(msg, isError = false) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.style.borderColor = isError ? 'var(--danger)' : 'var(--border)';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function fmtTime(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return iso; }
}

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' }); }
  catch { return iso; }
}

function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function requireAuth(roles) {
  if (!API.user || !API.token) {
    window.location.href = '/login';
    return false;
  }
  if (roles && !roles.includes(API.user.role)) {
    window.location.href = '/dashboard';
    return false;
  }
  return true;
}

initTheme();
