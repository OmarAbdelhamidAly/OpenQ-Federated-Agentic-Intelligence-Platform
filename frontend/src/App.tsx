import { useState, useEffect, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import './index.css';

// Layout Components
import Sidebar from './components/Sidebar/Sidebar';
import ChatInterface from './components/Chat/ChatInterface';
import AuthPage from './components/Auth/AuthPage';
import NeuralBackground from './components/NeuralBackground';
import PortalDashboard from './components/Dashboard/PortalDashboard';
import SentinelNexus from './components/Governance/SentinelNexus';
import TeamManagementView from './components/Governance/TeamManagementView';
import AboutUs from './components/Dashboard/AboutUs';
import NexusDashboard from './components/NexusDashboard';
import { AuthAPI } from './services/api';
import { useAppStore } from './store/appStore';
import type { AuthUser, BrandingConfig, PortalType } from './types';
import { PORTAL_TYPES } from './types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Convert a hex color string to HSL CSS-variable values on :root */
function applyHexToHSLVars(hex: string): void {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  const l = (max + min) / 2;

  let h = 0;
  let s = 0;

  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }

  const root = document.documentElement.style;
  root.setProperty('--p-h', (h * 360).toString());
  root.setProperty('--p-s', `${s * 100}%`);
  root.setProperty('--p-l', `${l * 100}%`);
}

/** Apply branding colours from a BrandingConfig object */
function applyBranding(config: BrandingConfig): void {
  const root = document.documentElement.style;
  if (config.primary_color) {
    root.setProperty('--primary', config.primary_color);
    applyHexToHSLVars(config.primary_color);
  }
  if (config.secondary_color) {
    root.setProperty('--secondary', config.secondary_color);
  }
}

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  const {
    currentView,
    user,
    token,
    setAuth,
    clearAuth,
  } = useAppStore();

  const [isInitializing, setIsInitializing] = useState(true);

  const {
    isAuthenticated,
    user: auth0User,
    getAccessTokenSilently,
    logout: auth0Logout,
    isLoading: auth0Loading,
  } = useAuth0();

  // ── Commit login state (single source of truth) ──────────────────────────

  const handleLogin = useCallback(
    (newToken: string, newRefreshToken: string, newUser: AuthUser) => {
      setAuth(newToken, newRefreshToken, newUser);
      if (newUser.branding_config) applyBranding(newUser.branding_config);
    },
    [setAuth],
  );

  // ── Bootstrap authentication on mount ────────────────────────────────────

  useEffect(() => {
    if (auth0Loading) return;

    const init = async () => {
      if (isAuthenticated && auth0User) {
        try {
          const accessToken = await getAccessTokenSilently();
          const newUser: AuthUser = {
            id: auth0User.sub ?? '',
            email: auth0User.email,
            role: 'admin',
            tenant_id: 'auto-provisioned',
          };
          handleLogin(accessToken, 'auth0-refresh-token', newUser);
        } catch (e) {
          console.error('Error getting Auth0 access token', e);
        }
      } else {
        const savedToken = useAppStore.getState().token;
        if (savedToken && user) {
          if (user.branding_config) applyBranding(user.branding_config);
        } else {
          clearAuth();
        }
      }

      setIsInitializing(false);
    };

    init();
  }, [auth0Loading, isAuthenticated, auth0User, getAccessTokenSilently, handleLogin, clearAuth]);

  // ── Logout ────────────────────────────────────────────────────────────────

  const handleLogout = useCallback(async () => {
    try {
      if (isAuthenticated) {
        auth0Logout({ logoutParams: { returnTo: window.location.origin } });
      } else {
        await AuthAPI.logout();
      }
    } catch (e) {
      console.error('Logout failed', e);
    } finally {
      clearAuth();
    }
  }, [isAuthenticated, auth0Logout, clearAuth]);

  // ── View renderer ─────────────────────────────────────────────────────────

  const renderContent = () => {
    if (currentView === 'dashboard') {
      return <ChatInterface />;
    }

    if ((PORTAL_TYPES as string[]).includes(currentView)) {
      return (
        <PortalDashboard
          type={currentView as PortalType}
        />
      );
    }

    switch (currentView) {
      case 'sentinel': return <SentinelNexus />;
      case 'team':     return <TeamManagementView />;
      case 'about':    return <AboutUs />;
      case 'nexus':    return <NexusDashboard />;
      default:         return <ChatInterface />;
    }
  };

  // ── Loading screen ────────────────────────────────────────────────────────

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-[#0a041f] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  // ── Auth gate ─────────────────────────────────────────────────────────────

  if (!token || !user) {
    return (
      <div className="min-h-screen bg-[#0a041f] relative overflow-hidden">
        <NeuralBackground />
        <AuthPage onLogin={handleLogin} />
      </div>
    );
  }

  // ── Main shell ────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-transparent text-slate-200 flex overflow-hidden relative">
      <NeuralBackground />

      <Sidebar onLogout={handleLogout} />

      <main className="flex-1 flex flex-col relative overflow-hidden bg-gradient-to-br from-indigo-500/5 via-transparent to-purple-500/5">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;