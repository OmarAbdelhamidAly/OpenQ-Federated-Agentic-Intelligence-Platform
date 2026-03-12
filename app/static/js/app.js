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

function getPremiumPlotlyLayout(title) {
  return {
    title: title ? { text: title, font: { family: 'Outfit', size: 18, color: '#fff' } } : null,
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter', color: '#94a3b8' },
    margin: { t: 40, r: 20, l: 40, b: 40 },
    xaxis: { 
      gridcolor: 'rgba(255,255,255,0.05)', 
      linecolor: 'rgba(255,255,255,0.1)',
      zeroline: false
    },
    yaxis: { 
      gridcolor: 'rgba(255,255,255,0.05)', 
      linecolor: 'rgba(255,255,255,0.1)',
      zeroline: false
    },
    hovermode: 'closest',
    showlegend: true,
    legend: { font: { size: 11 } }
  };
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
          <div class="logo-icon glass">🧠</div>
          <h1>DataAnalyst.AI</h1>
          <p style="color:var(--text-dim); font-weight:500;">Premium Autonomous Analytics</p>
        </div>
        <div class="auth-tabs">
          <button class="auth-tab active" data-tab="login" id="tab-login">Sign In</button>
          <button class="auth-tab" data-tab="register" id="tab-register">Get Started</button>
        </div>
        <div id="auth-form-login">
          <div class="form-group">
            <label class="form-label">Work Email</label>
            <input type="email" class="form-input" id="login-email" placeholder="name@company.com" autofocus>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" class="form-input" id="login-password" placeholder="••••••••">
          </div>
          <button class="btn btn-primary btn-full shadow-lg" id="btn-login" style="margin-top:1rem;">Sign In</button>
        </div>
        <div id="auth-form-register" class="hidden">
          <div class="form-group">
            <label class="form-label">Organization Name</label>
            <input type="text" class="form-input" id="reg-tenant" placeholder="Acme Global">
          </div>
          <div class="form-group">
            <label class="form-label">Work Email</label>
            <input type="email" class="form-input" id="reg-email" placeholder="name@company.com">
          </div>
          <div class="form-group">
            <label class="form-label">Secure Password</label>
            <input type="password" class="form-input" id="reg-password" placeholder="Min. 8 characters">
          </div>
          <button class="btn btn-primary btn-full shadow-lg" id="btn-register" style="margin-top:1rem;">Create Enterprise Account</button>
        </div>
      </div>
    </div>
  `;
  // ... (rest of logic stays same)
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
          <div class="sidebar-brand-icon">
             <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><path d="M12 2a5 5 0 0 0-5 5v2a5 5 0 0 0-2 4.41V16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2.59A5 5 0 0 0 17 9V7a5 5 0 0 0-5-5z"/></svg>
          </div>
          <span class="sidebar-brand-text">DataAnalyst.AI</span>
        </div>
        <nav class="sidebar-nav">
          <div class="nav-section">Intelligence</div>
          <button class="nav-item active" data-page="dashboard" onclick="navigate('dashboard')">
            <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></span> Insight Hub
          </button>
          <button class="nav-item" data-page="analysis" onclick="navigate('analysis')">
            <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span> Deep Research
          </button>
          <div class="nav-section">Data Assets</div>
          <button class="nav-item" data-page="data-sources" onclick="navigate('data-sources')">
            <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34-9-3V5"/></svg></span> Data Inventory
          </button>
          <button class="nav-item" data-page="enrichment" onclick="navigate('enrichment')">
            <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg></span> Knowledge Base
          </button>
          ${isAdmin ? `
          <div class="nav-section">Enterprise</div>
          <button class="nav-item" data-page="users" onclick="navigate('users')">
            <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></span> Team Management
          </button>
          ` : ''}
        </nav>
        <div class="sidebar-user glass" style="margin: 1rem; border-radius: 16px; padding: 1rem;">
          <div style="display:flex; align-items:center; gap:0.75rem;">
            <div class="sidebar-avatar" style="background:var(--grad-primary); color:white;">${initials}</div>
            <div class="sidebar-user-info">
              <div class="sidebar-user-name" style="font-weight:700; color:white;">${user.email.split('@')[0]}</div>
              <div class="sidebar-user-role" style="font-size:0.7rem; color:var(--accent-indigo); font-weight:800;">PRO MEMBER</div>
            </div>
          </div>
          <button class="btn-icon" onclick="logout()" title="Secure Exit" style="margin-left:auto; background:rgba(255,255,255,0.05); border:none; color:var(--text-dim);">
             <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Executive Overview</h1>
          <p class="page-subtitle">Platform health and intelligence across all analytical streams</p>
        </div>
      </div>

      <!-- Premium Stats Grid -->
      <div class="stats-grid" id="stats-grid">
        <div class="stat-card glass-card animate-up stagger-1">
          <div class="stat-label">Active Data Assets</div>
          <div class="stat-value tabular" id="stat-sources">—</div>
        </div>
        <div class="stat-card glass-card animate-up stagger-2">
          <div class="stat-label">Analytic Job Cycles</div>
          <div class="stat-value tabular" id="stat-analyses">—</div>
        </div>
        <div class="stat-card glass-card animate-up stagger-3">
          <div class="stat-label">System Fidelity</div>
          <div class="stat-value tabular" id="stat-success">—</div>
        </div>
        <div class="stat-card glass-card animate-up stagger-4" style="border-right:none;">
          <div class="stat-label">Authorized Personnel</div>
          <div class="stat-value tabular" id="stat-users">—</div>
        </div>
      </div>

      <div class="dashboard-main-split">
        <div class="dashboard-card">
          <div class="dashboard-card-header">
            <h3 class="dashboard-card-title">Recent Autonomous Activity</h3>
          </div>
          <div id="recent-analyses" style="min-height:380px;">
            <div class="empty-state" style="padding:6rem 2rem;">
              <div style="font-size:3rem; margin-bottom:1.5rem; opacity:0.3;">📡</div>
              <h3 style="font-family:var(--font-display);">Awaiting Stream Activity</h3>
              <p style="color:var(--text-dim);">Initiate an analysis to populate your intelligence feed.</p>
            </div>
          </div>
        </div>
        
        <div class="dashboard-section">
          <div class="dashboard-card" style="background:var(--grad-primary); border:none; padding:2.5rem; position:relative; overflow:hidden;">
            <div style="position:absolute; top:-20px; right:-20px; font-size:10rem; opacity:0.12; color:#fff;">✨</div>
            <h3 style="color:#fff; font-family:var(--font-display); margin-bottom:1rem; font-size:1.6rem; font-weight:700;">Accelerate Research</h3>
            <p style="color:rgba(255,255,255,0.8); font-size:1rem; margin-bottom:2.5rem; line-height:1.7;">Leverage multi-source AI to extract patterns and anomalies in seconds.</p>
            <button class="btn glass" onclick="navigate('analysis')" style="background:rgba(255,255,255,0.2); color:#fff; border:1px solid rgba(255,255,255,0.4); font-weight:700; width:100%; height:54px; font-size:1rem; border-radius:14px;">
              Initiate Strategic Inquiry
            </button>
          </div>

          <div class="dashboard-card">
            <div class="dashboard-card-header">
              <h3 class="dashboard-card-title">Quick Actions</h3>
            </div>
            <div class="dashboard-card-body" style="display:flex; flex-direction:column; gap:1.25rem;">
              <button class="btn glass" onclick="navigate('data-sources')" style="justify-content:flex-start; height:56px; width:100%; padding: 0 1.5rem; border-radius:12px; font-weight:600;">
                 <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:1rem; color:var(--accent-indigo);"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34-9-3V5"/></svg>
                 Audit Data Inventory
              </button>
              ${getUser()?.role === 'admin' ? `
              <button class="btn glass" onclick="navigate('users')" style="justify-content:flex-start; height:56px; width:100%; padding: 0 1.5rem; border-radius:12px; font-weight:600;">
                 <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:1rem; color:var(--accent-cyan);"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                 Identity & Access Control
              </button>` : ''}
            </div>
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
          <div class="table-wrapper" style="border:none; padding:1rem 0;">
            <table class="data-table">
              <thead><tr><th style="padding-left:2rem;">Intelligence Stream</th><th>Status</th><th style="padding-right:2rem; text-align:right;">Date</th></tr></thead>
              <tbody>${recent.map(j => `
                <tr>
                  <td style="padding-left:2rem; font-weight:600; color:#fff;">
                    ${j.question?.substring(0, 60) || '—'}${j.question?.length > 60 ? '...' : ''}
                  </td>
                  <td>
                    <span class="badge ${j.status === 'done' ? 'badge-success' : j.status === 'error' ? 'badge-error' : 'badge-warning'}" style="border-radius:6px;">
                      ${j.status === 'awaiting_approval' ? 'PENDING REVIEW' : j.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td style="text-align:right; padding-right:2rem; font-size:0.85rem; color:var(--text-dim);">${new Date(j.created_at || Date.now()).toLocaleDateString()}</td>
                </tr>
              `).join('')}</tbody>
            </table>
          </div>`;
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Enterprise Assets</h1>
          <p class="page-subtitle">Inventory of connected intelligence streams and research repositories</p>
        </div>
        ${isAdmin ? `
        <div style="display:flex; gap:0.75rem;">
          <button class="btn glass" onclick="showSQLModal()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34-9-3V5"/><ellipse cx="12" cy="5" rx="9" ry="3"/></svg>
            Connect SQL
          </button>
          <button class="btn btn-primary shadow-lg" onclick="document.getElementById('file-input').click()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Upload Asset
          </button>
          <input type="file" id="file-input" accept=".csv,.xlsx,.sqlite,.db,.sql" class="hidden" />
        </div>` : ''}
      </div>

      ${isAdmin ? `
      <div class="dashboard-card" style="margin-bottom:3rem; border-style:dashed; border-width:2px; background:rgba(255,255,255,0.01);">
        <div class="dashboard-card-body">
          <div class="upload-zone" id="upload-zone" style="border:none; background:transparent; padding:3rem 0; text-align:center;">
            <div class="upload-icon" style="font-size:3.5rem; margin-bottom:1.5rem; filter: drop-shadow(0 0 15px rgba(99, 102, 241, 0.4));">📂</div>
            <div class="upload-text" style="font-size:1.2rem; font-weight:600; color:var(--text-main);">
              Drag & drop analytical files here
              <div style="font-size:0.85rem; color:var(--text-dim); margin-top:0.4rem; font-weight:400;">Supports CSV, Excel, and SQLite databases</div>
            </div>
          </div>
          
          <div class="upload-status-card glass" id="upload-status-card" style="display:none; margin:2rem auto 0; max-width:500px; padding:1.5rem; border-radius:16px; border:1px solid var(--accent-indigo);">
            <div style="display:flex; justify-content:space-between; margin-bottom:1rem; align-items:center;">
              <span id="upload-filename" style="font-weight:700; color:#fff;">Syncing...</span>
              <span id="upload-percentage" class="badge badge-primary">0%</span>
            </div>
            <div class="progress-container" style="height:8px; background:rgba(255,255,255,0.05);"><div class="progress-bar" id="upload-progress-bar"></div></div>
          </div>
        </div>
      </div>` : ''}

      <div class="dashboard-section">
        <div class="section-title">
           <span style="background:var(--grad-primary); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:800;">🛰️ Active Data Streams</span>
        </div>
        <div id="sources-list" class="source-list" style="display:flex; flex-direction:column; gap:1rem;">
          <div style="text-align:center; padding:5rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>

      <!-- SQL Modal -->
      <div class="modal-overlay" id="sql-modal">
        <div class="modal">
          <div class="modal-header">
            <h3 class="modal-title">Connect Relational Engine</h3>
            <button class="btn-icon" onclick="closeSQLModal()">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-group"><label class="form-label">Instance Alias</label><input class="form-input" id="sql-name" placeholder="e.g. Analytics Data Lake" /></div>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1.5rem;">
                <div class="form-group">
                  <label class="form-label">Engine Architecture</label>
                  <select class="form-select" id="sql-engine">
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="mssql">MS SQL Server</option>
                  </select>
                </div>
                <div class="form-group"><label class="form-label">Database Identity</label><input class="form-input" id="sql-database" placeholder="analytics_prod" /></div>
            </div>

            <div style="display:grid; grid-template-columns: 2fr 1fr; gap:1.5rem;">
                <div class="form-group"><label class="form-label">Host / Vector Node</label><input class="form-input tabular" id="sql-host" placeholder="db.enterprise.com" /></div>
                <div class="form-group"><label class="form-label">Service Port</label><input class="form-input tabular" type="number" id="sql-port" value="5432" /></div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1.5rem;">
                <div class="form-group"><label class="form-label">Access Principal</label><input class="form-input" id="sql-username" placeholder="svc_analyst" /></div>
                <div class="form-group"><label class="form-label">Security Token</label><input class="form-input" type="password" id="sql-password" /></div>
            </div>

            <div style="background:rgba(245,158,11,0.05); padding:1.25rem; border-radius:12px; border:1px solid rgba(245,158,11,0.2); margin-top:1.5rem;">
              <p style="font-size:0.8rem; color:var(--warning); margin:0; line-height:1.6;"><strong>Governance Note:</strong> Ensure the service account has READ-ONLY privileges to maintain data sovereignty during autonomous analysis.</p>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary glass" onclick="closeSQLModal()">Cancel</button>
            <button class="btn btn-primary" id="btn-connect-sql">Initialize Connection</button>
          </div>
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
    list.innerHTML = data.data_sources.map((s, i) => {
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
        <div class="source-item glass-card animate-up stagger-${(i % 4) + 1}" style="display:flex; align-items:center; padding:1.5rem; margin-bottom:1rem; gap:1.5rem;">
          <div class="source-icon ${s.type}" style="width:48px; height:48px; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:1.5rem;">
            ${s.type === 'csv' ? '📄' : '🗄️'}
          </div>
          <div class="source-info" style="flex:1;">
            <div class="source-name" style="font-weight:700; font-size:1.1rem; color:#fff; margin-bottom:0.25rem;">${s.name}</div>
            <div class="source-meta" style="font-size:0.85rem; color:var(--text-dim); font-weight:500;"> ${s.type.toUpperCase()} • ${meta}</div>
          </div>
          <div class="source-status">
            <span class="badge ${s.auto_analysis_status === 'done' ? 'badge-success' : s.auto_analysis_status === 'failed' ? 'badge-error' : 'badge-warning'}" style="padding: 0.5rem 0.8rem; border-radius:8px;">
                ${statusIcon} <span style="margin-left:0.4rem;">${statusLabel || s.auto_analysis_status.toUpperCase()}</span>
            </span>
          </div>
          <div style="display:flex; gap:0.75rem; margin-left:1rem;">
            ${s.auto_analysis_status === 'done' ? `<button class="btn btn-sm btn-primary glass" onclick="openSourceDashboard('${s.id}')">View Metrics</button>` : ''}
            <button class="btn btn-sm btn-secondary glass" onclick="navigateToAnalysis('${s.id}')">Query AI</button>
            ${getUser()?.role === 'admin' ? `<button class="btn btn-sm" style="color:var(--error); border:1px solid rgba(239, 68, 68, 0.2); background:transparent;" onclick="deleteSource('${s.id}')">Delete</button>` : ''}
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Deep Research Engine</h1>
          <p class="page-subtitle">Autonomous multi-stream analysis for high-fidelity enterprise insights</p>
        </div>
      </div>

      <!-- Analysis Controller Card -->
      <div class="dashboard-card" style="margin-bottom:3rem; border-left: 4px solid var(--accent-indigo);">
        <div class="dashboard-card-body" style="padding:2.5rem;">
          <div style="display:grid; grid-template-columns: 1.2fr 1fr; gap: 3rem; margin-bottom: 2.5rem;">
              <div class="form-group">
                  <label class="form-label">Primary Intelligence Stream</label>
                  <select class="form-select glass" id="analysis-source" style="font-weight:600;"></select>
              </div>
              <div class="form-group">
                  <label class="form-label">Analytical Intensity</label>
                  <div class="pill-group glass" id="insight-count-pills" style="padding:4px; border-radius:12px; display:flex; background:rgba(255,255,255,0.02);">
                      <button class="pill-btn" data-value="1" style="flex:1;">Light</button>
                      <button class="pill-btn active" data-value="3" style="flex:1;">Balanced</button>
                      <button class="pill-btn" data-value="5" style="flex:1;">Deep Scan</button>
                  </div>
              </div>
          </div>
          
          <div class="form-group">
            <label class="form-label">Research Objective / Hypothesis</label>
            <textarea class="form-input glass" id="analysis-q" rows="4" style="resize:none; padding:1.5rem; font-size:1.1rem; line-height:1.6;"
              placeholder="e.g. Conduct a churn analysis for Q3 and correlate with recent pricing changes in EMEA regions...">${qText}</textarea>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; padding-top:2rem; border-top:1px solid var(--glass-border); margin-top:1rem;">
            <div style="font-size:0.85rem; color:var(--text-dim); font-weight:600; letter-spacing:0.02em;">
               <span id="insight-count-hint" style="opacity:0.8;">Orchestrating 3 parallel analytical workstreams</span>
            </div>
            <button class="btn btn-primary shadow-lg" id="btn-analyze" style="min-width:240px; height:52px; font-size:1rem; gap:0.75rem; font-weight:700;">
               <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m21 21-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z"/></svg>
               Initialize Research
            </button>
          </div>
        </div>
      </div>
      
      <div id="pbi-results-grid" style="display:none; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap:2rem; margin-bottom:4rem;">
      </div>
    </div>
  `;

  try {
    const data = await api.listDataSources();
    const select = document.getElementById('analysis-source');
    if (data.data_sources?.length) {
      select.innerHTML = data.data_sources.map(s => `< option value = "${s.id}" > ${s.name} (${s.type})</option > `).join('');
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
      payloads.push(api.post('/analysis/query', {
        source_id: sourceId, question: q, context_id: count > 1 ? `Insight ${i + 1}/${count}` : null
      }));
    }

    showToast(`Coordinating analytical resources for ${count} workstreams...`, 'info');
    const results = await Promise.all(payloads);
    btn.textContent = '🚀 Run Analysis';
    btn.disabled = false;

    // Create a panel for each job
      for (let i = 0; i < results.length; i++) {
        const jobId = results[i].job_id;
        const panelHtml = `
            <div class="pbi-panel glass-card" id="pbi-panel-${jobId}" style="border-radius:24px; padding:2rem;">
              <div class="pbi-panel-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
                <span class="pbi-panel-title" style="font-family:var(--font-display); font-weight:700; color:var(--accent-indigo);">RESEARCH STREAM ${i + 1}</span>
                <span class="pbi-panel-status badge badge-primary" id="pbi-status-${jobId}" style="border-radius:8px;">Initializing Stream...</span>
              </div>
              <div class="pbi-panel-chart glass" id="pbi-chart-${jobId}" style="min-height:300px; border-radius:16px; margin-bottom:1.5rem; display:flex; align-items:center; justify-content:center;">
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
        } else if (s === 'reflection') {
          statusEl.className = 'pbi-panel-status badge badge-info';
          statusEl.innerHTML = '<span class="pulse-loader"><span class="pulse-dot"></span><span class="pulse-dot"></span><span class="pulse-dot"></span></span> Introspecting...';
        } else if (s === 'data_discovery') {
          statusEl.className = 'pbi-panel-status badge badge-info';
          statusEl.textContent = 'Exploring Patterns...';
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

  if (statusEl) { statusEl.className = 'pbi-panel-status badge badge-warning'; statusEl.textContent = 'Awaiting Review'; }
  if (panelEl) panelEl.style.borderColor = 'var(--warning)';

  if (chartEl) {
    chartEl.innerHTML = `
      <div style="padding:1rem; height:100%; display:flex; flex-direction:column;">
        <h4 style="color:var(--warning); margin-bottom:0.5rem; display:flex; align-items:center; gap:0.5rem;">⚠️ Strategic Signal Required</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-bottom:0.75rem;"><strong>AI Reasoning:</strong> ${intent || 'To securely fetch your data.'}</p>
        <div style="background:rgba(0,0,0,0.3); padding:0.75rem; border-radius:6px; flex:1; overflow-y:auto; overflow-x:auto; margin-bottom:1rem; border:1px solid rgba(255,255,255,0.05);">
          <code style="color:#60A5FA; font-size:0.8rem; white-space:pre;">${sql || 'SELECT * FROM ...'}</code>
        </div>
        <div style="display:flex; gap:0.75rem; justify-content:flex-end;">
          <button class="btn btn-sm btn-secondary" onclick="cancelJob('${jobId}')" style="color:var(--error); border-color:var(--error);">Cancel Task</button>
          <button class="btn btn-sm btn-primary" onclick="approveJob('${jobId}')" style="background:var(--success); border-color:var(--success);">✓ Validate & Execute</button>
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

  if (statusEl) {
    statusEl.className = 'pbi-panel-status badge badge-success';
    statusEl.textContent = '✓ Ready';
    if (result.reflection_count > 0) {
      statusEl.innerHTML += ' <span style="font-size:0.7rem; opacity:0.8; margin-left:0.4rem; font-weight:500;">(Auto-Adjusted)</span>';
    }
  }
  if (panelEl) panelEl.classList.add('done');

  // Render chart
  if (chartEl && result.chart_json) {
    try {
      const Plotly = await loadPlotly();
      chartEl.innerHTML = '';
      const layout = getPremiumPlotlyLayout(result.chart_json.layout?.title?.text);
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Identity & Access</h1>
          <p class="page-subtitle">Governance of organization-level permissions and collaborative access control</p>
        </div>
        <button class="btn btn-primary shadow-lg" onclick="showInviteModal()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:0.5rem;"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
          Invite Principal
        </button>
      </div>

      <div class="dashboard-card">
        <div class="dashboard-card-header">
          <h3 class="dashboard-card-title">Authorized Personnel</h3>
          <span class="badge glass" style="font-size:0.75rem; border-color:rgba(255,255,255,0.05);">ACCESS CONTROL LIST</span>
        </div>
        <div class="dashboard-card-body" id="users-list" style="padding:2rem;">
          <div style="text-align:center;padding:5rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>

      <!-- Invite Modal -->
      <div class="modal-overlay" id="invite-modal">
        <div class="modal">
          <div class="modal-header">
            <h3 class="modal-title">Authorize New Principal</h3>
            <button class="btn-icon" onclick="closeInviteModal()">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-group"><label class="form-label">Corporate Email</label><input class="form-input" id="invite-email" placeholder="principal@enterprise.ai" /></div>
            <div class="form-group"><label class="form-label">Temporal Access Token</label><input class="form-input" type="password" id="invite-password" placeholder="System security key" /></div>
            <div class="form-group">
              <label class="form-label">Privilege Level</label>
              <select class="form-select" id="invite-role">
                <option value="viewer">Analyst (Viewer)</option>
                <option value="admin">Governor (Administrator)</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary glass" onclick="closeInviteModal()">Cancel</button>
            <button class="btn btn-primary" id="btn-invite">Dispatch Invitation</button>
          </div>
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
    list.innerHTML = data.users.map((u, i) => `
      <div class="user-item glass-card animate-up stagger-${(i % 4) + 1}" style="display:flex; align-items:center; padding:1.5rem; margin-bottom:1rem; gap:1.5rem;">
        <div class="sidebar-avatar" style="width:48px; height:48px; flex-shrink:0; background:var(--grad-primary); color:white; font-weight:700;">${u.email.substring(0, 2).toUpperCase()}</div>
        <div class="source-info" style="flex:1;">
          <div class="source-name" style="font-weight:700; color:#fff; font-size:1.1rem;">${u.email}</div>
          <div class="source-meta" style="font-size:0.85rem; color:var(--text-dim); font-weight:500;">
             Corporate Identity • Joined ${new Date(u.created_at).toLocaleDateString()}
          </div>
        </div>
        <span class="badge ${u.role === 'admin' ? 'badge-info' : 'badge-success'}" style="padding:0.5rem 1rem; border-radius:8px;">${u.role.toUpperCase()}</span>
        ${u.id !== getUser()?.id ? `<button class="btn btn-sm btn-secondary glass" style="color:var(--error); border-color:rgba(239, 68, 68, 0.2);" onclick="removeUser('${u.id}')">Revoke Access</button>` : ''}
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

// ── Access Revocation ──────────────────────────────────
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


// ══════════════════════════════════════════════════════
// ── SOURCE DASHBOARD (CSV & SQL) ──────────────────────
// ══════════════════════════════════════════════════════

async function renderSourceDashboard(container) {
  const sourceId = window._dashboardSourceId;
  if (!sourceId) { navigate('data-sources'); return; }

  // Loading state
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Executive Insight Hub</h1>
        <p class="page-subtitle">Auto-generated specialized intelligence dashboards</p>
      </div>
      <button class="btn btn-secondary glass" onclick="navigate('data-sources')">← Back to Assets</button>
    </div>
    <div class="glass-card" style="padding:5rem 2rem; text-align:center;">
      <div class="spinner" style="width:48px; height:48px; margin:0 auto 2rem;"></div>
      <h3 style="font-family:var(--font-display);">Initializing Data Synthesis...</h3>
      <p style="color:var(--text-dim);">Please wait while the AI identifies business patterns.</p>
    </div>
  `;

  try {
    let source = await api.getDashboard(sourceId);

    // If still running, poll and show spinner
    if (source.auto_analysis_status === 'running' || source.auto_analysis_status === 'pending') {
      container.innerHTML = `
        <div class="page-header">
          <div>
            <h1 class="page-title">Executive Insight Hub</h1>
            <p class="page-subtitle">Synthesizing autonomous reasoning for your data assets</p>
          </div>
          <button class="btn btn-secondary glass" onclick="navigate('data-sources')">← Back</button>
        </div>
        <div class="glass-card" style="padding:5rem 2rem; text-align:center;">
          <div class="spinner" style="width:56px; height:56px; margin:0 auto 2.5rem; border-width:4px;"></div>
          <h2 style="font-family:var(--font-display); margin-bottom:1rem;">Autonomous Reasoning in Progress...</h2>
          <p style="color:var(--text-dim); max-width:500px; margin:0 auto 3rem;">The agent is traversing your data to generate a multi-dimensional intelligence report. This typically concludes within 45 seconds.</p>
          <div class="analysis-progress" style="max-width:500px; margin:0 auto;">
            <div class="progress-container" style="display:block; height:10px; background:rgba(255,255,255,0.05);"><div class="progress-bar" id="progress-fill" style="box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);"></div></div>
            <div id="progress-label" style="margin-top:1.5rem; font-size:0.9rem; font-weight:700; color:var(--accent-indigo); text-transform:uppercase; letter-spacing:0.1em; animation: pulse 2s infinite;">Introspecting Schema...</div>
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

  container.innerHTML = `
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Resource Analysis</h1>
          <p class="page-subtitle" style="display:flex; align-items:center; gap:0.5rem;">
            <span style="color:#fff; font-weight:600;">${source.name}</span> 
            <span style="opacity:0.5;">•</span> 
            <span class="badge badge-info" style="text-transform:nowrap; border-radius:6px;">${domain.toUpperCase()} INTELLIGENCE</span>
          </p>
        </div>
        <div style="display:flex; gap:0.75rem;">
          <button class="btn btn-primary shadow-lg" onclick="navigateToAnalysis('${source.id}')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            New Analysis
          </button>
          <button class="btn glass" onclick="navigate('data-sources')" style="border-radius:10px;">← Back to Assets</button>
        </div>
      </div>

      <!-- Premium Stats Grid -->
      <div class="stats-grid">
        <div class="stat-card glass-card">
          <div class="stat-label">Inventory Size</div>
          <div class="stat-value tabular">${(schema.row_count || 0).toLocaleString()} <span style="font-size:0.85rem; font-weight:500; color:var(--text-dim); letter-spacing:0;">Records</span></div>
        </div>
        <div class="stat-card glass-card">
          <div class="stat-label">Schema Breadth</div>
          <div class="stat-value tabular">${schema.column_count || 0} <span style="font-size:0.85rem; font-weight:500; color:var(--text-dim); letter-spacing:0;">Variables</span></div>
        </div>
        <div class="stat-card glass-card">
          <div class="stat-label">Analytical Scope</div>
          <div class="stat-value tabular">${numCols.length} <span style="font-size:0.85rem; font-weight:500; color:var(--text-dim); letter-spacing:0;">Metrics</span></div>
        </div>
        <div class="stat-card glass-card" style="border-right: none; position:relative; overflow:hidden;">
          <div style="position:absolute; top:-10px; right:-10px; padding:1.5rem; opacity:0.1; font-size:5rem; color:var(--accent-cyan);">⚡</div>
          <div class="stat-label">Intelligence Health</div>
          <div class="stat-value tabular" style="color:var(--accent-cyan);">${Math.round((source.auto_analysis_json?.quality_score || 0.95) * 100)}%</div>
        </div>
      </div>

      <!-- Column profile -->
      <div class="dashboard-card">
        <div class="dashboard-card-header">
          <h3 class="dashboard-card-title">Structural intelligence Profile</h3>
          <span class="badge glass" style="font-size:0.75rem; border-color:rgba(255,255,255,0.05);">PRIMARY SCHEMA</span>
        </div>
        <div style="overflow-x:auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th style="padding-left:2.5rem;">IDENTITY</th>
                <th>DATA PROTOCOL</th>
                <th style="padding-right:2.5rem;">SAMPLE OBSERVATIONS</th>
              </tr>
            </thead>
            <tbody>
              ${cols.slice(0, 10).map(c => `
                <tr>
                  <td style="font-weight:700; color:#fff; padding-left:2.5rem;">${c.name}</td>
                  <td>
                    <span class="badge ${numCols.find(n => n.name === c.name) ? 'badge-info' : 'badge-neutral'}" style="border-radius:6px; font-weight:700; font-size:0.7rem;">
                      ${c.dtype.toUpperCase()}
                    </span>
                  </td>
                  <td class="tabular" style="color:var(--text-dim); font-size:0.9rem; padding-right:2.5rem;">
                    ${(c.sample_values || []).slice(0, 3).join(', ') || '—'}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- AI Insights grid -->
      <div class="dashboard-section">
        <div class="section-title" style="font-family:var(--font-display); font-size:1.4rem; display:flex; align-items:center; gap:1rem; margin:0;">
           <span style="background:var(--grad-primary); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:800;">🤖 Autonomous Synthesis</span>
           <span style="font-size:0.85rem; color:var(--text-dim); font-weight:500; opacity:0.6; letter-spacing:0.05em;">• ${results.length} STREAMS ACTIVE</span>
        </div>
        <div class="insight-grid" id="insights-grid"></div>
      </div>
    </div>
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Relational Intelligence</h1>
          <p class="page-subtitle" style="display:flex; align-items:center; gap:0.5rem;">
            <span style="color:#fff; font-weight:600;">${source.name}</span> 
            <span style="opacity:0.5;">•</span> 
            <span class="badge badge-success" style="text-transform:nowrap; border-radius:6px;">${domain.toUpperCase()} CLUSTER</span>
          </p>
        </div>
        <div style="display:flex; gap:0.75rem;">
          <button class="btn btn-primary" onclick="navigateToAnalysis('${source.id}')" style="box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:0.5rem;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            New Query
          </button>
          <button class="btn glass" onclick="navigate('data-sources')" style="border-radius:10px;">← Back</button>
        </div>
      </div>

      <!-- Premium Stats Grid -->
      <div class="stats-grid">
        <div class="stat-card glass-card">
          <div class="stat-label">Schema Depth</div>
          <div class="stat-value tabular">${schema.table_count || tables.length} <span style="font-size:0.85rem; font-weight:500; color:var(--text-dim); letter-spacing:0;">Tables</span></div>
        </div>
        <div class="stat-card glass-card">
          <div class="stat-label">Relational Scope</div>
          <div class="stat-value tabular">${schema.total_columns || '—'} <span style="font-size:0.85rem; font-weight:500; color:var(--text-dim); letter-spacing:0;">Attributes</span></div>
        </div>
        <div class="stat-card glass-card">
          <div class="stat-label">System Protocol</div>
          <div class="stat-value tabular" style="color:var(--accent-cyan); font-size:1.6rem; font-weight:800;">${(schema.dialect || schema.source_type || 'SQL').toUpperCase()}</div>
        </div>
        <div class="stat-card glass-card" style="border-right:none; position:relative; overflow:hidden;">
           <div style="position:absolute; top:-10px; right:-10px; padding:1.5rem; opacity:0.1; font-size:5rem; color:var(--accent-violet);">🗄️</div>
           <div class="stat-label">Autonomous Fidelity</div>
           <div class="stat-value tabular" style="color:var(--success);">${results.filter(r => r.status === 'done').length}/${results.length || 5}</div>
        </div>
      </div>

      <!-- Schema explorer -->
      ${tables.length > 0 ? `
      <div class="dashboard-card" style="margin-bottom:0;">
        <div class="dashboard-card-header">
          <h3 class="dashboard-card-title">Relational Architecture Map</h3>
          <span class="badge glass" style="font-size:0.75rem; border-color:rgba(255,255,255,0.05);">PHYSICAL SCHEMA</span>
        </div>
        <div class="dashboard-card-body" style="padding:2rem;">
          <div class="tables-grid" style="display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:1.5rem;">
            ${tables.map(t => `
              <div class="table-card glass" style="border-radius:16px; padding:1.75rem; transition:var(--transition); cursor:default; background:rgba(255,255,255,0.01);">
                <div class="table-card-name" style="font-weight:700; color:#fff; font-size:1.15rem; margin-bottom:0.5rem; display:flex; align-items:center; gap:0.75rem;">
                   <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-indigo)" stroke-width="2.5"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
                   ${t.table}
                </div>
                <div class="table-card-meta tabular" style="font-size:0.85rem; color:var(--text-dim); font-weight:500; margin-bottom:1.25rem;">
                  ${t.column_count} ATTRIBUTES ${t.row_count != null ? ' • ' + Number(t.row_count).toLocaleString() + ' RECORDS' : ''}
                </div>
                <div class="table-card-cols" style="display:flex; flex-wrap:wrap; gap:0.5rem;">
                  ${(t.columns || []).slice(0, 4).map(c => `<span class="badge badge-neutral" style="font-size:0.7rem; padding:0.25rem 0.6rem; text-transform:none; border-radius:4px; font-weight:600; background:rgba(255,255,255,0.05);">${c.name}</span>`).join('')}
                  ${t.columns?.length > 4 ? `<span class="badge badge-neutral" style="font-size:0.7rem; padding:0.25rem 0.6rem; opacity:0.5; background:transparent;">+${t.columns.length - 4}</span>` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>` : ''}

      <!-- AI Insights grid -->
      <div class="dashboard-section">
        <div class="section-title" style="font-family:var(--font-display); font-size:1.4rem; display:flex; align-items:center; gap:1rem; margin:0;">
           <span style="background:var(--grad-primary); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:800;">🤖 Relational Insights</span>
           <span style="font-size:0.85rem; color:var(--text-dim); font-weight:500; opacity:0.6; letter-spacing:0.05em;">• ${results.length} STREAMS ACTIVE</span>
        </div>
        <div class="insight-grid" id="insights-grid"></div>
      </div>
    </div>
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
    card.className = 'insight-card glass-card';
    card.style.animationDelay = `${i * 0.12}s`;
    card.style.padding = '2rem';
    card.style.borderRadius = '20px';

    const statusBadge = r.status === 'done'
      ? `<span class="badge badge-success" style="border-radius:6px; padding:0.3rem 0.6rem;">✓ Done</span>`
      : `<span class="badge badge-error" style="border-radius:6px; padding:0.3rem 0.6rem;">⚠ Failed</span>`;

    card.innerHTML = `
      <div class="insight-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
        <span class="insight-index" style="font-weight:800; color:var(--accent-indigo); opacity:0.8; font-family:var(--font-display);">INSIGHT #${i + 1}</span>
        ${statusBadge}
      </div>
      <div class="insight-question" style="font-size:1.2rem; font-weight:700; color:#fff; margin-bottom:1.5rem; line-height:1.4;">"${r.question}"</div>
      ${r.status === 'done' ? `
        <div class="insight-summary" style="font-size:0.95rem; line-height:1.7; color:var(--text-dim); margin-bottom:2rem; background:rgba(255,255,255,0.02); padding:1.25rem; border-radius:12px; border:1px solid var(--glass-border);">${r.executive_summary || ''}</div>
        ${r.chart_json ? `<div class="insight-chart glass" id="chart-${sourceId}-${i}" style="min-height:280px; border-radius:12px; margin-bottom:2rem;"></div>` : ''}
        <div class="insight-footer" style="padding-top:1.5rem; border-top:1px solid var(--glass-border);">
          <button class="btn btn-sm btn-secondary glass" style="width:100%; justify-content:center; gap:0.5rem;" 
            onclick="navigateToAnalysisWithQ('${sourceId}', ${JSON.stringify(r.question).replace(/"/g, '&quot;')})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            Refine Analysis
          </button>
        </div>
      ` : `<div style="color:var(--error); font-weight:600; padding:1.5rem; background:rgba(239, 68, 68, 0.05); border-radius:12px; border:1px solid rgba(239, 68, 68, 0.2);">${r.error || 'Analysis cycle failed'}</div>`}
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Semantic Intelligence</h1>
          <p class="page-subtitle">Standardized metric definitions to unify analytical reasoning across the enterprise</p>
        </div>
        ${isAdmin ? `<button class="btn btn-primary shadow-lg" onclick="showMetricModal()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:0.5rem;"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          Define Business Logic
        </button>` : ''}
      </div>

      <div class="dashboard-card">
        <div class="dashboard-card-header">
          <h3 class="dashboard-card-title">Corporate Metric Dictionary</h3>
          <span class="badge glass" style="font-size:0.75rem; border-color:rgba(255,255,255,0.05);">SYNTACTIC DEFINITIONS</span>
        </div>
        <div class="dashboard-card-body" id="metrics-list" style="padding:0;">
          <div style="text-align:center;padding:5rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>

      <!-- Metric Modal -->
      <div class="modal-overlay" id="metric-modal">
        <div class="modal">
          <div class="modal-header">
            <h3 class="modal-title">Define Strategic Metric</h3>
            <button class="btn-icon" onclick="closeMetricModal()">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-group"><label class="form-label">Metric Identifier</label><input class="form-input" id="metric-name" placeholder="e.g. Net Enterprise Value" /></div>
            <div class="form-group"><label class="form-label">Semantic Logic Definition</label><textarea class="form-input" id="metric-def" rows="3" placeholder="Explain the business context and calculation priority..."></textarea></div>
            <div class="form-group"><label class="form-label">Computational Formula</label><input class="form-input tabular" id="metric-formula" placeholder="e.g. (TotalRev - Churn) / AcquisitionCost" /></div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary glass" onclick="closeMetricModal()">Cancel</button>
            <button class="btn btn-primary" id="btn-save-metric">Register Metric</button>
          </div>
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
      <div class="table-wrapper" style="border:none; background:transparent;">
        <table class="data-table">
          <thead><tr><th style="padding-left:2rem;">Metric Property</th><th>Calculation Intent</th><th style="text-align:center;">Semantic Formula</th><th style="padding-right:2rem; text-align:right;">Control</th></tr></thead>
          <tbody>${data.metrics.map(m => `
            <tr>
              <td style="font-weight:700; color:#fff; padding-left:2rem;">${m.name}</td>
              <td style="max-width:350px; white-space:normal; font-size:0.9rem; color:var(--text-dim); line-height:1.6;">${m.definition}</td>
              <td style="text-align:center;"><code style="background:rgba(99, 102, 241, 0.1); color:var(--accent-indigo); padding:0.4rem 0.75rem; border-radius:8px; font-size:0.85rem; border:1px solid rgba(99, 102, 241, 0.15); font-family:'SF Mono', monospace;">${m.formula || 'DYNAMIC'}</code></td>
              <td style="text-align:right; padding-right:2rem;">
                ${getUser()?.role === 'admin' ? `<button class="btn btn-sm glass" style="color:var(--error); border-color:rgba(239, 68, 68, 0.2);" onclick="handleMetricDelete('${m.id}')">Delete</button>` : '—'}
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Knowledge Repositories</h1>
          <p class="page-subtitle">Index and orchestrate enterprise documentation for advanced RAG contextualization</p>
        </div>
        ${isAdmin ? `<button class="btn btn-primary shadow-lg" onclick="showKBModal()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:0.5rem;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
          New Collection
        </button>` : ''}
      </div>

      <div class="dashboard-section">
        <div class="insight-grid" id="kb-list">
          <div style="grid-column: 1 / -1; text-align:center; padding:5rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
      </div>

      <!-- KB Modal -->
      <div class="modal-overlay" id="kb-modal">
        <div class="modal">
          <div class="modal-header">
            <h3 class="modal-title">Initialize Knowledge Cluster</h3>
            <button class="btn-icon" onclick="closeKBModal()">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-group"><label class="form-label">Collection Identity</label><input class="form-input" id="kb-name" placeholder="e.g. Compliance Control Framework" /></div>
            <div class="form-group"><label class="form-label">Strategic Intent</label><textarea class="form-input" id="kb-desc" rows="3" placeholder="Define boundaries and dataset utility..."></textarea></div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary glass" onclick="closeKBModal()">Cancel</button>
            <button class="btn btn-primary" id="btn-save-kb">Initialize Collection</button>
          </div>
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
    list.innerHTML = data.knowledge_bases.map((kb, i) => `
      <div class="glass-card kb-card animate-up stagger-${(i % 4) + 1}" onclick="navigate('kb-detail', { id: '${kb.id}', name: '${kb.name}' })" style="cursor:pointer; transition:var(--transition); border-left: 4px solid var(--accent-indigo); padding:2.5rem; display:flex; flex-direction:column; gap:1.5rem;">
        <div style="width:56px; height:56px; background:rgba(99, 102, 241, 0.1); border:1px solid rgba(99, 102, 241, 0.2); border-radius:16px; display:flex; align-items:center; justify-content:center; font-size:1.8rem;">📂</div>
        <div>
          <h3 style="margin:0 0 0.75rem 0; font-family:var(--font-display); color:#fff; font-weight:700; font-size:1.4rem;">${kb.name}</h3>
          <p style="font-size:0.95rem; color:var(--text-dim); margin:0; line-height:1.6; height:3.2rem; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">${kb.description || 'No specialized description provided.'}</p>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.85rem; padding-top:1.5rem; border-top:1px solid var(--glass-border); margin-top:auto;">
          <span class="badge badge-neutral" style="font-weight:700; color:var(--accent-indigo); border:none; padding:0;">${kb.document_count} DOCUMENTS</span>
          <span style="color:var(--accent-indigo); font-weight:800; font-size:0.75rem; letter-spacing:0.05em; display:flex; align-items:center; gap:0.4rem;">EXPLORE <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span>
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
            <button class="btn btn-icon glass sm" onclick="navigate('knowledge')" style="width:32px; height:32px; border-radius:8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <span style="color:var(--text-dim); font-weight:600; font-size:0.9rem; text-transform:uppercase; letter-spacing:0.05em;">Repositories</span>
          </div>
          <h1 class="page-title" style="display:flex; align-items:center; gap:0.75rem;">
            <span style="opacity:0.6;">📂</span> ${kb.name}
          </h1>
        </div>
        ${isAdmin ? `
        <div style="display:flex; gap:1rem;">
          <label class="btn btn-primary shadow-lg" style="margin:0; cursor:pointer; height:48px;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:0.6rem;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Upload Document
            <input type="file" id="kb-file-upload" style="display:none;" onchange="handleKBFileUpload('${kb.id}')" />
          </label>
          <button class="btn glass" style="color:var(--error); border-color:rgba(239, 68, 68, 0.2); height:48px;" onclick="handleKBDelete('${kb.id}')">Delete Collection</button>
        </div>
        ` : ''}
      </div>

      <!-- Upload Progress Card -->
      <div id="kb-upload-card" class="dashboard-card" style="display:none; margin-bottom:2rem; background:rgba(99, 102, 241, 0.05); border:1px solid var(--accent-indigo);">
        <div class="dashboard-card-body" style="padding:1.5rem;">
          <div style="display:flex; justify-content:space-between; margin-bottom:1rem; align-items:center;">
            <span id="kb-upload-filename" style="font-weight:700; color:#fff;">document.pdf</span>
            <span id="kb-upload-percent" class="badge badge-primary">0%</span>
          </div>
          <div class="progress-container" style="height:8px; background:rgba(255,255,255,0.05);"><div id="kb-upload-progress" class="progress-bar" style="width:0%;"></div></div>
          <div id="kb-upload-status" style="font-size:0.85rem; margin-top:1rem; color:var(--text-dim); font-weight:500;">Ingesting into semantic layer...</div>
        </div>
      </div>

      <div class="dashboard-card">
        <div class="dashboard-card-header">
           <h3 class="dashboard-card-title">Indexed Documentation</h3>
           <span class="badge glass" style="font-size:0.75rem; border-color:rgba(255,255,255,0.05);">RAG CONTEXT</span>
        </div>
        <div class="dashboard-card-body" id="document-list" style="padding:0;">
          <div style="text-align:center; padding:5rem;"><div class="spinner" style="margin:0 auto;"></div></div>
        </div>
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
          <tbody>${data.documents.map((doc, i) => {
      let statusBadge = '';
      if (doc.status === 'indexed') statusBadge = '<span class="badge badge-success">✓ Indexed</span>';
      else if (doc.status === 'error') statusBadge = '<span class="badge badge-error">⚠ Error</span>';
      else statusBadge = '<span class="badge badge-info">⌛ Processing</span>';

      return `
              <tr class="animate-up stagger-${(i % 4) + 1}">
                <td style="font-weight:600;">${doc.name}</td>
                <td>${statusBadge}</td>
                <td style="font-size:0.85rem;" class="tabular">${new Date(doc.created_at).toLocaleDateString()}</td>
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
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Safety & Governance</h1>
          <p class="page-subtitle">Define strict operational guardrails and compliance protocols for AI agents</p>
        </div>
        <button class="btn btn-primary shadow-lg" onclick="showPolicyModal()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:0.5rem;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Establish Protocol
        </button>
      </div>

      <div class="dashboard-card">
        <div class="dashboard-card-header">
          <h3 class="dashboard-card-title">Governance Engine Policies</h3>
          <span class="badge glass" style="font-size:0.75rem; border-color:rgba(255,255,255,0.05);">SYSTEM GUARDRAILS</span>
        </div>
        <div style="overflow-x:auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th style="padding-left:2.5rem;">POLICY IDENTITY</th>
                <th>CLASSIFICATION</th>
                <th>OPERATIONAL DIRECTIVE</th>
                <th style="padding-right:2.5rem; text-align:right;">CONTROL</th>
              </tr>
            </thead>
            <tbody id="policy-list">
              <tr><td colspan="4" style="text-align:center;padding:5rem;color:var(--text-muted);"><div class="spinner" style="margin:0 auto;"></div></td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Policy Modal -->
      <div id="policy-modal" class="modal-overlay">
        <div class="modal">
          <div class="modal-header">
             <h3 class="modal-title">Establish Safety Protocol</h3>
             <button class="btn-icon" onclick="closePolicyModal()">✕</button>
          </div>
          <div class="modal-body">
            <form id="policy-form" onsubmit="event.preventDefault(); handlePolicyCreate();">
              <div class="form-group">
                <label class="form-label">Protocol Identifier</label>
                <input type="text" id="policy-name" class="form-input" placeholder="e.g. SEC-FIN-01-MASKING" required />
              </div>
              <div class="form-group">
                <label class="form-label">Directive Severity</label>
                <select id="policy-type" class="form-select">
                  <option value="compliance">Compliance (Access mapping)</option>
                  <option value="security">High-Security (Blocking rules)</option>
                  <option value="cleaning">Data Sanctuary (Refining rules)</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Neural Directive (The Rule)</label>
                <textarea id="policy-desc" class="form-input" style="min-height:120px;" placeholder="Implicit instructions for the AI engine... e.g. Anonymize all identifiers matching PII patterns." required></textarea>
              </div>
              <div class="modal-footer" style="padding:0; margin-top:2rem; border:none;">
                <button type="button" class="btn btn-secondary glass" onclick="closePolicyModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Establish Policy</button>
              </div>
            </form>
          </div>
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
      list.innerHTML = data.policies.map((p, i) => `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.03);" class="animate-up stagger-${(i % 4) + 1}">
          <td style="padding-left:2rem;"><span style="font-weight:700; color:#fff;">${p.name}</span></td>
          <td><span class="badge ${p.rule_type === 'security' ? 'badge-error' : 'badge-info'}" style="border-radius:6px;">${p.rule_type.toUpperCase()}</span></td>
          <td style="color:var(--text-dim);font-size:0.95rem;max-width:400px; line-height:1.6; padding:1.25rem 0;">${p.description}</td>
          <td style="text-align:right; padding-right:2rem;"><button class="btn btn-icon glass sm" onclick="handlePolicyDelete('${p.id}')" style="width:36px; height:36px; color:rgba(255,255,255,0.4);"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg></button></td>
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
    <div class="dashboard-container">
      <div class="page-header" style="margin-bottom:2.5rem;">
        <div>
          <h1 class="page-title">Intelligence Refinement</h1>
          <p class="page-subtitle">Configure business logic, semantic context, and operational guardrails</p>
        </div>
        <button class="btn btn-primary shadow-lg" onclick="navigate('dashboard')">
          Deploy Configuration 👉
        </button>
      </div>

      <div class="enrichment-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(360px, 1fr)); gap:2.5rem;">
        <div class="dashboard-card enrichment-card" style="padding:0; overflow:hidden;">
          <div class="dashboard-card-header" style="padding:2rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
              <h3 class="dashboard-card-title">📖 Metric Dictionary</h3>
              ${isAdmin ? `<button class="btn btn-sm btn-primary" onclick="showMetricModal()">➕ Define</button>` : ''}
            </div>
            <div style="font-size:0.85rem; padding:1.25rem; background:rgba(99, 102, 241, 0.05); border-radius:12px; border-left:4px solid var(--accent-indigo);">
              <div style="margin-bottom:0.4rem; color:var(--text-main); font-weight:700;">Logic Protocol</div>
              <div style="color:var(--text-dim); line-height:1.5; font-weight:500;">Ensures the AI agent utilizes authorized business formulas for all multi-stream calculations.</div>
            </div>
          </div>
          <div class="dashboard-card-body" id="metrics-list" style="max-height:450px; overflow-y:auto; padding:1.5rem;">
            <div style="text-align:center;padding:3rem;"><div class="spinner" style="margin:0 auto;"></div></div>
          </div>
        </div>

        <div class="dashboard-card enrichment-card" style="padding:0; overflow:hidden;">
          <div class="dashboard-card-header" style="padding:2rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
              <h3 class="dashboard-card-title">🧠 Knowledge Base</h3>
              ${isAdmin ? `<button class="btn btn-sm btn-primary" onclick="showKBModal()">➕ New</button>` : ''}
            </div>
            <div style="font-size:0.85rem; padding:1.25rem; background:rgba(6, 182, 212, 0.05); border-radius:12px; border-left:4px solid var(--accent-cyan);">
              <div style="margin-bottom:0.4rem; color:var(--text-main); font-weight:700;">Contextual Engine</div>
              <div style="color:var(--text-dim); line-height:1.5; font-weight:500;">Indexes non-relational documentation to broaden the agent's logical reasoning capabilities.</div>
            </div>
          </div>
          <div class="dashboard-card-body" id="kb-list" style="display:grid; grid-template-columns:1fr; gap:1.25rem; max-height:450px; overflow-y:auto; padding:1.5rem;">
            <div style="text-align:center;padding:3rem;"><div class="spinner" style="margin:0 auto;"></div></div>
          </div>
        </div>

        <div class="dashboard-card enrichment-card" style="padding:0; overflow:hidden;">
          <div class="dashboard-card-header" style="padding:2rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
              <h3 class="dashboard-card-title">🛡️ Safety Guards</h3>
              ${isAdmin ? `<button class="btn btn-sm btn-primary" onclick="showPolicyModal()">🛡️ Protect</button>` : ''}
            </div>
            <div style="font-size:0.85rem; padding:1.25rem; background:rgba(239, 68, 68, 0.05); border-radius:12px; border-left:4px solid var(--error);">
              <div style="margin-bottom:0.4rem; color:var(--text-main); font-weight:700;">Governor Plane</div>
              <div style="color:var(--text-dim); line-height:1.5; font-weight:500;">Defines strict operational boundaries for AI agent behavior and administrative data scope.</div>
            </div>
          </div>
          <div class="dashboard-card-body" id="policies-list" style="display:grid; grid-template-columns:1fr; gap:1.25rem; max-height:450px; overflow-y:auto; padding:1.5rem;">
            <div style="text-align:center;padding:3rem;"><div class="spinner" style="margin:0 auto;"></div></div>
          </div>
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

    <div style="max-width:1100px; margin:0 auto;">
      
      <!-- Premium Hero Section -->
      <div class="glass-card" style="margin-bottom:4rem; padding:4.5rem 3rem; text-align:center; border-top: 2px solid var(--accent-indigo); position:relative; overflow:hidden;">
        <div style="position:absolute; top:-100px; left:-100px; width:300px; height:300px; background:var(--grad-primary); filter:blur(100px); opacity:0.1; border-radius:50%;"></div>
        <h2 style="font-family:var(--font-display); font-size:2.2rem; font-weight:700; margin-bottom:1.5rem; color:#fff; letter-spacing: -1px;">Accelerating Data Sovereignty</h2>
        <p style="font-size:1.15rem; color:var(--text-dim); max-width:750px; margin:0 auto; line-height:1.8; font-weight:500;">
          DataAnalyst.AI is the infrastructure layer for autonomous enterprise research. We bridge the gap between complex relational databases and executive decision-making through high-fidelity AI orchestration.
        </p>
      </div>

      <!-- Core Capabilities Grid -->
      <div style="display:flex; align-items:center; gap:1.5rem; margin-bottom:2.5rem;">
        <h3 style="margin:0; font-family:var(--font-display); font-size:1.4rem; font-weight:700; color:#fff; white-space:nowrap;">Core Architecture</h3>
        <div style="flex:1; height:1px; background:var(--glass-border);"></div>
      </div>
      
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:2rem; margin-bottom:5rem;">
        
        <div class="glass-card" style="padding:2.5rem; transition:var(--transition); border-color:rgba(255,255,255,0.05); background:rgba(255,255,255,0.01);">
          <div style="height:56px; width:56px; border-radius:16px; background:rgba(99,102,241,0.1); border:1px solid rgba(99,102,241,0.2); display:flex; align-items:center; justify-content:center; margin-bottom:1.5rem; color:var(--accent-indigo); font-size:1.5rem;">📊</div>
          <h4 style="margin-bottom:1rem; color:#fff; font-family:var(--font-display); font-weight:700; font-size:1.2rem;">Multi-Stream Synthesis</h4>
          <p style="font-size:0.95rem; color:var(--text-dim); line-height:1.7; margin:0;">
            Simultaneously coordinate multiple specialized agents to analyze data from disparate sources, producing unified analytical dashboards in real-time.
          </p>
        </div>

        <div class="glass-card" style="padding:2.5rem; transition:var(--transition); border-color:rgba(255,255,255,0.05); background:rgba(255,255,255,0.01);">
          <div style="height:56px; width:56px; border-radius:16px; background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.2); display:flex; align-items:center; justify-content:center; margin-bottom:1.5rem; color:var(--warning); font-size:1.5rem;">🔐</div>
          <h4 style="margin-bottom:1rem; color:#fff; font-family:var(--font-display); font-weight:700; font-size:1.2rem;">Guardian Protocol</h4>
          <p style="font-size:0.95rem; color:var(--text-dim); line-height:1.7; margin:0;">
            Enterprise-grade governance with Human-in-the-Loop validation. Every AI-generated query is inspected and approved before execution against production schemas.
          </p>
        </div>

        <div class="glass-card" style="padding:2.5rem; transition:var(--transition); border-color:rgba(255,255,255,0.05); background:rgba(255,255,255,0.01);">
          <div style="height:56px; width:56px; border-radius:16px; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.2); display:flex; align-items:center; justify-content:center; margin-bottom:1.5rem; color:var(--success); font-size:1.5rem;">🧠</div>
          <h4 style="margin-bottom:1rem; color:#fff; font-family:var(--font-display); font-weight:700; font-size:1.2rem;">RAG-Augmented Logic</h4>
          <p style="font-size:0.95rem; color:var(--text-dim); line-height:1.7; margin:0;">
            Combine structured database records with unstructured corporate knowledge. Our engine vectorizes documentation to provide unmatched contextual depth.
          </p>
        </div>

      </div>

      <!-- Deployment Specs -->
      <div class="glass-card" style="padding:3.5rem; margin-bottom:4rem; border-color:var(--accent-indigo); background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, transparent 100%);">
        <h3 style="margin:0 0 1.5rem 0; font-family:var(--font-display); font-size:1.5rem; font-weight:700; color:#fff;">System Integration</h3>
        <p style="color:var(--text-dim); line-height:1.8; margin-bottom:2.5rem; max-width:800px; font-size:1.05rem;">
          Designed for seamless orchestration across modern data stacks. The platform utilizes parallel processing workers to manage heavy analytical loads without impacting core database performance.
        </p>
        <div style="display:flex; gap:1rem; flex-wrap:wrap;">
          <span class="badge glass" style="padding:0.6rem 1.25rem; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px; border-radius:100px;">Neural Processing Units</span>
          <span class="badge glass" style="padding:0.6rem 1.25rem; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px; border-radius:100px;">Vector Embedding Layers</span>
          <span class="badge glass" style="padding:0.6rem 1.25rem; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px; border-radius:100px;">Semantic SQL Mappers</span>
          <span class="badge glass" style="padding:0.6rem 1.25rem; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px; border-radius:100px;">Governor Control Plane</span>
        </div>
      </div>
    </div>
  `;
}

// ── Neural Background Engine ───────────────────────────
function initNeuralBackground() {
  const canvas = document.getElementById('neural-bg');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let particles = [];
  let width, height;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  class Particle {
    constructor() {
      this.reset();
    }
    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.size = Math.random() * 2 + 1;
      this.alpha = Math.random() * 0.5 + 0.1;
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > width || this.y < 0 || this.y > height) this.reset();
    }
    draw() {
      ctx.fillStyle = `rgba(99, 102, 241, ${this.alpha})`;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function init() {
    resize();
    particles = Array.from({ length: 80 }, () => new Particle());
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach(p => {
      p.update();
      p.draw();
      particles.forEach(p2 => {
        const dx = p.x - p2.x;
        const dy = p.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          ctx.strokeStyle = `rgba(99, 102, 241, ${0.1 * (1 - dist / 150)})`;
          ctx.lineWidth = 0.5;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }
      });
    });
    requestAnimationFrame(animate);
  }

  window.addEventListener('resize', resize);
  init();
  animate();
}

// ── Boot ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initNeuralBackground();
  renderApp();
});
