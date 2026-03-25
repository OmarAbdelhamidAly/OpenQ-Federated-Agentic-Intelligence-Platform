import { useState, useEffect } from 'react';
import { ShieldCheck, Lock, Eye, AlertTriangle, ChevronRight, Plus, X, Zap, Trash2, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { GovernanceAPI } from '../../services/api';

export default function GovernanceView() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [protocols, setProtocols] = useState<any[]>([]);

  const fetchPolicies = async () => {
    try {
      setLoading(true);
      const data = await GovernanceAPI.list();
      setProtocols(data);
    } catch (e) {
      console.error("Failed to fetch policies", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const handleEstablish = async (e: any) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
      await GovernanceAPI.create({
        name: formData.get('name') as string,
        rule_type: formData.get('type') as string,
        description: `Autonomous guardrail for ${formData.get('type')} with ${formData.get('severity')} priority.`
      });
      fetchPolicies();
      setIsModalOpen(false);
    } catch (e) {
      alert("Failed to establish policy. Check backend logs.");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to revoke this protocol?")) return;
    try {
      await GovernanceAPI.delete(id);
      fetchPolicies();
    } catch (e) {
      alert("Failed to delete policy.");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto custom-scroll bg-[#0a0d17]/50 relative">
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-md"
            />
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-lg bg-[#171c2a] border border-slate-700/50 rounded-[32px] shadow-2xl overflow-hidden"
            >
              <div className="p-8 border-b border-slate-800 flex items-center justify-between bg-gradient-to-r from-emerald-500/10 to-transparent">
                <div>
                  <h2 className="text-xl font-black text-white tracking-tight">Establish New Policy</h2>
                  <p className="text-xs text-slate-400 font-medium mt-1 uppercase tracking-widest">Autonomous Guardrail Provisioning</p>
                </div>
                <button onClick={() => setIsModalOpen(false)} className="p-2 hover:bg-white/5 rounded-xl transition-all">
                  <X className="w-5 h-5 text-slate-500" />
                </button>
              </div>

              <form onSubmit={handleEstablish} className="p-8 space-y-6">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Protocol Name</label>
                  <input name="name" required placeholder="e.g. Health Data Anonymization" className="w-full bg-black/20 border border-slate-800 focus:border-emerald-500/50 outline-none rounded-2xl px-5 py-4 text-white text-sm font-bold transition-all" />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Policy Type</label>
                    <select name="type" className="w-full bg-black/20 border border-slate-800 focus:border-emerald-500/50 outline-none rounded-2xl px-5 py-4 text-white text-sm font-bold appearance-none transition-all">
                      <option value="security">Security</option>
                      <option value="compliance">Compliance</option>
                      <option value="cleaning">Data Cleaning</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Severity</label>
                    <select name="severity" className="w-full bg-black/20 border border-slate-800 focus:border-emerald-500/50 outline-none rounded-2xl px-5 py-4 text-white text-sm font-bold appearance-none transition-all">
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                    </select>
                  </div>
                </div>

                <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-2xl shadow-xl shadow-emerald-500/20 transition-all flex items-center justify-center gap-3 active:scale-[0.98]">
                  <Zap className="w-5 h-5" /> Activate Guardrail
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="p-8 pb-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2"></div>
        
        <div className="relative z-10 flex items-end justify-between">
          <div>
             <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                   <ShieldCheck className="w-5 h-5 text-emerald-400" />
                </div>
                <span className="text-[10px] font-black text-emerald-400 uppercase tracking-[0.3em]">Governance & Oversight</span>
             </div>
             <h1 className="text-4xl font-black text-white tracking-tight">Safety Protocols</h1>
             <p className="text-slate-400 mt-2 font-medium max-w-xl">
               Maintain enterprise sovereignty with autonomous natural-language policy enforcement and neural guardrails.
             </p>
          </div>

          <button 
            onClick={() => setIsModalOpen(true)}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-2xl text-sm font-bold shadow-xl shadow-emerald-500/20 transition-all flex items-center gap-2 group"
          >
            <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform" /> Establish Policy
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="px-8 pb-12 grid grid-cols-12 gap-6">
        
        {/* Policy List */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] overflow-hidden backdrop-blur-xl">
            <div className="p-6 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Active Directives</h3>
              <span className="text-[10px] text-slate-600 font-bold uppercase">{protocols.length} Enabled</span>
            </div>

            <div className="divide-y divide-slate-800/50">
              {loading ? (
                <div className="p-12 flex flex-col items-center gap-4">
                  <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Syncing Security Matrix...</p>
                </div>
              ) : protocols.length === 0 ? (
                <div className="p-12 text-center">
                  <ShieldCheck className="w-12 h-12 text-slate-800 mx-auto mb-4 opacity-20" />
                  <p className="text-xs font-bold text-slate-600 uppercase tracking-widest">No active guardrails found</p>
                </div>
              ) : protocols.map((p) => (
                <div key={p.id} className="p-6 hover:bg-white/5 transition-all cursor-pointer group flex items-center justify-between">
                  <div className="flex items-center gap-5">
                    <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all ${
                      p.rule_type === 'security' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400'
                    }`}>
                      {p.rule_type === 'security' ? <Lock className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <p className="font-bold text-white group-hover:text-emerald-400 transition-colors uppercase text-sm tracking-tight">{p.name}</p>
                        <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 uppercase tracking-widest">{p.id.substring(0, 8)}</span>
                      </div>
                      <p className="text-[10px] text-slate-500 font-bold uppercase mt-1 tracking-widest">
                        {p.rule_type.toUpperCase()} • ENFORCED REAL-TIME
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                       <p className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Enforced</p>
                       <p className="text-[8px] font-bold text-slate-600 uppercase mt-0.5">Latency: 4ms</p>
                    </div>
                    <div className="flex items-center gap-2">
                       <button 
                         onClick={() => handleDelete(p.id)}
                         className="p-2 text-slate-700 hover:text-red-400 hover:bg-red-400/10 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                       >
                         <Trash2 className="w-4 h-4" />
                       </button>
                       <ChevronRight className="w-5 h-5 text-slate-700 group-hover:text-white group-hover:translate-x-1 transition-all" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar Info */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] p-6 backdrop-blur-xl">
             <div className="flex items-center gap-3 mb-6">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Sovereignty Audit</h3>
             </div>
             <div className="space-y-4">
                <div className="p-4 rounded-2xl bg-black/20 border border-slate-800/50">
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Redacted Entities</p>
                   <p className="text-2xl font-black text-white">1,482</p>
                </div>
                <div className="p-4 rounded-2xl bg-black/20 border border-slate-800/50">
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Blocked Queries</p>
                   <p className="text-2xl font-black text-white">12</p>
                </div>
                <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/20">
                   <p className="text-[10px] font-black text-emerald-400 uppercase tracking-widest mb-1">Compliance Score</p>
                   <p className="text-2xl font-black text-emerald-400">99.8%</p>
                </div>
             </div>
          </div>
        </div>

      </div>
    </div>
  );
}
