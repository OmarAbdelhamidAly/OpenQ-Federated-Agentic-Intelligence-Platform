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
  knowledge: renderKnowledge,
  'kb-detail': renderKBDetail,
  policies: renderPolicies,
  enrichment: renderEnrichment,
  about: renderAbout,
};

function navigate(page, params) {
  if (!getAccessToken()) {
    renderAuth();
    return;
  }
  if (params) window._pageParams = params;

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const activeNav = document.querySelector(`[data-page="${page}"]`);
  if (activeNav) activeNav.classList.add('active');

  const mainContent = document.getElementById('main-content');
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.remove('open');

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
          <h1>DataAnalyst.AI</h1>
          <p>Premium Autonomous Analysis</p>
        </div>
        <div class="auth-tabs">
          <button class="auth-tab active" data-tab="login" id="tab-login">Sign In</button>
          <button class="auth-tab" data-tab="register" id="tab-register">Sign Up</button>
        </div>
        <div id="auth-form-login">
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" class="form-input" id="login-email" placeholder="you@company.com">
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" class="form-input" id="login-password" placeholder="••••••••">
          </div>
          <button class="btn btn-primary btn-full" id="btn-login">Sign In — Let's Go</button>
        </div>
        <div id="auth-form-register" class="hidden">
          <div class="form-group">
            <label class="form-label">Organization Name</label>
            <input type="text" class="form-input" id="reg-tenant" placeholder="Acme Corp">
          </div>
          <div class="form-group">
            <label class="form-label">Work Email</label>
            <input type="email" class="form-input" id="reg-email" placeholder="you@company.com">
          </div>
          <div class="form-group">
            <label class="form-label">Choose Password</label>
            <input type="password" class="form-input" id="reg-password" placeholder="Min 8 characters">
          </div>
          <button class="btn btn-primary btn-full" id="btn-register">Create Global Account</button>
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
      <aside class="sidebar" id="sidebar" style="background: var(--glass-bg); backdrop-filter: blur(var(--glass-blur)); border-right: 1px solid var(--glass-border);">
        <div class="sidebar-brand">
          <div class="sidebar-brand-icon" style="color:var(--primary-400); margin-right:0.5rem; display:flex;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a5 5 0 0 0-5 5v2a5 5 0 0 0-2 4.41V16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2.59A5 5 0 0 0 17 9V7a5 5 0 0 0-5-5z"/></svg>
          </div>
          <span class="sidebar-brand-text">DATAANALYST.AI</span>
        </div>
        <nav class="sidebar-nav">
          <div class="nav-section">Insights</div>
          <button class="nav-item active" data-page="dashboard" onclick="navigate('dashboard')">
            <span class="nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M21 12H3"/><path d="M12 3v18"/></svg></span> Overview
          </button>
          <button class="nav-item" data-page="analysis" onclick="navigate('analysis')">
            <span class="nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span> Deep Analysis
          </button>
          <button class="nav-item" data-page="enrichment" onclick="navigate('enrichment')">
            <span class="nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg></span> Enrichment & Rules
          </button>
          <div class="nav-section">Management</div>
          <button class="nav-item" data-page="data-sources" onclick="navigate('data-sources')">
            <span class="nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></span> Data Sources
          </button>
          ${isAdmin ? `
          <button class="nav-item" data-page="users" onclick="navigate('users')">
            <span class="nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></span> Team Access
          </button>
          ` : ''}
          <div class="nav-section">System</div>
          <button class="nav-item" data-page="about" onclick="navigate('about')">
            <span class="nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg></span> About
          </button>
        </nav>
        <div class="sidebar-user" style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; align-items:center; gap:0.75rem;">
            <div class="sidebar-avatar">${initials}</div>
            <div class="sidebar-user-info">
              <div class="sidebar-user-name">${user.email.split('@')[0]}</div>
              <div class="sidebar-user-role">${user.role} Member</div>
            </div>
          </div>
          <button class="btn-icon" onclick="logout()" title="Sign out" style="border:none;background:transparent;color:var(--text-muted);cursor:pointer;padding:0.5rem;font-size:1.1rem;transition:color 0.2s;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          </button>
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
        <h1 class="page-title">Executive Overview</h1>
        <p class="page-subtitle">Real-time intelligence and system health</p>
      </div>
    </div>
    <div class="stats-grid" id="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Active Sources</div>
        <div class="stat-value" id="stat-sources">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Analyses</div>
        <div class="stat-value" id="stat-analyses">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Collaborators</div>
        <div class="stat-value" id="stat-users">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Success Rate</div>
        <div class="stat-value" id="stat-success">—</div>
      </div>
    </div>
    <div style="display:grid; grid-template-columns: 2fr 1fr; gap: 2.5rem;">
      <div class="card">
        <div class="card-header"><span class="card-title">Recent Intelligence</span></div>
        <div class="card-body" id="recent-analyses" style="padding:0;">
          <div class="empty-state" style="padding:4rem;">
            <div class="empty-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
            <h3>No activity yet</h3>
            <p>Initiate an analysis to see insights here.</p>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Quick Control</span></div>
        <div class="card-body">
          <div style="display:flex;flex-direction:column;gap:1rem;">
            <button class="btn btn-secondary btn-full" onclick="navigate('data-sources')">Manage Data</button>
            <button class="btn btn-primary btn-full" onclick="navigate('analysis')">New Deep Analysis</button>
            ${getUser()?.role === 'admin' ? '<button class="btn btn-secondary btn-full" onclick="navigate(\'users\')">Team Access</button>' : ''}
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
        <p class="page-subtitle">Manage files and database connections</p>
      </div>
      ${isAdmin ? `<div style="display:flex;gap:1rem;">
        <button class="btn btn-secondary" onclick="showSQLModal()">🔗 Connect SQL</button>
        <button class="btn btn-primary" onclick="document.getElementById('file-input').click()">📤 Upload File</button>
        <input type="file" id="file-input" accept=".csv,.xlsx,.sqlite,.db,.sql" class="hidden">
      </div>` : ''}
    </div>

    ${isAdmin ? `
    <div class="upload-zone" id="upload-zone">
      <div class="upload-icon">�</div>
      <div class="upload-text">Drag & drop files here, or <span>browse</span></div>
    </div>
    
    <!-- Upload Progress Card -->
    <div class="upload-status-card" id="upload-status-card">
      <div class="upload-status-header">
        <span id="upload-filename">uploading_file.csv</span>
        <span id="upload-percentage">0%</span>
      </div>
      <div class="progress-container" style="display: block; margin: 0;">
        <div class="progress-bar" id="upload-progress-bar"></div>
      </div>
    </div>
    ` : ''}

    <div class="card" style="margin-top:2.5rem;">
      <div class="card-header"><span class="card-title">Connected Sources</span></div>
      <div class="card-body" id="sources-list">
        <div style="text-align:center;padding:3rem;"><div class="spinner" style="margin:0 auto;"></div></div>
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
    if (fileInput) fileInput.onchange = async (e) => {
      if (e.target.files[0]) await handleUpload(e.target.files[0]);
    };
    if (uploadZone) {
      uploadZone.onclick = () => fileInput.click();
      uploadZone.ondragover = (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); };
      uploadZone.ondragleave = () => uploadZone.classList.remove('dragover');
      uploadZone.ondrop = async (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files[0]) await handleUpload(e.dataTransfer.files[0]);
      };
    }
    // SQL modal
    const connectBtn = document.getElementById('btn-connect-sql');
    if (connectBtn) connectBtn.onclick = async () => {
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
        navigate('enrichment');
      } catch (e) { showToast(e.message, 'error'); }
    };
  }
  loadSources();
}

async function handleUpload(file) {
  const statusCard = document.getElementById('upload-status-card');
  const progressBar = document.getElementById('upload-progress-bar');
  const percentageTxt = document.getElementById('upload-percentage');
  const filenameTxt = document.getElementById('upload-filename');

  if (statusCard) {
    statusCard.style.display = 'block';
    filenameTxt.textContent = `Uploading ${file.name}...`;
    progressBar.style.width = '0%';
    percentageTxt.textContent = '0%';
  }

  try {
    await api.uploadFile(file, (percent) => {
      if (progressBar) progressBar.style.width = `${percent}%`;
      if (percentageTxt) percentageTxt.textContent = `${percent}%`;
    });

    if (statusCard) {
      filenameTxt.textContent = `Processing ${file.name}...`;
      progressBar.style.width = '100%';
    }

    showToast(`"${file.name}" uploaded successfully!`, 'success');
    loadSources();
    navigate('enrichment');

    // Hide progress bar after a short delay
    setTimeout(() => {
      if (statusCard) statusCard.style.display = 'none';
    }, 2000);
  } catch (e) {
    showToast(e.message, 'error');
    if (statusCard) statusCard.style.display = 'none';
  }
}

async function loadSources() {
  try {
    const data = await api.listDataSources();
    const list = document.getElementById('sources-list');
    if (!data.data_sources?.length) {
      list.innerHTML = `<div class="empty-state" style="padding:4rem;"><div class="empty-icon">📂</div><h3>Ready for Data</h3><p>Upload a file or connect a database to begin analysis</p></div>`;
      return;
    }
    list.innerHTML = data.data_sources.map(s => {
      let meta = 'Connected';
      if (s.type === 'csv' && s.schema_json?.row_count) {
        meta = `${s.schema_json.row_count.toLocaleString()} rows · ${s.schema_json.column_count} cols`;
      } else if (s.type === 'sql' && s.schema_json?.table_count) {
        meta = `${s.schema_json.table_count} tables · ${s.schema_json.total_columns || 'DB'} cols`;
      }

      const statusIcon = {
        pending: '⏳',
        running: '<div class="spinner-sm"></div>',
        done: '✅',
        failed: '⚠️',
      }[s.auto_analysis_status] || '⏳';

      const statusLabel = {
        pending: 'Wait..',
        running: 'Analysing...',
        done: 'AI Insights Ready',
        failed: 'AI Failed',
      }[s.auto_analysis_status] || '';

      return `
        <div class="source-item card" style="display:flex;align-items:center;padding:1.5rem;margin-bottom:1rem;gap:1.5rem;background:rgba(255,255,255,0.02);border:1px solid var(--glass-border);border-radius:14px;transition:var(--transition);text-decoration:none;">
          <div class="source-icon ${s.type}" style="width:48px;height:48px;background:rgba(255,255,255,0.05);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;">
            ${s.type === 'csv' ? '📄' : '🗄️'}
          </div>
          <div class="source-info" style="flex:1;">
            <div class="source-name" style="font-weight:700;font-size:1.1rem;margin-bottom:0.25rem;">${s.name}</div>
            <div class="source-meta" style="font-size:0.85rem;color:var(--text-muted);"> ${s.type.toUpperCase()} · ${meta}</div>
          </div>
          <div class="source-status" style="display:flex;align-items:center;gap:0.5rem;font-size:0.85rem;font-weight:600;color:var(--primary-400);">
            ${statusIcon} ${statusLabel}
          </div>
          <div style="display:flex;gap:0.75rem;">
            ${s.auto_analysis_status === 'done' ? `<button class="btn btn-sm btn-primary" onclick="openSourceDashboard('${s.id}')">📊 Metrics</button>` : ''}
            <button class="btn btn-sm btn-secondary" onclick="navigateToAnalysis('${s.id}')">🔍 Query</button>
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
  } catch (e) {
    showToast('Failed to load data sources', 'error');
  }
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
  let initialSourceId = window._preselectedSourceId || '';
  window._preselectedSourceId = null;
  let qText = window._pageParams?.q || '';

  container.innerHTML = `
    <div class="page-header" style="margin-bottom:2rem;">
      <div>
        <h1 class="page-title">Deep Analysis</h1>
        <p class="page-subtitle">Ask questions and generate comprehensive Power BI-style dashboards</p>
      </div>
    </div>

    <!-- Power BI Analysis Card -->
    <div class="pbi-analysis-card" style="margin-bottom:2.5rem; border:1px solid rgba(99,102,241,0.2); box-shadow:0 8px 32px rgba(0,0,0,0.2);">
      <div class="pbi-header">
        <div class="pbi-header-left">
          <span class="pbi-icon">✨</span>
          <span class="pbi-title">New Request</span>
        </div>
      </div>
      <div class="pbi-body">
        <div class="form-group" style="margin-bottom:1.5rem;">
          <label class="form-label" style="font-weight:600; color:var(--text-light);">Select Data Source</label>
          <select class="form-select" id="analysis-source" style="max-width:400px; background:rgba(255,255,255,0.03);"></select>
        </div>
        
        <div class="form-group" style="margin-bottom:1.5rem;">
          <label class="form-label" style="font-weight:600; color:var(--text-light);">What would you like to analyze?</label>
          <textarea class="form-input" id="analysis-q" rows="3" placeholder="e.g. Give me a comprehensive overview of our sales performance over the latest year, broken down by region and product category." style="background:rgba(255,255,255,0.03); resize:vertical;">${qText}</textarea>
        </div>

        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem;">
          <div class="depth-selector" style="display:flex; align-items:center; gap:1rem;">
            <label class="form-label" style="margin:0; font-weight:600; color:var(--text-light);">Number of Insights:</label>
            <div class="pill-group" id="insight-count-pills">
              <button class="pill-btn" data-value="1">1</button>
              <button class="pill-btn" data-value="2">2</button>
              <button class="pill-btn active" data-value="3">3</button>
              <button class="pill-btn" data-value="4">4</button>
              <button class="pill-btn" data-value="5">5</button>
            </div>
            <span style="font-size:0.8rem; color:var(--text-muted); margin-left:0.5rem;" id="insight-count-hint">Generates 3 distinct charts</span>
          </div>
          
          <button class="btn btn-primary" id="btn-analyze" style="padding:0.75rem 2rem; font-weight:600; font-size:1rem; box-shadow:0 4px 12px rgba(99,102,241,0.3);">
            🚀 Run Analysis
          </button>
        </div>
      </div>
    </div>
    
    <!-- PBI Results Grid (Auto-fitting) -->
    <div id="pbi-results-grid" style="display:none; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap:1.5rem; margin-bottom:3rem;">
    </div>
  `;

  try {
    const data = await api.listDataSources();
    const select = document.getElementById('analysis-source');
    if (data.data_sources?.length) {
      select.innerHTML = data.data_sources.map(s => `<option value="${s.id}">${s.name} (${s.type})</option>`).join('');
      if (initialSourceId) select.value = initialSourceId;
    } else {
      select.innerHTML = '<option value="">No data sources available</option>';
    }
  } catch (e) { }

  // Pill selector logic
  const pills = document.querySelectorAll('#insight-count-pills .pill-btn');
  const hint = document.getElementById('insight-count-hint');
  let selectedCount = 3;
  pills.forEach(p => {
    p.onclick = () => {
      pills.forEach(btn => btn.classList.remove('active'));
      p.classList.add('active');
      selectedCount = parseInt(p.dataset.value);
      hint.textContent = selectedCount === 1 ? 'Generates 1 detailed chart' : `Generates ${selectedCount} distinct charts`;
    };
  });

  document.getElementById('btn-analyze').onclick = submitCustomAnalysis;
}

function navigateToAnalysisWithQ(sourceId, q) {
  navigate('analysis', { q, sourceId });
}

async function submitCustomAnalysis() {
  const sourceId = document.getElementById('analysis-source').value;
  const q = document.getElementById('analysis-q').value;
  if (!sourceId || !q.trim()) return showToast('Please select source and enter a question', 'error');

  const btn = document.getElementById('btn-analyze');
  btn.disabled = true;
  btn.textContent = 'Submitting...';

  const grid = document.getElementById('pbi-results-grid');
  grid.style.display = 'grid';
  grid.innerHTML = '';

  const countEl = document.querySelector('#insight-count-pills .pill-btn.active');
  const count = countEl ? parseInt(countEl.dataset.value) : 3;
  if (count === 1) grid.style.gridTemplateColumns = '1fr';
  else if (count === 2) grid.style.gridTemplateColumns = '1fr 1fr';
  else grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(480px, 1fr))';

  try {
    const payloads = [];
    for (let i = 0; i < count; i++) {
      payloads.push(api.post('/analysis/query', { source_id: sourceId, question: q, context_id: count > 1 ? `Insight ${i + 1}/${count}` : null }));
    }

    showToast(`Dispatching ${count} isolated worker(s)...`, 'info');
    const results = await Promise.all(payloads);
    btn.textContent = '🚀 Run Analysis';
    btn.disabled = false;

    // Create a panel for each job
    for (let i = 0; i < results.length; i++) {
      const jobId = results[i].job_id;
      const panelHtml = `
          <div class="pbi-panel" id="pbi-panel-${jobId}">
            <div class="pbi-panel-header">
              <span class="pbi-panel-title">Insight ${i + 1}</span>
              <span class="pbi-panel-status badge badge-primary" id="pbi-status-${jobId}">Initializing...</span>
            </div>
            <div class="pbi-panel-chart" id="pbi-chart-${jobId}">
              <div class="spinner"></div>
            </div>
            <div class="pbi-panel-insight" id="pbi-insight-${jobId}"></div>
          </div>
        `;
      grid.insertAdjacentHTML('beforeend', panelHtml);

      pollPBIPanel(jobId, sourceId);
    }
  } catch (e) {
    showToast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = '🚀 Run Analysis';
  }
}

async function pollPBIPanel(jobId, sourceId) {
  let attempts = 0;
  while (attempts < 90) {
    try {
      const st = await api.get(`/analysis/${jobId}`);
      const s = st.status;
      const statusEl = document.getElementById(`pbi-status-${jobId}`);
      if (statusEl) {
        if (s === 'done') {
          return _renderPBIPanel(jobId, await api.get(`/analysis/${jobId}/result`), sourceId);
        } else if (s === 'failed') {
          return _setPBIPanelError(jobId, st.error || 'Failed to complete analysis');
        } else if (s === 'awaiting_approval') {
          return _renderApprovalState(jobId, st.sql_query, st.explanation);
        } else {
          statusEl.textContent = s.replace('_', ' ').toUpperCase();
        }
      }
    } catch (e) { console.warn('Poll error', e); }
    await new Promise(r => setTimeout(r, 3000));
    attempts++;
  }
  _setPBIPanelError(jobId, 'Analysis timed out');
}

function _renderApprovalState(jobId, sql, intent) {
  const statusEl = document.getElementById(`pbi-status-${jobId}`);
  const chartEl = document.getElementById(`pbi-chart-${jobId}`);
  const panelEl = document.getElementById(`pbi-panel-${jobId}`);

  if (statusEl) { statusEl.className = 'pbi-panel-status badge badge-warning'; statusEl.textContent = 'Needs Review'; }
  if (panelEl) panelEl.style.borderColor = 'var(--warning-500)';

  if (chartEl) {
    chartEl.innerHTML = `
      <div style="padding:1rem; height:100%; display:flex; flex-direction:column;">
        <h4 style="color:var(--warning-500); margin-bottom:0.5rem; display:flex; align-items:center; gap:0.5rem;">⚠️ Approval Required</h4>
        <p style="font-size:0.85rem; color:var(--text-light); margin-bottom:0.75rem;"><strong>AI Intent:</strong> ${intent || 'To securely fetch your data.'}</p>
        <div style="background:rgba(0,0,0,0.3); padding:0.75rem; border-radius:6px; flex:1; overflow-y:auto; overflow-x:auto; margin-bottom:1rem; border:1px solid rgba(255,255,255,0.05);">
          <code style="color:#60A5FA; font-size:0.8rem; white-space:pre;">${sql || 'SELECT * FROM ...'}</code>
        </div>
        <div style="display:flex; gap:0.75rem; justify-content:flex-end;">
          <button class="btn btn-sm btn-secondary" onclick="cancelJob('${jobId}')" style="color:var(--error-500);">Cancel</button>
          <button class="btn btn-sm btn-primary" onclick="approveJob('${jobId}')" style="background:var(--success-500); border-color:var(--success-500);">✓ Approve & Run</button>
        </div>
      </div>
    `;
  }
}

async function approveJob(jobId) {
  try {
    await api.post(`/analysis/${jobId}/approve`, {});
    const statusEl = document.getElementById(`pbi-status-${jobId}`);
    const panelEl = document.getElementById(`pbi-panel-${jobId}`);
    const chartEl = document.getElementById(`pbi-chart-${jobId}`);
    if (statusEl) { statusEl.className = 'pbi-panel-status badge badge-primary'; statusEl.textContent = 'Resuming...'; }
    if (panelEl) panelEl.style.borderColor = '';
    if (chartEl) chartEl.innerHTML = '<div class="spinner"></div>';

    pollPBIPanel(jobId, null);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function cancelJob(jobId) {
  const panelEl = document.getElementById(`pbi-panel-${jobId}`);
  if (panelEl) panelEl.style.borderColor = '';
  _setPBIPanelError(jobId, 'Analysis cancelled by user');
  showToast('Analysis cancelled', 'info');
}

async function _renderPBIPanel(jobId, result, sourceId) {
  const statusEl = document.getElementById(`pbi-status-${jobId}`);
  const chartEl = document.getElementById(`pbi-chart-${jobId}`);
  const insightEl = document.getElementById(`pbi-insight-${jobId}`);
  const panelEl = document.getElementById(`pbi-panel-${jobId}`);

  if (statusEl) { statusEl.className = 'pbi-panel-status badge badge-success'; statusEl.textContent = '✓ Ready'; }
  if (panelEl) panelEl.classList.add('done');

  // Render chart
  if (chartEl && result.chart_json) {
    try {
      const Plotly = await loadPlotly();
      chartEl.innerHTML = '';
      const layout = {
        ...(result.chart_json.layout || {}),
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(12,16,36,0.6)',
        font: { color: '#cbd5e1', family: 'Inter, sans-serif', size: 11 },
        margin: { t: 28, b: 40, l: 50, r: 16 },
        legend: { bgcolor: 'rgba(0,0,0,0)', font: { color: '#94a3b8' } },
        xaxis: { ...(result.chart_json.layout?.xaxis || {}), gridcolor: 'rgba(255,255,255,0.05)', linecolor: 'rgba(255,255,255,0.1)' },
        yaxis: { ...(result.chart_json.layout?.yaxis || {}), gridcolor: 'rgba(255,255,255,0.05)', linecolor: 'rgba(255,255,255,0.1)' },
      };
      Plotly.newPlot(chartEl, result.chart_json.data, layout, { responsive: true, displayModeBar: false });
    } catch (e) {
      chartEl.innerHTML = '<div class="pbi-no-chart">Chart unavailable</div>';
    }
  } else if (chartEl) {
    chartEl.innerHTML = '<div class="pbi-no-chart">No chart generated</div>';
  }

  // Render insight
  if (insightEl) {
    const text = result.executive_summary || result.insight_report || '';
    insightEl.innerHTML = text
      ? `<div class="pbi-insight-text">${text}</div>`
      : `<div class="pbi-insight-text" style="color:var(--text-muted)">No insight summary returned.</div>`;
  }
}

function _setPBIPanelError(jobId, msg) {
  const statusEl = document.getElementById(`pbi-status-${jobId}`);
  const chartEl = document.getElementById(`pbi-chart-${jobId}`);
  if (statusEl) { statusEl.className = 'pbi-panel-status badge badge-danger'; statusEl.textContent = 'Error'; }
  if (chartEl) chartEl.innerHTML = `<div class="pbi-no-chart" style="color:var(--error-500)">${msg}</div>`;
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

  const btnInvite = document.getElementById('btn-invite');
  if (btnInvite) {
    btnInvite.onclick = async () => {
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
      <div class="user-item card" style="display:flex;align-items:center;padding:1.25rem 1.5rem;margin-bottom:1rem;gap:1.5rem;background:rgba(255,255,255,0.02);border:1px solid var(--glass-border);border-radius:14px;">
        <div class="sidebar-avatar" style="width:40px;height:40px;flex-shrink:0;">${u.email.substring(0, 2).toUpperCase()}</div>
        <div class="source-info" style="flex:1;">
          <div class="source-name" style="font-weight:700;">${u.email}</div>
          <div class="source-meta" style="font-size:0.85rem;color:var(--text-muted);">Joined ${new Date(u.created_at).toLocaleDateString()}</div>
        </div>
        <span class="badge ${u.role === 'admin' ? 'badge-info' : 'badge-success'}">${u.role}</span>
        ${u.id !== getUser()?.id ? `<button class="btn btn-sm btn-secondary" style="color:#EF4444;border-color:rgba(239,68,68,0.2);" onclick="removeUser('${u.id}')">Remove</button>` : ''}
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

// ── Metrics Page ───────────────────────────────────────
async function renderMetrics(container) {
  const isAdmin = getUser()?.role === 'admin';
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Metric Dictionary</h1>
        <p class="page-subtitle">Define business terms to help the AI understand your data</p>
      </div>
      ${isAdmin ? `<button class="btn btn-primary" onclick="showMetricModal()">➕ Add Metric</button>` : ''}
    </div>
    <div class="card">
      <div class="card-body" id="metrics-list">
        <div style="text-align:center;padding:3rem;"><div class="spinner" style="margin:0 auto;"></div></div>
      </div>
    </div>
    <!-- Metric Modal -->
    <div class="modal-overlay" id="metric-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">Define New Metric</h3><button class="btn-icon" onclick="closeMetricModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Metric Name</label><input class="form-input" id="metric-name" placeholder="e.g. Monthly Active Users"></div>
          <div class="form-group"><label class="form-label">Business Definition</label><textarea class="form-input" id="metric-def" rows="3" placeholder="Explain what this means in plain English..."></textarea></div>
          <div class="form-group"><label class="form-label">Formula (Optional)</label><input class="form-input" id="metric-formula" placeholder="e.g. count(distinct user_id) where login_date > now() - interval '30 days'"></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeMetricModal()">Cancel</button>
          <button class="btn btn-primary" id="btn-save-metric">Save Metric</button>
        </div>
      </div>
    </div>
  `;

  loadMetrics();

  if (isAdmin) {
    document.getElementById('btn-save-metric').onclick = async () => {
      try {
        await api.createMetric({
          name: document.getElementById('metric-name').value,
          definition: document.getElementById('metric-def').value,
          formula: document.getElementById('metric-formula').value,
        });
        closeMetricModal();
        showToast('Metric defined! 📖', 'success');
        loadMetrics();
      } catch (e) { showToast(e.message, 'error'); }
    };
  }
}

async function loadMetrics() {
  try {
    const data = await api.listMetrics();
    const list = document.getElementById('metrics-list');
    if (!data.metrics?.length) {
      list.innerHTML = `<div class="empty-state" style="padding:4rem;"><div class="empty-icon">📖</div><h3>Dictionary is empty</h3><p>Defining metrics helps the AI provide more accurate business insights.</p></div>`;
      return;
    }
    list.innerHTML = `
      <div class="table-wrapper">
        <table class="data-table">
          <thead><tr><th>Metric</th><th>Definition</th><th>Formula</th><th>Actions</th></tr></thead>
          <tbody>${data.metrics.map(m => `
            <tr>
              <td style="font-weight:700;color:var(--primary-400);">${m.name}</td>
              <td style="max-width:300px;white-space:normal;font-size:0.9rem;">${m.definition}</td>
              <td><code>${m.formula || '—'}</code></td>
              <td style="text-align:right;">
                ${getUser()?.role === 'admin' ? `<button class="btn btn-sm btn-icon" title="Delete" onclick="handleMetricDelete('${m.id}')">🗑️</button>` : '—'}
              </td>
            </tr>
          `).join('')}</tbody>
        </table>
      </div>
    `;
  } catch (e) { showToast('Failed to load metrics', 'error'); }
}

async function handleMetricDelete(id) {
  if (!confirm('Remove this metric definition?')) return;
  try {
    await api.deleteMetric(id);
    showToast('Metric removed', 'info');
    loadMetrics();
  } catch (e) { showToast(e.message, 'error'); }
}

function showMetricModal() { document.getElementById('metric-modal').classList.add('open'); }
function closeMetricModal() { document.getElementById('metric-modal').classList.remove('open'); }

// ── Knowledge Base Page ──────────────────────────────────
async function renderKnowledge(container) {
  const isAdmin = getUser()?.role === 'admin';
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Knowledge Base</h1>
        <p class="page-subtitle">Manage documents and context for AI analysis</p>
      </div>
      ${isAdmin ? `<button class="btn btn-primary" onclick="showKBModal()">➕ New Collection</button>` : ''}
    </div>
    <div class="kb-grid" id="kb-list">
      <div style="text-align:center;padding:3rem;grid-column:1/-1;"><div class="spinner" style="margin:0 auto;"></div></div>
    </div>
    <!-- KB Modal -->
    <div class="modal-overlay" id="kb-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">New Knowledge Base</h3><button class="btn-icon" onclick="closeKBModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Name</label><input class="form-input" id="kb-name" placeholder="e.g. Legal Documents"></div>
          <div class="form-group"><label class="form-label">Description</label><textarea class="form-input" id="kb-desc" rows="2" placeholder="What kind of documents are in this collection?"></textarea></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeKBModal()">Cancel</button>
          <button class="btn btn-primary" id="btn-save-kb">Create Collection</button>
        </div>
      </div>
    </div>
  `;

  loadKnowledgeBases();

  if (isAdmin) {
    document.getElementById('btn-save-kb').onclick = async () => {
      try {
        await api.createKB({
          name: document.getElementById('kb-name').value,
          description: document.getElementById('kb-desc').value,
        });
        closeKBModal();
        showToast('Knowledge Base created! 🧠', 'success');
        loadKnowledgeBases();
      } catch (e) { showToast(e.message, 'error'); }
    };
  }
}

async function loadKnowledgeBases() {
  try {
    const data = await api.listKBs();
    const list = document.getElementById('kb-list');
    if (!data.knowledge_bases?.length) {
      list.innerHTML = `<div class="empty-state" style="grid-column:1/-1;padding:4rem;"><div class="empty-icon">🧠</div><h3>No collections yet</h3><p>Create a collection to start indexing your documents.</p></div>`;
      return;
    }
    list.innerHTML = data.knowledge_bases.map(kb => `
      <div class="card kb-card" onclick="navigate('kb-detail', { id: '${kb.id}', name: '${kb.name}' })" style="cursor:pointer;transition:transform 0.2s;">
        <div class="card-body">
          <div style="font-size:2rem;margin-bottom:1rem;">📂</div>
          <h3 style="margin:0 0 0.5rem 0;">${kb.name}</h3>
          <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:1rem;">${kb.description || 'No description'}</p>
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.8rem;color:var(--primary-400);">
            <span>${kb.document_count} Documents</span>
            <span>View Details →</span>
          </div>
        </div>
      </div>
    `).join('');
  } catch (e) { showToast('Failed to load collections', 'error'); }
}

function showKBModal() { document.getElementById('kb-modal').classList.add('open'); }
function closeKBModal() { document.getElementById('kb-modal').classList.remove('open'); }

// ── KB Detail Page ──────────────────────────────────────
async function renderKBDetail(container) {
  const kb = window._pageParams;
  if (!kb || !kb.id) { navigate('knowledge'); return; }

  const isAdmin = getUser()?.role === 'admin';
  container.innerHTML = `
    <div class="page-header">
      <div>
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
          <button class="btn-icon" onclick="navigate('knowledge')" style="padding:0;">←</button>
          <span style="color:var(--text-muted);">Knowledge Base</span>
        </div>
        <h1 class="page-title">📂 ${kb.name}</h1>
      </div>
      ${isAdmin ? `
      <div style="display:flex;gap:0.75rem;">
        <label class="btn btn-primary" style="margin:0;cursor:pointer;">
          ➕ Upload Document
          <input type="file" id="kb-file-upload" style="display:none;" onchange="handleKBFileUpload('${kb.id}')">
        </label>
        <button class="btn btn-secondary" style="color:#EF4444;" onclick="handleKBDelete('${kb.id}')">Delete Collection</button>
      </div>
      ` : ''}
    </div>

    <!-- Upload Progress Card -->
    <div id="kb-upload-card" class="card" style="display:none;margin-bottom:1.5rem;background:rgba(255,255,255,0.02);border:1px solid var(--glass-border);">
      <div class="card-body" style="padding:1rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
          <span id="kb-upload-filename" style="font-weight:600;">document.pdf</span>
          <span id="kb-upload-percent">0%</span>
        </div>
        <div class="progress-bar-container"><div id="kb-upload-progress" class="progress-bar" style="width:0%;"></div></div>
        <div id="kb-upload-status" style="font-size:0.75rem;margin-top:0.5rem;color:var(--text-muted);">Uploading to secure vault...</div>
      </div>
    </div>

    <div class="card">
      <div class="card-body" id="document-list">
        <div style="text-align:center;padding:3rem;"><div class="spinner" style="margin:0 auto;"></div></div>
      </div>
    </div>
  `;

  loadDocuments(kb.id);
}

async function loadDocuments(kbId) {
  try {
    const data = await api.listDocuments(kbId);
    const list = document.getElementById('document-list');
    if (!list) return;
    if (!data.documents?.length) {
      list.innerHTML = `<div class="empty-state" style="padding:4rem;"><div class="empty-icon">📄</div><h3>Empty Collection</h3><p>Upload PDFs or text files to add context for the AI.</p></div>`;
      return;
    }
    list.innerHTML = `
      <div class="table-wrapper">
        <table class="data-table">
          <thead><tr><th>Name</th><th>Status</th><th>Added</th><th>Actions</th></tr></thead>
          <tbody>${data.documents.map(doc => {
      let statusBadge = '';
      if (doc.status === 'indexed') statusBadge = '<span class="badge badge-success">✓ Indexed</span>';
      else if (doc.status === 'error') statusBadge = '<span class="badge badge-error">⚠ Error</span>';
      else statusBadge = '<span class="badge badge-info">⌛ Processing</span>';

      return `
              <tr>
                <td style="font-weight:600;">${doc.name}</td>
                <td>${statusBadge}</td>
                <td style="font-size:0.85rem;">${new Date(doc.created_at).toLocaleDateString()}</td>
                <td>
                  ${getUser()?.role === 'admin' ? `
                    <button class="btn btn-sm btn-icon" title="Delete" onclick="deleteDocument('${kbId}', '${doc.id}')">🗑️</button>
                  ` : '—'}
                </td>
              </tr>
            `;
    }).join('')}</tbody>
        </table>
      </div>
    `;
  } catch (e) { showToast('Failed to load documents', 'error'); }
}

async function handleKBFileUpload(kbId) {
  const input = document.getElementById('kb-file-upload');
  const file = input.files[0];
  if (!file) return;

  const card = document.getElementById('kb-upload-card');
  const bar = document.getElementById('kb-upload-progress');
  const percentText = document.getElementById('kb-upload-percent');
  const nameText = document.getElementById('kb-upload-filename');
  const statusText = document.getElementById('kb-upload-status');

  nameText.innerText = file.name;
  card.style.display = 'block';
  bar.style.width = '0%';
  percentText.innerText = '0%';
  statusText.innerText = 'Uploading...';

  try {
    await api.uploadDocument(kbId, file, (percent) => {
      bar.style.width = `${percent}%`;
      percentText.innerText = `${percent}%`;
    });

    statusText.innerText = 'File saved. Indexing in progress...';
    setTimeout(() => {
      card.style.display = 'none';
      loadDocuments(kbId);
      showToast('Document uploaded! Indexing started.', 'success');
    }, 1500);
  } catch (e) {
    showToast(e.message, 'error');
    card.style.display = 'none';
  }
}

async function handleKBDelete(kbId) {
  if (!confirm('This will delete the entire collection and all its vectors. Continue?')) return;
  try {
    await api.deleteKB(kbId);
    showToast('Collection deleted', 'info');
    navigate('knowledge');
  } catch (e) { showToast('Delete failed', 'error'); }
}

async function renderPolicies(container) {
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Safety & Governance</h1>
        <p class="page-subtitle">Define guardrails to control AI behavior and data access</p>
      </div>
      <button class="btn btn-primary" onclick="showPolicyModal()">🛡️ Add Policy</button>
    </div>
    <div class="card">
      <div class="card-body">
        <table class="data-table">
          <thead>
            <tr>
              <th>Policy Name</th>
              <th>Type</th>
              <th>Description</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="policy-list">
            <tr><td colspan="4" style="text-align:center;padding:2rem;color:var(--text-muted);">Loading policies...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Policy Modal -->
    <div id="policy-modal" class="modal">
      <div class="modal-content card" style="max-width:500px;">
        <div class="card-header">🛡️ Define New Policy</div>
        <div class="card-body">
          <form id="policy-form" onsubmit="event.preventDefault(); handlePolicyCreate();">
            <div class="form-group" style="margin-bottom:1.5rem;">
              <label class="form-label">Policy Name</label>
              <input type="text" id="policy-name" class="form-input" placeholder="e.g. No PII Data" required>
            </div>
            <div class="form-group" style="margin-bottom:1.5rem;">
              <label class="form-label">Rule Type</label>
              <select id="policy-type" class="form-select">
                <option value="compliance">Compliance (Data access rules)</option>
                <option value="security">Security (Query restrictions)</option>
                <option value="cleaning">Data Quality (Processing rules)</option>
              </select>
            </div>
            <div class="form-group" style="margin-bottom:1.5rem;">
              <label class="form-label">Description (The AI Rule)</label>
              <textarea id="policy-desc" class="form-input" style="min-height:100px;" placeholder="e.g. Never allow the AI to select columns containing SSN, Credit Card info, or personal addresses." required></textarea>
            </div>
            <div style="display:flex;gap:1rem;justify-content:flex-end;">
              <button type="button" class="btn" onclick="closePolicyModal()">Cancel</button>
              <button type="submit" class="btn btn-primary">Create Policy</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  loadPolicies();
}

async function loadPolicies() {
  try {
    const data = await api.listPolicies();
    const list = document.getElementById('policy-list');
    if (list && data.policies?.length) {
      list.innerHTML = data.policies.map(p => `
        <tr>
          <td><span style="font-weight:500;">${p.name}</span></td>
          <td><span class="badge badge-${p.rule_type === 'security' ? 'error' : 'secondary'}">${p.rule_type}</span></td>
          <td style="color:var(--text-dim);font-size:0.9rem;max-width:300px;">${p.description}</td>
          <td><button class="btn btn-icon" onclick="handlePolicyDelete('${p.id}')">🗑️</button></td>
        </tr>
      `).join('');
    } else if (list) {
      list.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:3rem;color:var(--text-muted);">No policies defined yet.</td></tr>';
    }
  } catch (e) {
    showToast('Failed to load policies', 'error');
  }
}

async function handlePolicyCreate() {
  const data = {
    name: document.getElementById('policy-name').value,
    rule_type: document.getElementById('policy-type').value,
    description: document.getElementById('policy-desc').value,
  };
  try {
    await api.createPolicy(data);
    showToast('Policy active', 'success');
    closePolicyModal();
    loadPolicies();
  } catch (e) { showToast(e.message, 'error'); }
}

async function handlePolicyDelete(id) {
  if (!confirm('Are you sure you want to remove this guardrail?')) return;
  try {
    await api.deletePolicy(id);
    showToast('Policy removed', 'info');
    loadPolicies();
  } catch (e) { showToast('Delete failed', 'error'); }
}

function showPolicyModal() { document.getElementById('policy-modal').classList.add('open'); }
function closePolicyModal() { document.getElementById('policy-modal').classList.remove('open'); }


// ── Enrichment Page ───────────────────────────────────────
async function renderEnrichment(container) {
  const isAdmin = getUser()?.role === 'admin';
  container.innerHTML = `
    <div class="page-header" style="margin-bottom:2rem;">
      <div>
        <h1 class="page-title">Data Enrichment & Rules</h1>
        <p class="page-subtitle">Define business logic, organizational context, and safety guardrails.</p>
      </div>
      <button class="btn btn-primary" onclick="navigate('dashboard')" style="background:var(--primary-600); border:none; box-shadow:0 4px 12px rgba(99,102,241,0.3);">
        Finish & View Dashboard 👉
      </button>
    </div>

    <!-- Modals (hidden by default) -->
    <div class="modal-overlay" id="metric-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">Define Business Metric</h3><button class="btn-icon" onclick="closeMetricModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Metric Name</label><input class="form-input" id="metric-name" placeholder="e.g. MRR"></div>
          <div class="form-group"><label class="form-label">Calculation Logic</label><textarea class="form-input" id="metric-logic" rows="4" placeholder="Sum of active subscriptions..."></textarea></div>
        </div>
        <div class="modal-footer"><button class="btn btn-secondary" onclick="closeMetricModal()">Cancel</button><button class="btn btn-primary" id="btn-save-metric">Save</button></div>
      </div>
    </div>

    <div class="modal-overlay" id="kb-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">Upload Knowledge Document</h3><button class="btn-icon" onclick="closeKBModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Title / Subject</label><input class="form-input" id="kb-title" placeholder="e.g. Q3 Marketing Plan"></div>
          <div class="form-group"><label class="form-label">Upload File</label><input type="file" id="kb-file" class="form-input" accept=".txt,.md,.pdf,.csv"></div>
        </div>
        <div class="modal-footer"><button class="btn btn-secondary" onclick="closeKBModal()">Cancel</button><button class="btn btn-primary" id="btn-upload-kb">Upload</button></div>
      </div>
    </div>

    <div class="modal-overlay" id="policy-modal">
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">Create Data Policy</h3><button class="btn-icon" onclick="closePolicyModal()">✕</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Policy Title</label><input class="form-input" id="policy-title" placeholder="e.g. PII Masking"></div>
          <div class="form-group"><label class="form-label">Rules</label><textarea class="form-input" id="policy-content" rows="4" placeholder="Never expose SSN..."></textarea></div>
        </div>
        <div class="modal-footer"><button class="btn btn-secondary" onclick="closePolicyModal()">Cancel</button><button class="btn btn-primary" id="btn-save-policy">Save</button></div>
      </div>
    </div>

    <div class="enrichment-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:1.5rem;">
      <div class="card enrichment-card">
        <div class="card-header">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <span class="card-title">📖 Metric Dictionary</span>
            ${isAdmin ? `<button class="btn btn-sm btn-primary" onclick="showMetricModal()">➕ Add</button>` : ''}
          </div>
          <div class="card-context" style="font-size:0.85rem; padding:0.75rem; background:rgba(255,255,255,0.03); border-radius:8px; border-left:3px solid var(--primary-500);">
            <div style="margin-bottom:0.4rem;"><strong>Description:</strong> Define business KPIs and calculation logic.</div>
            <div style="color:var(--primary-400); font-weight:600;">✨ Importance: Ensures the AI uses your formulas, preventing calculation errors.</div>
          </div>
        </div>
        <div class="card-body" id="metrics-list" style="max-height:400px; overflow-y:auto;">
          <div style="text-align:center;padding:2rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>

      <div class="card enrichment-card">
        <div class="card-header">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <span class="card-title">🧠 Knowledge Base</span>
            ${isAdmin ? `<button class="btn btn-sm btn-primary" onclick="showKBModal()">➕ New</button>` : ''}
          </div>
          <div class="card-context" style="font-size:0.85rem; padding:0.75rem; background:rgba(255,255,255,0.03); border-radius:8px; border-left:3px solid var(--accent-500);">
            <div style="margin-bottom:0.4rem;"><strong>Description:</strong> Upload documents for contextual background.</div>
            <div style="color:var(--accent-400); font-weight:600;">✨ Importance: Provides company-specific context (PDFs, guides) that isn't in your db.</div>
          </div>
        </div>
        <div class="card-body" id="kb-list" style="display:grid; grid-template-columns:1fr; gap:1rem; max-height:400px; overflow-y:auto;">
          <div style="text-align:center;padding:2rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>

      <div class="card enrichment-card">
        <div class="card-header">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <span class="card-title">🛡️ Safety & Governance</span>
            ${isAdmin ? `<button class="btn btn-sm btn-primary" onclick="showPolicyModal()">🛡️ Add</button>` : ''}
          </div>
          <div class="card-context" style="font-size:0.85rem; padding:0.75rem; background:rgba(255,255,255,0.03); border-radius:8px; border-left:3px solid #EF4444;">
            <div style="margin-bottom:0.4rem;"><strong>Description:</strong> Set rules for data access and behavior.</div>
            <div style="color:#EF4444; font-weight:600;">✨ Importance: Maintains enterprise-grade security and compliance.</div>
          </div>
        </div>
        <div class="card-body" id="policies-list" style="display:grid; grid-template-columns:1fr; gap:1rem; max-height:400px; overflow-y:auto;">
          <div style="text-align:center;padding:2rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>
    </div>
  `;

  if (window.loadMetrics) loadMetrics();
  if (window.loadDocuments) loadDocuments();
  if (window.loadPolicies) loadPolicies();

  const saveMetricBtn = document.getElementById('btn-save-metric');
  if (saveMetricBtn) {
    saveMetricBtn.onclick = async () => {
      try {
        await api.createMetric({ name: document.getElementById('metric-name').value, logic: document.getElementById('metric-logic').value, source_id: null });
        closeMetricModal();
        showToast('Metric created', 'success');
        if (window.loadMetrics) loadMetrics();
      } catch (e) { showToast(e.message, 'error'); }
    };
  }

  const uploadKbBtn = document.getElementById('btn-upload-kb');
  if (uploadKbBtn) {
    uploadKbBtn.onclick = async () => {
      const file = document.getElementById('kb-file').files[0];
      const title = document.getElementById('kb-title').value;
      if (!file || !title) return showToast('Title and file required', 'error');
      try {
        await handleKBFileUpload(file, title);
        closeKBModal();
        if (window.loadDocuments) loadDocuments();
      } catch (e) { showToast(e.message, 'error'); }
    };
  }

  const savePolicyBtn = document.getElementById('btn-save-policy');
  if (savePolicyBtn) {
    savePolicyBtn.onclick = async () => {
      try {
        await api.post('/policies', { name: document.getElementById('policy-title').value, rules: document.getElementById('policy-content').value, description: document.getElementById('policy-content').value });
        closePolicyModal();
        showToast('Policy created', 'success');
        if (window.loadPolicies) loadPolicies();
      } catch (e) { showToast(e.message, 'error'); }
    };
  }
}

window.showMetricModal = window.showMetricModal || function () { document.getElementById('metric-modal')?.classList.add('open'); };
window.closeMetricModal = window.closeMetricModal || function () { document.getElementById('metric-modal')?.classList.remove('open'); };
window.showKBModal = window.showKBModal || function () { document.getElementById('kb-modal')?.classList.add('open'); };
window.closeKBModal = window.closeKBModal || function () { document.getElementById('kb-modal')?.classList.remove('open'); };
window.showPolicyModal = window.showPolicyModal || function () { document.getElementById('policy-modal')?.classList.add('open'); };
window.closePolicyModal = window.closePolicyModal || function () { document.getElementById('policy-modal')?.classList.remove('open'); };

// ── About Page ──────────────────────────────────────────
async function renderAbout(container) {
  container.innerHTML = `
    <div class="page-header" style="margin-bottom:2.5rem; text-align:center;">
      <div>
        <h1 class="page-title" style="font-size:2.5rem; letter-spacing:-0.5px; background: linear-gradient(to right, #ffffff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">DATAANALYST.AI</h1>
        <p class="page-subtitle" style="font-size:1.1rem; max-width:600px; margin:0 auto; color:var(--text-muted);">The intelligent engine transforming raw data into actionable enterprise insights.</p>
      </div>
    </div>

    <div style="max-width:900px; margin:0 auto;">
      
      <!-- Hero Section -->
      <div class="card" style="margin-bottom:3rem; padding:3.5rem 2.5rem; text-align:center; background: var(--glass-bg); backdrop-filter: blur(var(--glass-blur)); border: 1px solid var(--glass-border); border-top: 2px solid var(--primary-500); box-shadow: 0 20px 40px rgba(0,0,0,0.3);">
        <h2 style="font-size:1.75rem; font-weight:500; margin-bottom:1.5rem; color:var(--text-light); letter-spacing: -0.5px;">Democratizing Data Science</h2>
        <p style="font-size:1.05rem; color:var(--text-muted); max-width:650px; margin:0 auto; line-height:1.75;">
          DataAnalyst.AI empowers teams to make targeted, data-driven decisions without requiring a dedicated engineering department. By establishing secure, direct connections to your databases and contextual documents, we transition complex analytical workloads into intuitive conversations.
        </p>
      </div>

      <!-- Core Capabilities Grid -->
      <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1.5rem;">
        <h3 style="margin:0; font-size:1.25rem; font-weight:500; color:var(--text-light);">Core Architecture</h3>
        <div style="flex:1; height:1px; background:var(--glass-border);"></div>
      </div>
      
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:1.5rem; margin-bottom:4rem;">
        
        <div class="card" style="padding:2rem 1.5rem; background:rgba(255,255,255,0.015); border:1px solid rgba(255,255,255,0.05); transition:transform 0.2s;">
          <div style="height:48px; width:48px; border-radius:12px; background:rgba(99,102,241,0.1); display:flex; align-items:center; justify-content:center; margin-bottom:1.25rem; color:var(--primary-400);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M21 12H3"/><path d="M12 3v18"/></svg>
          </div>
          <h4 style="margin-bottom:0.75rem; color:var(--text-light); font-weight:500; font-size:1.1rem;">Multi-Insight Generation</h4>
          <p style="font-size:0.9rem; color:var(--text-muted); line-height:1.6; margin:0;">
            Produce comprehensive dashboards through a single natural language prompt. Specialized agents analyze inputs to compute optimal visual representation, rendering discrete, dynamic Plotly components.
          </p>
        </div>

        <div class="card" style="padding:2rem 1.5rem; background:rgba(255,255,255,0.015); border:1px solid rgba(255,255,255,0.05); transition:transform 0.2s;">
          <div style="height:48px; width:48px; border-radius:12px; background:rgba(245,158,11,0.1); display:flex; align-items:center; justify-content:center; margin-bottom:1.25rem; color:var(--warning-400);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
          </div>
          <h4 style="margin-bottom:0.75rem; color:var(--text-light); font-weight:500; font-size:1.1rem;">HITL Security Model</h4>
          <p style="font-size:0.9rem; color:var(--text-muted); line-height:1.6; margin:0;">
            Maintain strict governance overhead with Human-in-the-Loop workflows. AI-generated SQL execution intent is suspended, requiring explicit manual sign-off before hitting production workloads.
          </p>
        </div>

        <div class="card" style="padding:2rem 1.5rem; background:rgba(255,255,255,0.015); border:1px solid rgba(255,255,255,0.05); transition:transform 0.2s;">
          <div style="height:48px; width:48px; border-radius:12px; background:rgba(16,185,129,0.1); display:flex; align-items:center; justify-content:center; margin-bottom:1.25rem; color:var(--success-400);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" y1="22" x2="12" y2="12"/></svg>
          </div>
          <h4 style="margin-bottom:0.75rem; color:var(--text-light); font-weight:500; font-size:1.1rem;">Unified Context Engine</h4>
          <p style="font-size:0.9rem; color:var(--text-muted); line-height:1.6; margin:0;">
            Automatically harmonize structured rule ingestion (SQL logic and formulas) with unstructured Retrieval-Augmented Generation (RAG docs) for deeply contextual, highly-accurate AI formulation.
          </p>
        </div>

      </div>

      <!-- Tech Stack -->
      <div class="card" style="padding:2.5rem; margin-bottom:3rem; background:var(--glass-bg); border:1px solid var(--glass-border);">
        <h3 style="margin:0 0 1.5rem 0; font-size:1.25rem; font-weight:500; color:var(--text-light);">Deployment Stack</h3>
        <p style="color:var(--text-muted); line-height:1.6; margin-bottom:2rem; max-width:700px; font-size:0.95rem;">
          At its core, DataAnalyst.AI utilizes a scalable multi-agent infrastructure. Independent worker agents collaborate seamlessly to map logical database relationships (ERD discovery), synthesize optimized sequential queries, and assemble final state reporting blocks.
        </p>
        <div style="display:flex; gap:0.75rem; flex-wrap:wrap;">
          <span class="badge" style="background:rgba(255,255,255,0.03); color:var(--text-light); padding:0.5rem 1rem; font-size:0.8rem; border:1px solid rgba(255,255,255,0.1); border-radius:20px; font-weight:400; letter-spacing:0.5px;">AUTONOMOUS AGENTS</span>
          <span class="badge" style="background:rgba(255,255,255,0.03); color:var(--text-light); padding:0.5rem 1rem; font-size:0.8rem; border:1px solid rgba(255,255,255,0.1); border-radius:20px; font-weight:400; letter-spacing:0.5px;">RAG VECTORIZATION</span>
          <span class="badge" style="background:rgba(255,255,255,0.03); color:var(--text-light); padding:0.5rem 1rem; font-size:0.8rem; border:1px solid rgba(255,255,255,0.1); border-radius:20px; font-weight:400; letter-spacing:0.5px;">SEMANTIC SQL LAYER</span>
          <span class="badge" style="background:rgba(255,255,255,0.03); color:var(--text-light); padding:0.5rem 1rem; font-size:0.8rem; border:1px solid rgba(255,255,255,0.1); border-radius:20px; font-weight:400; letter-spacing:0.5px;">ENTERPRISE GOVERNANCE</span>
          <span class="badge" style="background:rgba(255,255,255,0.03); color:var(--text-light); padding:0.5rem 1rem; font-size:0.8rem; border:1px solid rgba(255,255,255,0.1); border-radius:20px; font-weight:400; letter-spacing:0.5px;">INTERACTIVE PLOTLY JS</span>
        </div>
      </div>
    </div>
  `;
}
