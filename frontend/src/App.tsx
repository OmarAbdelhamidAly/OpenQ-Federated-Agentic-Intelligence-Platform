import { useState, useEffect } from 'react';
import './index.css';

// Layout Components
import Sidebar from './components/Sidebar/Sidebar';
import ChatInterface from './components/Chat/ChatInterface';
import AuthPage from './components/Auth/AuthPage';
import NeuralBackground from './components/NeuralBackground';
import PortalDashboard from './components/Dashboard/PortalDashboard';
import GovernanceView from './components/Governance/GovernanceView';
import TeamManagementView from './components/Governance/TeamManagementView';
import KnowledgeHubView from './components/Governance/KnowledgeHubView';
import SystemView from './components/System/SystemView';
import { AuthAPI } from './services/api';

// Team Management integrated via external component

function App() {
  const [activeSourceIds, setActiveSourceIds] = useState<string[]>([]);
  const [currentView, setCurrentView] = useState<string>('dashboard');
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem('auth_token');
    const savedRefreshToken = localStorage.getItem('auth_refresh_token');
    const savedUser = localStorage.getItem('auth_user');
    
    if (savedToken && savedRefreshToken && savedUser) {
      try {
        const parsedUser = JSON.parse(savedUser);
        if (parsedUser && typeof parsedUser === 'object') {
          setToken(savedToken);
          setUser(parsedUser);
          
          // Apply Branding
          if (parsedUser.branding_config) {
            const config = parsedUser.branding_config;
            if (config.primary_color) document.documentElement.style.setProperty('--primary', config.primary_color);
            if (config.secondary_color) document.documentElement.style.setProperty('--secondary', config.secondary_color);
          }
        } else {
          clearAuth();
        }
      } catch (e) {
        clearAuth();
      }
    }
    setIsInitializing(false);
  }, []);

  const clearAuth = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_refresh_token');
    localStorage.removeItem('auth_user');
    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    if (user?.branding_config?.primary_color) {
      // Simple Hex to HSL conversion for CSS variables
      const hex = user.branding_config.primary_color;
      const r = parseInt(hex.slice(1, 3), 16) / 255;
      const g = parseInt(hex.slice(3, 5), 16) / 255;
      const b = parseInt(hex.slice(5, 7), 16) / 255;
      const max = Math.max(r, g, b), min = Math.min(r, g, b);
      let h = 0, s, l = (max + min) / 2;
      if (max === min) { h = s = 0; } else {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
          case r: h = (g - b) / d + (g < b ? 6 : 0); break;
          case g: h = (b - r) / d + 2; break;
          case b: h = (r - g) / d + 4; break;
        }
        h /= 6;
      }
      document.documentElement.style.setProperty('--p-h', (h * 360).toString());
      document.documentElement.style.setProperty('--p-s', (s * 100) + '%');
      document.documentElement.style.setProperty('--p-l', (l * 100) + '%');
    }
  }, [user]);

  const handleLogin = (newToken: string, newRefreshToken: string, newUser: any) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('auth_token', newToken);
    localStorage.setItem('auth_refresh_token', newRefreshToken);
    localStorage.setItem('auth_user', JSON.stringify(newUser));

    // Apply Branding
    if (newUser.branding_config) {
      const config = newUser.branding_config;
      if (config.primary_color) document.documentElement.style.setProperty('--primary', config.primary_color);
      if (config.secondary_color) document.documentElement.style.setProperty('--secondary', config.secondary_color);
    }
  };

  const handleLogout = async () => {
    try {
      await AuthAPI.logout();
    } catch (e) {
      console.error("Logout failed", e);
    } finally {
      clearAuth();
    }
  };

  const renderContent = () => {
    switch (currentView) {
      case 'dashboard':
        return <ChatInterface activeSourceIds={activeSourceIds} />;
      case 'csv':
        return <PortalDashboard type="csv" onSelectSource={(id) => { 
          if (id) setActiveSourceIds([id]); 
          setCurrentView('dashboard'); 
        }} />;
      case 'sql':
        return <PortalDashboard type="sql" onSelectSource={(id) => { 
          if (id) setActiveSourceIds([id]); 
          setCurrentView('dashboard'); 
        }} />;
      case 'pdf':
        return <PortalDashboard type="pdf" onSelectSource={(id) => { 
          if (id) setActiveSourceIds([id]); 
          setCurrentView('dashboard'); 
        }} />;
      case 'json':
        return <PortalDashboard type="json" onSelectSource={(id) => { 
          if (id) setActiveSourceIds([id]); 
          setCurrentView('dashboard'); 
        }} />;
      case 'governance':
        return <GovernanceView />;
      case 'system':
        return <SystemView />;
      case 'team':
        return <TeamManagementView />;
      case 'knowledge':
        return <KnowledgeHubView />;
      default:
        return <ChatInterface activeSourceIds={activeSourceIds} />;
    }
  };

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-[#0a041f] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <div className="min-h-screen bg-[#0a041f] relative overflow-hidden">
        <NeuralBackground />
        <AuthPage onLogin={handleLogin} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-transparent text-slate-200 flex overflow-hidden relative">
      <NeuralBackground />
      <Sidebar 
        activeSourceIds={activeSourceIds} 
        onToggleSource={(id) => {
          if (!id) {
            setActiveSourceIds([]);
            return;
          }
          setActiveSourceIds(prev => 
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
          );
        }} 
        onSelectSource={(id) => {
          if (id) {
            setActiveSourceIds([id]);
            setCurrentView('dashboard');
          } else {
            setActiveSourceIds([]);
          }
        }}
        currentView={currentView}
        onViewChange={setCurrentView}
        user={user}
        onLogout={handleLogout}
      />

      <main className="flex-1 flex flex-col relative overflow-hidden bg-gradient-to-br from-indigo-500/5 via-transparent to-purple-500/5">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
