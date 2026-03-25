import { Layers, Server, Cpu, Hexagon } from 'lucide-react';

export default function SystemView() {
  const layers = [
    { 
      id: 1, 
      name: "API Gateway", 
      status: "STABLE", 
      load: "12%", 
      icon: Server, 
      desc: "Llama-3.3 Edge Routing & Request Sanitization",
      color: "border-emerald-500/20 text-emerald-400"
    },
    { 
      id: 2, 
      name: "Governance Engine", 
      status: "ENFORCING", 
      load: "4%", 
      icon: ShieldCheck, 
      desc: "Real-time Policy Intercept & Semantic RBAC",
      color: "border-[var(--primary)]/20 text-[var(--primary)]"
    },
    { 
      id: 3, 
      name: "Execution Nexus", 
      status: "SYNCHRONIZED", 
      load: "28%", 
      icon: Cpu, 
      desc: "Isolated Workers & Multi-Source Context Injection",
      color: "border-blue-500/20 text-blue-400"
    },
    { 
      id: 4, 
      name: "Neural Orchestrator", 
      status: "STANDBY", 
      load: "0%", 
      icon: Layers, 
      desc: "LangGraph Agentic Workflow & Tool Synthesis",
      color: "border-slate-800/50 text-slate-500"
    }
  ];

  function ShieldCheck({ className }: { className?: string }) {
    return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>;
  }

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scroll bg-[#0a0d17]/50">
      <div className="max-w-6xl mx-auto">
        <div className="mb-12">
           <div className="flex items-center gap-3 mb-4">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div>
              <span className="text-[10px] font-black text-emerald-500 uppercase tracking-[0.3em]">System Integrity: Optimal</span>
           </div>
           <h1 className="text-4xl font-black text-white tracking-tight uppercase">Architecture Nexus</h1>
           <p className="text-slate-400 mt-2 font-medium max-w-2xl">
             Real-time visualization of the Vision 2026 autonomous orchestration stack and subsystem telemetry.
           </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          {layers.map((layer, i) => (
            <div key={i} className="group relative overflow-hidden">
               <div className="absolute -inset-0.5 bg-gradient-to-br from-[var(--primary)]/20 to-transparent rounded-[32px] opacity-0 group-hover:opacity-100 transition duration-500"></div>
               <div className={`relative bg-slate-900/40 border ${layer.color.split(' ')[0]} p-8 rounded-[32px] backdrop-blur-xl transition-all group-hover:border-[var(--primary)]/30 group-hover:translate-y-[-4px]`}>
                  <div className="flex justify-between items-start mb-6">
                    <div className="p-3 rounded-2xl bg-white/5 text-[var(--primary)] group-hover:bg-[var(--primary)] group-hover:text-white transition-all duration-500">
                      <layer.icon className="w-6 h-6" />
                    </div>
                    <div className="text-right">
                       <p className={`text-[10px] font-black uppercase tracking-widest ${layer.color.split(' ')[1]}`}>{layer.status}</p>
                       <p className="text-2xl font-black text-white mt-1 tabular-nums">{layer.load}</p>
                       <p className="text-[8px] text-slate-600 font-black uppercase tracking-widest mt-0.5">Current Utilization</p>
                    </div>
                  </div>
                  <h3 className="text-xl font-black text-white mb-2 uppercase tracking-tight">{layer.name}</h3>
                  <p className="text-sm text-slate-500 font-bold leading-relaxed">{layer.desc}</p>
                  
                  <div className="mt-8 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                     <div 
                       className="h-full bg-gradient-to-r from-[var(--primary)] to-[var(--primary-alt)] transition-all duration-1000"
                       style={{ width: layer.load }}
                     ></div>
                  </div>
               </div>
            </div>
          ))}
        </div>

        <div className="bg-[#171033]/40 border border-slate-800 rounded-[40px] p-12 text-center relative overflow-hidden group">
          <div className="absolute -top-24 -left-24 w-64 h-64 bg-[var(--primary)]/10 blur-[100px] rounded-full"></div>
          <div className="absolute -bottom-24 -right-24 w-64 h-64 bg-purple-500/10 blur-[100px] rounded-full"></div>
          
          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 rounded-2xl bg-[var(--primary)] flex items-center justify-center text-white shadow-2xl shadow-[var(--primary)]/20 mb-6 group-hover:scale-110 transition-transform duration-500">
              <Hexagon className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-black text-white mb-4 uppercase tracking-tighter">Diagnostic Deep Scan</h2>
            <p className="text-slate-400 max-w-lg text-sm font-medium leading-relaxed mb-8">
              Execute a comprehensive cross-cluster validation of all neural nodes and data sovereignty protocols.
            </p>
            <button className="bg-white/5 hover:bg-white/10 border border-white/10 text-white px-10 py-4 rounded-2xl text-xs font-black uppercase tracking-[0.2em] transition-all hover:border-[var(--primary)]/40 hover:text-[var(--primary)]">
              Initiate Cold Reboot Sequence
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
