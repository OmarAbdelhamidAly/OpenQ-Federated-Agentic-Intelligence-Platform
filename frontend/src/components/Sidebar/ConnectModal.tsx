import { useState } from 'react';
import { X, Database, Shield, Globe, Lock, GitBranch, Github, Code } from 'lucide-react';
import { DataSourcesAPI } from '../../services/api';

interface ConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ConnectModal({ isOpen, onClose, onSuccess }: ConnectModalProps) {
  const [tab, setTab] = useState<'sql' | 'github'>('sql');
  const [formData, setFormData] = useState({
    name: '',
    engine: 'postgresql',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: '',
  });
  
  const [githubData, setGithubData] = useState({
    github_url: '',
    branch: 'main',
    access_token: '',
  });
  
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (tab === 'sql') {
        await DataSourcesAPI.connectSQL(formData);
      } else {
        await DataSourcesAPI.connectGithub(githubData);
      }
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to connect', error);
      alert('Connection failed. Please check credentials or URL.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="w-full max-w-lg bg-[#0d1426] border border-slate-800 rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-lg">
              {tab === 'sql' ? <Database className="w-5 h-5 text-indigo-400" /> : <Github className="w-5 h-5 text-emerald-400" />}
            </div>
            <h2 className="text-xl font-bold text-white">Connect Context Source</h2>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Custom Tab Switcher */}
        <div className="flex items-center gap-1 p-2 bg-slate-900/50 border-b border-slate-800">
           <button 
             onClick={() => setTab('sql')}
             className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-widest rounded-xl transition-all ${tab === 'sql' ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'}`}
           >
             SQL Engine
           </button>
           <button
             onClick={() => setTab('github')}
             className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-widest rounded-xl transition-all flex items-center justify-center gap-2 ${tab === 'github' ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'}`}
           >
              GitHub Codebase
           </button>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {tab === 'sql' ? (
            <div className="grid grid-cols-2 gap-4 animate-in slide-in-from-left-4 fade-in duration-300">
               <div className="col-span-2 space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Connection Name</label>
                 <input required type="text" placeholder="e.g. Production Analytics" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
               </div>
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Engine</label>
                 <select className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all appearance-none" value={formData.engine} onChange={e => setFormData({...formData, engine: e.target.value as any})}>
                   <option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option><option value="mssql">SQL Server</option>
                 </select>
               </div>
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Port</label>
                 <input required type="number" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all" value={formData.port} onChange={e => setFormData({...formData, port: parseInt(e.target.value)})} />
               </div>
               <div className="col-span-2 space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Host / Endpoint</label>
                 <div className="relative"><Globe className="absolute left-4 top-3.5 w-4 h-4 text-slate-500" /><input required type="text" placeholder="db.example.com or IP address" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl pl-11 pr-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all" value={formData.host} onChange={e => setFormData({...formData, host: e.target.value})} /></div>
               </div>
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Database Name</label>
                 <input required type="text" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all" value={formData.database} onChange={e => setFormData({...formData, database: e.target.value})} />
               </div>
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Username</label>
                 <input required type="text" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all" value={formData.username} onChange={e => setFormData({...formData, username: e.target.value})} />
               </div>
               <div className="col-span-2 space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Password</label>
                 <div className="relative"><Lock className="absolute left-4 top-3.5 w-4 h-4 text-slate-500" /><input required type="password" placeholder="••••••••" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl pl-11 pr-4 py-3 text-slate-100 focus:outline-none focus:border-indigo-500/50 transition-all" value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} /></div>
               </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 animate-in slide-in-from-right-4 fade-in duration-300">
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Repository URL</label>
                 <div className="relative">
                   <Code className="absolute left-4 top-3.5 w-4 h-4 text-slate-500" />
                   <input required type="text" placeholder="https://github.com/user/repo" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl pl-11 pr-4 py-3 text-slate-100 focus:outline-none focus:border-emerald-500/50 transition-all" value={githubData.github_url} onChange={e => setGithubData({...githubData, github_url: e.target.value})} />
                 </div>
               </div>
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1">Branch</label>
                 <div className="relative">
                   <GitBranch className="absolute left-4 top-3.5 w-4 h-4 text-slate-500" />
                   <input type="text" placeholder="main" className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl pl-11 pr-4 py-3 text-slate-100 focus:outline-none focus:border-emerald-500/50 transition-all" value={githubData.branch} onChange={e => setGithubData({...githubData, branch: e.target.value})} />
                 </div>
               </div>
               <div className="space-y-2">
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1 flex justify-between">
                    <span>Access Token</span>
                    <span className="text-[9px] text-emerald-500 bg-emerald-500/10 px-1.5 rounded">Private Repos Only</span>
                 </label>
                 <div className="relative">
                   <Lock className="absolute left-4 top-3.5 w-4 h-4 text-slate-500" />
                   <input type="password" placeholder="ghp_..." className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl pl-11 pr-4 py-3 text-slate-100 focus:outline-none focus:border-emerald-500/50 transition-all" value={githubData.access_token} onChange={e => setGithubData({...githubData, access_token: e.target.value})} />
                 </div>
               </div>
            </div>
          )}

          {tab === 'sql' && (
             <div className="p-4 bg-amber-500/5 border border-amber-500/10 rounded-2xl flex items-start gap-3">
               <Shield className="w-4 h-4 text-amber-500 mt-0.5" />
               <p className="text-[10px] text-amber-200/60 leading-relaxed uppercase tracking-tight font-medium">
                 We recommend using a read-only database user for maximum security. 
                 The analyst will only execute SELECT queries.
               </p>
             </div>
          )}

          <button
            disabled={loading}
            className={`w-full py-4 rounded-xl font-black uppercase tracking-widest text-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed transform active:scale-[0.98] ${
              tab === 'sql' 
                ? 'bg-[var(--primary)] text-white shadow-[0_4px_20px_rgba(99,102,241,0.2)] hover:brightness-110' 
                : 'bg-emerald-500 text-slate-900 shadow-[0_4px_20px_rgba(16,185,129,0.2)] hover:bg-emerald-400'
            }`}
          >
            {loading ? 'Initializing Bridge...' : tab === 'sql' ? 'Establish Secure Connection' : 'Clone & Map Codebase'}
          </button>
        </form>
      </div>
    </div>
  );
}
