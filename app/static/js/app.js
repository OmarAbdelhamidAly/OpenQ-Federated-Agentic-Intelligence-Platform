/**
 * App — SPA router, page rendering, and UI logic.
 */

// ── Toast System ───────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <span class="toast-message">${message}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── Plotly Loader ──────────────────────────────────────
let plotlyPromise = null;
function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (plotlyPromise) return plotlyPromise;

  plotlyPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.plot.ly/plotly-2.27.0.min.js';
    script.onload = () => resolve(window.Plotly);
    script.onerror = () => reject(new Error('Failed to load Plotly'));
    document.head.appendChild(script);
  });
  return plotlyPromise;
}

// ── SPA Router ─────────────────────────────────────────
const routes = {
  dashboard: renderDashboard,
  'data-sources': renderDataSources,
  analysis: renderAnalysis,
  users: renderUsers,
  'source-dashboard': renderSourceDashboard,
};

function navigate(page) {
  if (!getAccessToken()) {
    renderAuth();
    return;
  }
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const activeNav = document.querySelector(`[data-page="${page}"]`);
  if (activeNav) activeNav.classList.add('active');

  const mainContent = document.getElementById('main-content');
  if (routes[page]) {
    renderPageWithSkeleton(page, mainContent);
  } else {
    renderPageWithSkeleton('dashboard', mainContent);
  }
}

async function renderPageWithSkeleton(page, container) {
  container.innerHTML = `
    <div class="skeleton-loader">
      <div class="skeleton-header"></div>
      <div class="skeleton-content">
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
        <div class="skeleton-line medium"></div>
        <div class="skeleton-line"></div>
      </div>
    </div>
  `;
  try {
    await routes[page](container);
  } catch (e) {
    console.error(`Error rendering page ${page}:`, e);
    container.innerHTML = `<div class="error-state">Failed to load page: ${e.message}</div>`;
  }
}

// ── Auth Page ──────────────────────────────────────────
function renderAuth() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-logo">
          <div class="logo-icon">🧠</div>
          <h1>Data Analyst Agent</h1>
          <p>AI-powered autonomous data analysis</p>
        </div>
        <div class="auth-tabs">
          <button class="auth-tab active" data-tab="login" id="tab-login">Sign In</button>
          <button class="auth-tab" data-tab="register" id="tab-register">Sign Up</button>
        </div>
        <div id="auth-form-login">
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="login-email" placeholder="you@company.com">
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" class="form-input" id="login-password" placeholder="••••••••">
          </div>
          <button class="btn btn-primary btn-full" id="btn-login">Sign In</button>
        </div>
        <div id="auth-form-register" class="hidden">
          <div class="form-group">
            <label class="form-label">Organization Name</label>
            <input type="text" class="form-input" id="reg-tenant" placeholder="Acme Corp">
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="reg-email" placeholder="you@company.com">
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" class="form-input" id="reg-password" placeholder="Min 8 characters">
          </div>
          <button class="btn btn-primary btn-full" id="btn-register">Create Account</button>
        </div>
      </div>
    </div>
  `;

  // Tab switching
  document.getElementById('tab-login').onclick = () => {
    document.getElementById('tab-login').classList.add('active');
    document.getElementById('tab-register').classList.remove('active');
    document.getElementById('auth-form-login').classList.remove('hidden');
    document.getElementById('auth-form-register').classList.add('hidden');
  };
  document.getElementById('tab-register').onclick = () => {
    document.getElementById('tab-register').classList.add('active');
    document.getElementById('tab-login').classList.remove('active');
    document.getElementById('auth-form-register').classList.remove('hidden');
    document.getElementById('auth-form-login').classList.add('hidden');
  };

  // Login
  document.getElementById('btn-login').onclick = async () => {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    if (!email || !password) return showToast('Please fill in all fields', 'error');
    try {
      const data = await api.login(email, password);
      setTokens(data.access_token, data.refresh_token);
      // Decode JWT to get user info
      const payload = JSON.parse(atob(data.access_token.split('.')[1]));
      setUser({ id: payload.sub, email, role: payload.role, tenant_id: payload.tenant_id });
      showToast('Welcome back! 🎉', 'success');
      renderApp();
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  // Register
  document.getElementById('btn-register').onclick = async () => {
    const tenant = document.getElementById('reg-tenant').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    if (!tenant || !email || !password) return showToast('Please fill in all fields', 'error');
    try {
      const data = await api.register(tenant, email, password);
      setTokens(data.access_token, data.refresh_token);
      const payload = JSON.parse(atob(data.access_token.split('.')[1]));
      setUser({ id: payload.sub, email, role: payload.role, tenant_id: payload.tenant_id });
      showToast('Account created! 🚀', 'success');
      renderApp();
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  // Enter key support
  document.querySelectorAll('.auth-card input').forEach(input => {
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        const loginVisible = !document.getElementById('auth-form-login').classList.contains('hidden');
        if (loginVisible) document.getElementById('btn-login').click();
        else document.getElementById('btn-register').click();
      }
    });
  });
}

// ── App Shell ──────────────────────────────────────────
function renderApp() {
  const user = getUser();
  if (!user) return renderAuth();

  const initials = user.email.substring(0, 2).toUpperCase();
  const isAdmin = user.role === 'admin';

  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="app-layout">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar-brand">
          <div class="sidebar-brand-icon">🧠</div>
          <span class="sidebar-brand-text">Data Analyst AI</span>
        </div>
        <nav class="sidebar-nav">
          <div class="nav-section">Main</div>
          <button class="nav-item active" data-page="dashboard" onclick="navigate('dashboard')">
            <span class="nav-icon">📊</span> Dashboard
          </button>
          <button class="nav-item" data-page="data-sources" onclick="navigate('data-sources')">
            <span class="nav-icon">📁</span> Data Sources
          </button>
          <button class="nav-item" data-page="analysis" onclick="navigate('analysis')">
            <span class="nav-icon">🔍</span> Analysis
          </button>
          ${isAdmin ? `
          <div class="nav-section">Admin</div>
          <button class="nav-item" data-page="users" onclick="navigate('users')">
            <span class="nav-icon">👥</span> Team Members
          </button>
          ` : ''}
        </nav>
        <div class="sidebar-user">
          <div class="sidebar-avatar">${initials}</div>
          <div class="sidebar-user-info">
            <div class="sidebar-user-name">${user.email}</div>
            <div class="sidebar-user-role">${user.role}</div>
          </div>
          <button class="btn-icon" onclick="logout()" title="Sign out">🚪</button>
        </div>
      </aside>
      <main class="main-content" id="main-content"></main>
    </div>
  `;
  navigate('dashboard');
}

function logout() {
  clearTokens();
  showToast('Signed out', 'info');
  renderAuth();
}

// ── Dashboard ──────────────────────────────────────────
async function renderDashboard(container) {
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">Your analytics overview at a glance</p>
      </div>
    </div>
    <div class="stats-grid" id="stats-grid">
      <div class="stat-card"><div class="stat-label">Data Sources</div><div class="stat-value" id="stat-sources">—</div></div>
      <div class="stat-card"><div class="stat-label">Analyses Run</div><div class="stat-value" id="stat-analyses">—</div></div>
      <div class="stat-card"><div class="stat-label">Team Members</div><div class="stat-value" id="stat-users">—</div></div>
      <div class="stat-card"><div class="stat-label">Success Rate</div><div class="stat-value" id="stat-success">—</div></div>
    </div>
    <div class="section-grid">
      <div class="card">
        <div class="card-header"><span class="card-title">Recent Analyses</span></div>
        <div class="card-body" id="recent-analyses">
          <div class="empty-state">
            <div class="empty-icon">🔍</div>
            <h3>No analyses yet</h3>
            <p>Go to the Analysis page to ask your first question</p>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Quick Actions</span></div>
        <div class="card-body">
          <div style="display:flex;flex-direction:column;gap:0.75rem;">
            <button class="btn btn-secondary" onclick="navigate('data-sources')">📁 Upload Data Source</button>
            <button class="btn btn-secondary" onclick="navigate('analysis')">🔍 New Analysis</button>
            ${getUser()?.role === 'admin' ? '<button class="btn btn-secondary" onclick="navigate(\'users\')">👥 Manage Team</button>' : ''}
          </div>
        </div>
      </div>
    </div>
  `;

  // Load stats
  try {
    const [sources, history] = await Promise.allSettled([
      api.listDataSources(),
      api.getAnalysisHistory(),
    ]);
    if (sources.status === 'fulfilled') {
      document.getElementById('stat-sources').textContent = sources.value.data_sources?.length || 0;
    }
    if (history.status === 'fulfilled') {
      const jobs = history.value.jobs || [];
      document.getElementById('stat-analyses').textContent = jobs.length;
      const done = jobs.filter(j => j.status === 'done').length;
      const rate = jobs.length > 0 ? Math.round((done / jobs.length) * 100) : 0;
      document.getElementById('stat-success').textContent = `${rate}%`;

      // Render recent
      if (jobs.length > 0) {
        const recent = jobs.slice(0, 5);
        document.getElementById('recent-analyses').innerHTML = `
          <div class="table-wrapper"><table class="data-table">
            <thead><tr><th>Question</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>${recent.map(j => `<tr>
              <td>${j.question?.substring(0, 50) || '—'}${j.question?.length > 50 ? '...' : ''}</td>
              <td><span class="badge badge-${j.status === 'done' ? 'success' : j.status === 'error' ? 'error' : 'warning'}">${j.status}</span></td>
              <td>${new Date(j.created_at || Date.now()).toLocaleDateString()}</td>
            </tr>`).join('')}</tbody>
          </table></div>`;
      }
    }
    // Load user count (admin only)
    if (getUser()?.role === 'admin') {
      try {
        const users = await api.listUsers();
        document.getElementById('stat-users').textContent = users.users?.length || 0;
      } catch { document.getElementById('stat-users').textContent = '—'; }
    } else {
      document.getElementById('stat-users').textContent = '—';
    }
  } catch { }
}

// ── Data Sources Page ──────────────────────────────────
async function renderDataSources(container) {
  const isAdmin = getUser()?.role === 'admin';
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Data Sources</h1>
        <p class="page-subtitle">Manage CSV files and SQL database connections</p>
      </div>
      ${isAdmin ? `<div style="display:flex;gap:0.75rem;">
        <button class="btn btn-secondary" onclick="showSQLModal()">🔗 Connect SQL</button>
        <button class="btn btn-primary" onclick="document.getElementById('file-input').click()">📤 Upload File</button>
        <input type="file" id="file-input" accept=".csv,.xlsx,.sqlite,.db,.sql" class="hidden">
      </div>` : ''}
    </div>
    ${isAdmin ? `
    <div class="upload-zone" id="upload-zone">
      <div class="upload-icon">📂</div>
      <div class="upload-text">Drag & drop your CSV, XLSX, SQLite or SQL file here, or <span>browse</span></div>
    </div>` : ''}
    <div class="card" style="margin-top:1.5rem;">
      <div class="card-header"><span class="card-title">Your Data Sources</span></div>
      <div class="card-body" id="sources-list">
        <div style="text-align:center;padding:2rem;"><div class="spinner" style="margin:0 auto;"></div></div>
      </div>
    </div>
    <!-- SQL Modal -->
    <div class="modal-overlay" id="sql-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">Connect SQL Database</h3><button class="btn-icon" onclick="closeSQLModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Connection Name</label><input class="form-input" id="sql-name" placeholder="Production DB"></div>
          <div class="form-group"><label class="form-label">Engine</label>
            <select class="form-select" id="sql-engine"><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option><option value="mssql">MS SQL Server</option></select>
          </div>
          <div class="form-group"><label class="form-label">Host</label><input class="form-input" id="sql-host" placeholder="localhost"></div>
          <div class="form-group"><label class="form-label">Port</label><input class="form-input" type="number" id="sql-port" value="5432"></div>
          <div class="form-group"><label class="form-label">Database</label><input class="form-input" id="sql-database" placeholder="mydb"></div>
          <div class="form-group"><label class="form-label">Username</label><input class="form-input" id="sql-username" placeholder="readonly_user"></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-input" type="password" id="sql-password"></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeSQLModal()">Cancel</button>
          <button class="btn btn-primary" id="btn-connect-sql">Connect</button>
        </div>
      </div>
    </div>
  `;

  // Setup file upload
  if (isAdmin) {
    const fileInput = document.getElementById('file-input');
    const uploadZone = document.getElementById('upload-zone');

    fileInput.onchange = async (e) => {
      if (e.target.files[0]) await handleUpload(e.target.files[0]);
    };

    uploadZone.onclick = () => fileInput.click();
    uploadZone.ondragover = (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); };
    uploadZone.ondragleave = () => uploadZone.classList.remove('dragover');
    uploadZone.ondrop = async (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      if (e.dataTransfer.files[0]) await handleUpload(e.dataTransfer.files[0]);
    };

    // SQL modal
    document.getElementById('btn-connect-sql').onclick = async () => {
      try {
        await api.connectSQL({
          name: document.getElementById('sql-name').value,
          engine: document.getElementById('sql-engine').value,
          host: document.getElementById('sql-host').value,
          port: parseInt(document.getElementById('sql-port').value),
          database: document.getElementById('sql-database').value,
          username: document.getElementById('sql-username').value,
          password: document.getElementById('sql-password').value,
        });
        closeSQLModal();
        showToast('SQL database connected! ✓', 'success');
        loadSources();
      } catch (e) { showToast(e.message, 'error'); }
    };
  }

  loadSources();
}

async function handleUpload(file) {
  try {
    showToast('Uploading...', 'info');
    await api.uploadFile(file);
    showToast(`"${file.name}" uploaded! ✓`, 'success');
    loadSources();
  } catch (e) { showToast(e.message, 'error'); }
}

async function loadSources() {
  try {
    const data = await api.listDataSources();
    const list = document.getElementById('sources-list');
    if (!data.data_sources?.length) {
      list.innerHTML = `<div class="empty-state"><div class="empty-icon">📂</div><h3>No data sources</h3><p>Upload a CSV file or connect a SQL database to get started</p></div>`;
      return;
    }
    list.innerHTML = data.data_sources.map(s => {
      let meta = 'Connected';
      if (s.type === 'csv' && s.schema_json?.row_count) {
        meta = `${s.schema_json.row_count.toLocaleString()} rows · ${s.schema_json.column_count} columns`;
      } else if (s.type === 'sql' && s.schema_json?.table_count) {
        meta = `${s.schema_json.table_count} tables · ${s.schema_json.total_columns || 'multiple'} columns`;
      }

      const statusIcon = {
        pending: '⏳',
        running: '<span class="spinner-sm"></span>',
        done: '✅',
        failed: '⚠️',
      }[s.auto_analysis_status] || '⏳';

      const statusLabel = {
        pending: 'Auto-analysis pending',
        running: 'AI is analysing your data…',
        done: 'AI insights ready',
        failed: 'Auto-analysis failed',
      }[s.auto_analysis_status] || '';

      return `
        <div class="source-item" id="source-item-${s.id}">
          <div class="source-icon ${s.type}">${s.type === 'csv' ? '📄' : '🗄️'}</div>
          <div class="source-info">
            <div class="source-name">${s.name}</div>
            <div class="source-meta">${s.type.toUpperCase()} · ${meta}</div>
            <div class="source-status">${statusIcon} ${statusLabel}</div>
          </div>
          <div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;">
            <span class="badge ${s.type === 'csv' ? 'badge-info' : 'badge-success'}">${s.type}</span>
            ${s.auto_analysis_status === 'done' ? `<button class="btn btn-sm btn-primary" onclick="openSourceDashboard('${s.id}')">📊 Dashboard</button>` : ''}
            <button class="btn btn-sm btn-secondary" onclick="navigateToAnalysis('${s.id}')">🔍 Ask</button>
            ${getUser()?.role === 'admin' ? `<button class="btn btn-sm btn-danger" onclick="deleteSource('${s.id}')">Delete</button>` : ''}
          </div>
        </div>
      `;
    }).join('');

    // Poll running sources
    const running = data.data_sources.filter(s => s.auto_analysis_status === 'running' || s.auto_analysis_status === 'pending');
    if (running.length > 0) {
      setTimeout(loadSources, 5000);
    }
  } catch (e) { showToast('Failed to load data sources', 'error'); }
}

function openSourceDashboard(sourceId) {
  window._dashboardSourceId = sourceId;
  navigate('source-dashboard');
}

function navigateToAnalysis(sourceId) {
  window._preselectedSourceId = sourceId;
  navigate('analysis');
}

async function deleteSource(id) {
  if (!confirm('Delete this data source?')) return;
  try {
    await api.deleteDataSource(id);
    showToast('Data source deleted', 'success');
    loadSources();
  } catch (e) { showToast(e.message, 'error'); }
}

function showSQLModal() { document.getElementById('sql-modal').classList.add('open'); }
function closeSQLModal() { document.getElementById('sql-modal').classList.remove('open'); }

// ── Analysis Page ──────────────────────────────────────
async function renderAnalysis(container) {
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Analysis</h1>
        <p class="page-subtitle">Ask questions about your data in plain English</p>
      </div>
    </div>
    <div class="analysis-container">
      <div class="analysis-main card">
        <div class="card-body" style="display:flex;flex-direction:column;height:100%;">
          <div class="form-group">
            <label class="form-label">Data Source</label>
            <select class="form-select" id="analysis-source"><option value="">Loading...</option></select>
          </div>
          <div class="analysis-messages" id="analysis-messages">
            <div class="empty-state">
              <div class="empty-icon">💡</div>
              <h3>Ask your data a question</h3>
              <p>Select a data source and type your question below</p>
            </div>
          </div>
          <div class="analysis-input-area">
            <input class="analysis-input" id="analysis-query" placeholder="e.g. What are the top 5 products by revenue this quarter?">
            <button class="btn btn-primary" id="btn-analyze">Analyze</button>
          </div>
        </div>
      </div>
      <div class="results-sidebar" id="results-sidebar">
        <div class="result-card">
          <div class="result-card-header">📊 Chart</div>
          <div class="result-card-body"><div class="chart-container" id="chart-area">Run an analysis to see charts</div></div>
        </div>
        <div class="result-card">
          <div class="result-card-header">💡 Executive Summary</div>
          <div class="result-card-body" id="exec-summary">Run an analysis to see insights</div>
        </div>
        <div class="result-card">
          <div class="result-card-header">🎯 Recommendations</div>
          <div class="result-card-body" id="recommendations">Run an analysis to see recommendations</div>
        </div>
      </div>
    </div>
  `;

  // Load sources for dropdown
  try {
    const data = await api.listDataSources();
    const select = document.getElementById('analysis-source');
    if (data.data_sources?.length) {
      select.innerHTML = data.data_sources.map(s =>
        `<option value="${s.id}">${s.name} (${s.type})</option>`
      ).join('');
      // Pre-select if coming from source dashboard
      if (window._preselectedSourceId) {
        select.value = window._preselectedSourceId;
        window._preselectedSourceId = null;
      }
    } else {
      select.innerHTML = '<option value="">No data sources available</option>';
    }
  } catch { }

  // Analyze button
  document.getElementById('btn-analyze').onclick = submitAnalysis;
  const inputEl = document.getElementById('analysis-query');

  inputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') submitAnalysis();
  });

  // Pre-fill question if navigated from AI Dashboard
  if (window._prefilledQuestion) {
    inputEl.value = window._prefilledQuestion;
    window._prefilledQuestion = null;
    // Auto-focus and simulate click if a source is also selected
    if (document.getElementById('analysis-source').value) {
      setTimeout(submitAnalysis, 300);
    }
  }
}

async function submitAnalysis() {
  const sourceId = document.getElementById('analysis-source').value;
  const question = document.getElementById('analysis-query').value.trim();
  if (!sourceId || !question) return showToast('Select a source and enter a question', 'error');

  const messages = document.getElementById('analysis-messages');

  // Add user message
  messages.innerHTML += `
    <div class="message message-user">
      <div class="message-avatar">👤</div>
      <div class="message-content"><div class="message-text">${question}</div></div>
    </div>
  `;

  // Add loading message
  messages.innerHTML += `
    <div class="message message-ai" id="ai-loading">
      <div class="message-avatar">🧠</div>
      <div class="message-content"><div class="message-text">Analyzing your data<span class="loading-dots"></span></div></div>
    </div>
  `;
  messages.scrollTop = messages.scrollHeight;
  document.getElementById('analysis-query').value = '';

  try {
    const job = await api.submitAnalysis(sourceId, question);

    // Poll for results
    let result = job;
    let attempts = 0;
    while (result.status === 'pending' || result.status === 'running') {
      await new Promise(r => setTimeout(r, 2000));
      result = await api.getJobStatus(job.id);
      attempts++;
      if (attempts > 60) break;
    }

    // Remove loading
    document.getElementById('ai-loading')?.remove();

    if (result.status === 'done') {
      const r = await api.getJobResult(job.id);
      messages.innerHTML += `
        <div class="message message-ai">
          <div class="message-avatar">🧠</div>
          <div class="message-content">
            <div class="message-text">${r.insight_report || 'Analysis complete.'}</div>
            ${r.follow_up_suggestions?.length ? `
            <div class="suggestions">
              ${r.follow_up_suggestions.map(s => `<button class="suggestion-chip" onclick="document.getElementById('analysis-query').value='${s}';submitAnalysis();">${s}</button>`).join('')}
            </div>` : ''}
          </div>
        </div>
      `;

      // Update sidebar
      if (r.exec_summary) document.getElementById('exec-summary').textContent = r.exec_summary;
      if (r.chart_json) {
        document.getElementById('chart-area').innerHTML = '';
        loadPlotly().then(Plotly => {
          Plotly.newPlot('chart-area', r.chart_json.data, r.chart_json.layout, { responsive: true });
        }).catch(err => {
          console.error('Plotly load error:', err);
          document.getElementById('chart-area').innerHTML = `<div class="error-state">Failed to load chart library.</div>`;
        });
      }
      if (r.recommendations?.length) {
        document.getElementById('recommendations').innerHTML = r.recommendations.map(rec => `
          <div class="recommendation-item">
            <div class="rec-action">${rec.action}</div>
            <div class="rec-impact">${rec.expected_impact || ''}</div>
            <div class="rec-confidence">Confidence: ${rec.confidence_score || '—'}%</div>
          </div>
        `).join('');
      }
    } else {
      messages.innerHTML += `
        <div class="message message-ai">
          <div class="message-avatar">🧠</div>
          <div class="message-content"><div class="message-text">Analysis is still processing. Check back shortly or refresh the page.</div></div>
        </div>
      `;
    }
  } catch (e) {
    document.getElementById('ai-loading')?.remove();
    messages.innerHTML += `
      <div class="message message-ai">
        <div class="message-avatar">🧠</div>
        <div class="message-content"><div class="message-text" style="color:var(--error-400)">Error: ${e.message}</div></div>
      </div>
    `;
  }
  messages.scrollTop = messages.scrollHeight;
}

// ── Users Page ─────────────────────────────────────────
async function renderUsers(container) {
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Team Members</h1>
        <p class="page-subtitle">Manage who has access to your organization</p>
      </div>
      <button class="btn btn-primary" onclick="showInviteModal()">➕ Invite Member</button>
    </div>
    <div class="card">
      <div class="card-body" id="users-list">
        <div style="text-align:center;padding:2rem;"><div class="spinner" style="margin:0 auto;"></div></div>
      </div>
    </div>
    <!-- Invite Modal -->
    <div class="modal-overlay" id="invite-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">Invite Team Member</h3><button class="btn-icon" onclick="closeInviteModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Email</label><input class="form-input" id="invite-email" placeholder="colleague@company.com"></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-input" type="password" id="invite-password" placeholder="Temporary password"></div>
          <div class="form-group"><label class="form-label">Role</label>
            <select class="form-select" id="invite-role"><option value="viewer">Viewer</option><option value="admin">Admin</option></select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeInviteModal()">Cancel</button>
          <button class="btn btn-primary" id="btn-invite">Send Invite</button>
        </div>
      </div>
    </div>
  `;

  loadUsers();

  document.getElementById('btn-invite').onclick = async () => {
    try {
      await api.inviteUser(
        document.getElementById('invite-email').value,
        document.getElementById('invite-password').value,
        document.getElementById('invite-role').value,
      );
      closeInviteModal();
      showToast('Invitation sent! ✓', 'success');
      loadUsers();
    } catch (e) { showToast(e.message, 'error'); }
  };
}

async function loadUsers() {
  try {
    const data = await api.listUsers();
    const list = document.getElementById('users-list');
    if (!data.users?.length) {
      list.innerHTML = '<div class="empty-state"><h3>No team members</h3></div>';
      return;
    }
    list.innerHTML = data.users.map(u => `
      <div class="user-item">
        <div class="user-avatar-sm">${u.email.substring(0, 2).toUpperCase()}</div>
        <div class="source-info">
          <div class="source-name">${u.email}</div>
          <div class="source-meta">Joined ${new Date(u.created_at).toLocaleDateString()}</div>
        </div>
        <span class="badge ${u.role === 'admin' ? 'badge-info' : 'badge-neutral'}">${u.role}</span>
        ${u.id !== getUser()?.id ? `<button class="btn btn-sm btn-danger" onclick="removeUser('${u.id}')">Remove</button>` : ''}
      </div>
    `).join('');
  } catch (e) { showToast('Failed to load users', 'error'); }
}

async function removeUser(id) {
  if (!confirm('Remove this team member?')) return;
  try {
    await api.removeUser(id);
    showToast('User removed', 'success');
    loadUsers();
  } catch (e) { showToast(e.message, 'error'); }
}

function showInviteModal() { document.getElementById('invite-modal').classList.add('open'); }
function closeInviteModal() { document.getElementById('invite-modal').classList.remove('open'); }

// ── Boot ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (getAccessToken()) {
    renderApp();
  } else {
    renderAuth();
  }
});


// ══════════════════════════════════════════════════════
// ── SOURCE DASHBOARD (CSV & SQL) ──────────────────────
// ══════════════════════════════════════════════════════

async function renderSourceDashboard(container) {
  const sourceId = window._dashboardSourceId;
  if (!sourceId) { navigate('data-sources'); return; }

  // Loading state
  container.innerHTML = `
    <div class="page-header">
      <div><h1 class="page-title">📊 AI Dashboard</h1><p class="page-subtitle">Auto-generated insights for your data</p></div>
      <button class="btn btn-secondary" onclick="navigate('data-sources')">← Back to Sources</button>
    </div>
    <div class="dashboard-loading">
      <div class="loading-orb"></div>
      <h3>Loading your AI-generated insights…</h3>
      <p>Please wait</p>
    </div>
  `;

  try {
    let source = await api.getDashboard(sourceId);

    // If still running, poll and show spinner
    if (source.auto_analysis_status === 'running' || source.auto_analysis_status === 'pending') {
      container.innerHTML = `
        <div class="page-header">
          <div><h1 class="page-title">📊 AI Dashboard</h1><p class="page-subtitle">Auto-generated insights for your data</p></div>
          <button class="btn btn-secondary" onclick="navigate('data-sources')">← Back</button>
        </div>
        <div class="dashboard-loading">
          <div class="loading-orb"></div>
          <h3>AI is analysing your data…</h3>
          <p>The AI is exploring your data and generating 5 smart insights.<br>This takes about 30–60 seconds.</p>
          <div class="analysis-progress">
            <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
            <span class="progress-label" id="progress-label">Detecting data domain…</span>
          </div>
        </div>
      `;

      // Animate progress bar + poll
      const steps = [
        'Detecting data domain…',
        'Generating smart questions…',
        'Running analysis 1/5…',
        'Running analysis 2/5…',
        'Running analysis 3/5…',
        'Running analysis 4/5…',
        'Running analysis 5/5…',
        'Finalising insights…',
      ];
      let stepIdx = 0;
      const interval = setInterval(() => {
        if (stepIdx < steps.length - 1) stepIdx++;
        const fill = document.getElementById('progress-fill');
        const label = document.getElementById('progress-label');
        if (fill) fill.style.width = `${Math.round(((stepIdx + 1) / steps.length) * 100)}%`;
        if (label) label.textContent = steps[stepIdx];
      }, 4000);

      // Poll until done
      let attempts = 0;
      while ((source.auto_analysis_status === 'running' || source.auto_analysis_status === 'pending') && attempts < 30) {
        await new Promise(r => setTimeout(r, 4000));
        source = await api.getDashboard(sourceId);
        attempts++;
      }
      clearInterval(interval);
    }

    // Render the right dashboard based on source type
    if (source.type === 'csv') {
      await renderCSVDashboard(container, source);
    } else {
      await renderSQLDashboard(container, source);
    }
  } catch (e) {
    container.innerHTML = `<div class="error-state">Failed to load dashboard: ${e.message}</div>`;
  }
}


// ── CSV Dashboard ──────────────────────────────────────
async function renderCSVDashboard(container, source) {
  const schema = source.schema_json || {};
  const autoData = source.auto_analysis_json || {};
  const results = autoData.results || [];
  const domain = source.domain_type || autoData.domain_type || 'data';

  const cols = schema.columns || [];
  const numCols = cols.filter(c => ['float64', 'int64', 'int32', 'float32'].includes(c.dtype));
  const catCols = cols.filter(c => c.dtype === 'object');
  const dateCols = cols.filter(c => c.dtype.includes('date') || c.name.toLowerCase().includes('date') || c.name.toLowerCase().includes('time'));

  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">📄 CSV Dashboard</h1>
        <p class="page-subtitle">${source.name} · <span class="badge badge-info" style="text-transform:capitalize;">${domain}</span></p>
      </div>
      <div style="display:flex;gap:0.75rem;">
        <button class="btn btn-secondary" onclick="navigateToAnalysis('${source.id}')">🔍 Ask a Question</button>
        <button class="btn btn-secondary" onclick="navigate('data-sources')">← Back</button>
      </div>
    </div>

    <!-- Stats row -->
    <div class="stats-grid" style="margin-bottom:1.5rem;">
      <div class="stat-card">
        <div class="stat-label">Total Rows</div>
        <div class="stat-value">${(schema.row_count || 0).toLocaleString()}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Columns</div>
        <div class="stat-value">${schema.column_count || 0}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Numeric Columns</div>
        <div class="stat-value">${numCols.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Data Quality</div>
        <div class="stat-value" style="color:${(source.auto_analysis_json?.quality_score || 1) > 0.8 ? 'var(--success-400)' : 'var(--warning-400)'}">${Math.round((source.auto_analysis_json?.quality_score || 1) * 100)}%</div>
      </div>
    </div>

    <!-- Column profile -->
    <div class="card" style="margin-bottom:1.5rem;">
      <div class="card-header"><span class="card-title">📋 Column Profile</span></div>
      <div class="card-body" style="padding:0;overflow-x:auto;">
        <table class="data-table">
          <thead><tr><th>Column</th><th>Type</th><th>Sample Values</th></tr></thead>
          <tbody>
            ${cols.slice(0, 10).map(c => `
              <tr>
                <td style="font-weight:600;">${c.name}</td>
                <td><span class="badge ${numCols.find(n => n.name === c.name) ? 'badge-info' : dateCols.find(d => d.name === c.name) ? 'badge-warning' : 'badge-neutral'}">${c.dtype}</span></td>
                <td style="color:var(--text-muted);font-size:0.8rem;">${(c.sample_values || []).slice(0, 3).join(', ')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <!-- AI Insights grid -->
    <div class="section-title">🤖 AI-Generated Insights <span style="font-size:0.8rem;color:var(--text-muted);font-weight:400;">— ${results.length} analyses · auto-generated once</span></div>
    <div class="ai-insights-grid" id="insights-grid"></div>
  `;

  // Render cards with staggered animation
  await renderInsightCards(results, 'insights-grid', source.id);
}


// ── SQL Dashboard ──────────────────────────────────────
async function renderSQLDashboard(container, source) {
  const schema = source.schema_json || {};
  const autoData = source.auto_analysis_json || {};
  const results = autoData.results || [];
  const domain = source.domain_type || autoData.domain_type || 'database';
  const tables = schema.tables || [];

  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">🗄️ SQL Dashboard</h1>
        <p class="page-subtitle">${source.name} · <span class="badge badge-success" style="text-transform:capitalize;">${domain}</span></p>
      </div>
      <div style="display:flex;gap:0.75rem;">
        <button class="btn btn-secondary" onclick="navigateToAnalysis('${source.id}')">🔍 Ask a Question</button>
        <button class="btn btn-secondary" onclick="navigate('data-sources')">← Back</button>
      </div>
    </div>

    <!-- Stats row -->
    <div class="stats-grid" style="margin-bottom:1.5rem;">
      <div class="stat-card">
        <div class="stat-label">Tables</div>
        <div class="stat-value">${schema.table_count || tables.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Columns</div>
        <div class="stat-value">${schema.total_columns || '—'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Dialect</div>
        <div class="stat-value" style="font-size:1rem;">${(schema.dialect || schema.source_type || 'SQL').toUpperCase()}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AI Insights</div>
        <div class="stat-value" style="color:var(--success-400);">${results.filter(r => r.status === 'done').length}/${results.length || 5}</div>
      </div>
    </div>

    <!-- Schema explorer -->
    ${tables.length > 0 ? `
    <div class="card" style="margin-bottom:1.5rem;">
      <div class="card-header"><span class="card-title">🗂️ Schema Explorer</span></div>
      <div class="card-body">
        <div class="tables-grid">
          ${tables.map(t => `
            <div class="table-card">
              <div class="table-card-name">📋 ${t.table}</div>
              <div class="table-card-meta">${t.column_count} cols${t.row_count != null ? ' · ' + Number(t.row_count).toLocaleString() + ' rows' : ''}</div>
              <div class="table-card-cols">${(t.columns || []).slice(0, 4).map(c => `<span class="col-chip">${c.name}</span>`).join('')}${t.columns?.length > 4 ? `<span class="col-chip muted">+${t.columns.length - 4} more</span>` : ''}</div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>` : ''}

    <!-- AI Insights grid -->
    <div class="section-title">🤖 AI-Generated Insights <span style="font-size:0.8rem;color:var(--text-muted);font-weight:400;">— ${results.length} analyses · auto-generated once</span></div>
    <div class="ai-insights-grid" id="insights-grid"></div>
  `;

  // Render cards with staggered animation
  await renderInsightCards(results, 'insights-grid', source.id);
}


// ── Animated Insight Cards ─────────────────────────────
async function renderInsightCards(results, containerId, sourceId) {
  const grid = document.getElementById(containerId);
  if (!grid) return;

  if (!results || results.length === 0) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><div class="empty-icon">🤖</div><h3>No insights yet</h3><p>Auto-analysis may still be running.</p></div>`;
    return;
  }

  // Render each card with a stagger delay
  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    const card = document.createElement('div');
    card.className = 'insight-card';
    card.style.animationDelay = `${i * 0.12}s`;

    const statusBadge = r.status === 'done'
      ? `<span class="badge badge-success">✓ Done</span>`
      : `<span class="badge badge-error">⚠ Failed</span>`;

    card.innerHTML = `
      <div class="insight-card-header">
        <span class="insight-index">#${i + 1}</span>
        ${statusBadge}
      </div>
      <div class="insight-question">"${r.question}"</div>
      ${r.status === 'done' ? `
        <div class="insight-summary">${r.executive_summary || ''}</div>
        ${r.chart_json ? `<div class="insight-chart" id="chart-${sourceId}-${i}"></div>` : ''}
        <div class="insight-footer">
          <button class="btn btn-sm btn-secondary" onclick="navigateToAnalysisWithQ('${sourceId}', ${JSON.stringify(r.question).replace(/"/g, '&quot;')})">🔍 Ask follow-up</button>
        </div>
      ` : `<div style="color:var(--error-400);font-size:0.85rem;">${r.error || 'Analysis failed'}</div>`}
    `;

    grid.appendChild(card);

    // Render chart after DOM append
    if (r.status === 'done' && r.chart_json) {
      await loadPlotly().then(Plotly => {
        const chartEl = document.getElementById(`chart-${sourceId}-${i}`);
        if (chartEl) {
          Plotly.newPlot(chartEl, r.chart_json.data, r.chart_json.layout, {
            responsive: true, displayModeBar: false
          });
        }
      }).catch(() => { });
    }
  }
}

function navigateToAnalysisWithQ(sourceId, question) {
  window._preselectedSourceId = sourceId;
  window._prefilledQuestion = question;
  navigate('analysis');
}
