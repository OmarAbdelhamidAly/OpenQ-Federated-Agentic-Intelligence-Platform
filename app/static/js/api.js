/**
 * API Client — wraps all fetch calls to the FastAPI backend.
 * Handles JWT token storage, automatic auth headers, and token refresh.
 */

const API_BASE = '/api/v1';

// ── Token Storage ──────────────────────────────────────
function getAccessToken() { return localStorage.getItem('access_token'); }
function getRefreshToken() { return localStorage.getItem('refresh_token'); }
function setTokens(access, refresh) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}
function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}
function getUser() {
  const u = localStorage.getItem('user');
  return u ? JSON.parse(u) : null;
}
function setUser(user) {
  localStorage.setItem('user', JSON.stringify(user));
}

// ── Core fetch wrapper ─────────────────────────────────
async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getAccessToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && getRefreshToken()) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getAccessToken()}`;
      return fetch(`${API_BASE}${path}`, { ...options, headers });
    }
  }

  return res;
}

async function refreshTokens() {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
    if (res.ok) {
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token);
      return true;
    }
  } catch { }
  clearTokens();
  return false;
}

// ── Auth API ───────────────────────────────────────────
const api = {
  async register(tenantName, email, password) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_name: tenantName, email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Registration failed');
    }
    return res.json();
  },

  async login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }
    return res.json();
  },

  // ── Users ──────────────────────────────────────────
  // ── Generic Helpers ─────────────────────────────────────
  async get(endpoint) {
    const res = await apiFetch(endpoint);
    if (!res.ok) throw new Error(`GET ${endpoint} failed: ${res.statusText}`);
    return res.json();
  },
  async post(endpoint, data) {
    const res = await apiFetch(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`POST ${endpoint} failed: ${res.statusText}`);
    return res.json();
  },

  // ── Users ─────────────────────────────────────────────
  async listUsers() {

    const res = await apiFetch('/users');
    if (!res.ok) throw new Error('Failed to load users');
    return res.json();
  },

  async inviteUser(email, password, role) {
    const res = await apiFetch('/users/invite', {
      method: 'POST',
      body: JSON.stringify({ email, password, role }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to invite user');
    }
    return res.json();
  },

  async removeUser(userId) {
    const res = await apiFetch(`/users/${userId}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to remove user');
    }
  },

  // ── Metrics ──────────────────────────────────────────
  async listMetrics() {
    const res = await apiFetch('/metrics');
    return res.json();
  },

  async createMetric(data) {
    const res = await apiFetch('/metrics', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create metric');
    }
    return res.json();
  },

  async deleteMetric(id) {
    const res = await apiFetch(`/metrics/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete metric');
    }
    return true;
  },

  // ── Knowledge Base ─────────────────────────────────
  async listKBs() {
    const res = await apiFetch('/knowledge');
    return res.json();
  },

  async createKB(data) {
    const res = await apiFetch('/knowledge', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.json();
  },

  async deleteKB(id) {
    return apiFetch(`/knowledge/${id}`, { method: 'DELETE' });
  },

  async listDocuments(kbId) {
    const res = await apiFetch(`/knowledge/${kbId}/documents`);
    return res.json();
  },

  async uploadDocument(kbId, file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.open('POST', `${API_BASE}/knowledge/${kbId}/upload`);
      xhr.setRequestHeader('Authorization', `Bearer ${getAccessToken()}`);

      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            onProgress(percent);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.response));
        } else {
          try {
            const err = JSON.parse(xhr.response);
            reject(new Error(err.detail || 'Upload failed'));
          } catch {
            reject(new Error('Upload failed'));
          }
        }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  },

  // ── Policies ───────────────────────────────────────
  async listPolicies() {
    const res = await apiFetch('/policies');
    return res.json();
  },

  async createPolicy(data) {
    const res = await apiFetch('/policies', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.json();
  },

  async deletePolicy(id) {
    return apiFetch(`/policies/${id}`, { method: 'DELETE' });
  },

  // ── Data Sources ───────────────────────────────────
  async listDataSources() {
    const res = await apiFetch('/data-sources');
    if (!res.ok) throw new Error('Failed to load data sources');
    return res.json();
  },

  async uploadFile(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.open('POST', `${API_BASE}/data-sources/upload`);

      // Auth header
      const token = getAccessToken();
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          const percent = Math.round((e.loaded / e.total) * 100);
          onProgress(percent);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || 'Upload failed'));
          } catch {
            reject(new Error('Upload failed'));
          }
        }
      };

      xhr.onerror = () => reject(new Error('Network error during upload'));
      xhr.send(formData);
    });
  },

  async connectSQL(data) {
    const res = await apiFetch('/data-sources/connect-sql', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Connection failed');
    }
    return res.json();
  },

  async deleteDataSource(id) {
    const res = await apiFetch(`/data-sources/${id}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error('Failed to delete');
  },

  async getDashboard(sourceId) {
    const res = await apiFetch(`/data-sources/${sourceId}/dashboard`);
    if (!res.ok) throw new Error('Failed to load dashboard');
    return res.json();
  },


  async submitAnalysis(sourceId, question, kbId = null) {
    const res = await apiFetch('/analysis/query', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId, question, kb_id: kbId }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Analysis failed');
    }
    return res.json();
  },

  async getJobStatus(jobId) {
    const res = await apiFetch(`/analysis/${jobId}`);
    if (!res.ok) throw new Error('Failed to get job status');
    return res.json();
  },

  async getJobResult(jobId) {
    const res = await apiFetch(`/analysis/${jobId}/result`);
    if (!res.ok) throw new Error('Failed to get job result');
    return res.json();
  },

  async getAnalysisHistory() {
    const res = await apiFetch('/analysis/history');
    if (!res.ok) throw new Error('Failed to load history');
    return res.json();
  },

  async approveJob(jobId) {
    const res = await apiFetch(`/analysis/${jobId}/approve`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Approval failed');
    }
    return res.json();
  },

  // ── Generic Helpers ─────────────────────────────────
  async get(path) {
    const res = await apiFetch(path, { method: 'GET' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `GET ${path} failed`);
    }
    return res.json();
  },

  async post(path, data) {
    const res = await apiFetch(path, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `POST ${path} failed`);
    }
    return res.json();
  },
};

// Export
window.api = api;
window.getUser = getUser;
window.setUser = setUser;
window.setTokens = setTokens;
window.clearTokens = clearTokens;
window.getAccessToken = getAccessToken;
