import { useState, useEffect } from 'react';
import { AnalysisAPI } from '../../services/api';
import type { AnalysisJob } from '../../types';
import { 
  Activity, 
  Database, 
  Zap, 
  Brain,
  CheckCircle2,
  AlertCircle,
  Loader2
} from 'lucide-react';

const MOCK_DEMO_EVENTS: AnalysisJob[] = [
  {
    id: "demo-node-001",
    status: "done",
    question: "Perform deep strategic synthesis of Q4 Revenue vs. Supply Chain disruption reports (PDF + SQL).",
    created_at: new Date(Date.now() - 3600000).toISOString(),
    completed_at: new Date(Date.now() - 3500000).toISOString(),
    source_id: "demo",
    thinking_steps: [],
    executive_summary: "Success: Identified 12% margin leakage due to logistics bottlenecks in the EMEA region."
  },
  {
    id: "demo-node-002",
    status: "done",
    question: "تحليل ميزانية الربع الثالث ومقارنتها بالسنوات السابقة لتحديد فرص خفض التكاليف.",
    created_at: new Date(Date.now() - 7200000).toISOString(),
    completed_at: new Date(Date.now() - 7100000).toISOString(),
    source_id: "demo",
    thinking_steps: [],
    executive_summary: "تم اكتشاف وفر جيو-استراتيجي بنسبة 5% في قطاع العقود اللوجستية."
  },
  {
    id: "demo-node-003",
    status: "running",
    question: "Vision-RAG: Extracting structural debt signals from 150+ scanned bank statements (Deep Vision Mode).",
    created_at: new Date(Date.now() - 600000).toISOString(),
    completed_at: "",
    source_id: "demo",
    thinking_steps: [],
  },
  {
    id: "demo-node-004",
    status: "done",
    question: "Audit 200+ Employee NDAs for high-risk indemnity clauses and non-standard liability terms.",
    created_at: new Date(Date.now() - 86400000).toISOString(),
    completed_at: new Date(Date.now() - 86300000).toISOString(),
    source_id: "demo",
    thinking_steps: [],
    executive_summary: "4 contracts flagged for immediate legal review due to missing liability caps."
  }
];

export default function NeuralFeed() {
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      const history = await AnalysisAPI.getHistory();
      // Combine real jobs with Demo events for a "Full" Enterprise look
      const combined = [...(history || []), ...MOCK_DEMO_EVENTS];
      setJobs(combined);
    } catch (e) {
      console.error("Failed to fetch feed history", e);
      setJobs(MOCK_DEMO_EVENTS); // Fallback to demo events if API fails
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // Poll every 15 seconds for real-time updates
    const interval = setInterval(fetchHistory, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading && jobs.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0d17]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 text-[var(--primary)] animate-spin" />
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Syncing Intelligence Stream...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto custom-scroll bg-[#0a0d17]/50 p-8 pt-12 pb-24">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12 relative">
          <div className="absolute -top-10 -left-10 w-40 h-40 bg-indigo-500/10 blur-[80px] rounded-full"></div>
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20">
               <Activity className="w-5 h-5 text-amber-500" />
            </div>
            <span className="text-[10px] font-black text-amber-500 uppercase tracking-[0.3em] font-['JetBrains_Mono']">Live Activity</span>
          </div>
          <h1 className="text-4xl font-black text-white tracking-tight">Neural Intelligence Feed</h1>
          <p className="text-slate-400 mt-2 font-medium">Real-time tracking of autonomous reasoning, cross-source synthesis, and data ingestion protocols.</p>
        </header>

        <div className="space-y-4">
          {jobs.sort((a,b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).map((job) => (
            <FeedEvent key={job.id} job={job} />
          ))}
        </div>
      </div>
    </div>
  );
}

function FeedEvent({ job }: { job: AnalysisJob }) {
  const isDone = job.status === 'done';
  const isError = job.status === 'error';

  const perspective = job.question.length > 50 ? "Executive Synthesis" : "Logical Inquiry";
  
  return (
    <div className="bg-slate-900/40 border border-slate-800/80 rounded-[28px] p-5 backdrop-blur-xl relative overflow-hidden group hover:border-[var(--primary)]/30 transition-all shadow-xl hover:shadow-[var(--primary)]/5">
      <div className="flex items-start gap-5 relative z-10">
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 border transition-all ${
          isDone ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' : 
          isError ? 'bg-rose-500/10 border-rose-500/20 text-rose-500' : 
          'bg-indigo-500/10 border-indigo-500/20 text-indigo-500'
        }`}>
          {isDone ? <CheckCircle2 className="w-6 h-6" /> : 
           isError ? <AlertCircle className="w-6 h-6" /> : 
           <Brain className="w-6 h-6 animate-pulse" />}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <span className={`text-[8px] font-black px-2 py-0.5 rounded border uppercase tracking-widest ${
                isDone ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' : 
                isError ? 'bg-rose-500/10 border-rose-500/20 text-rose-500' : 
                'bg-indigo-500/10 border-indigo-500/20 text-indigo-500'
              }`}>
                {perspective}
              </span>
              <span className="text-[10px] font-bold text-slate-600 font-['JetBrains_Mono'] tracking-tighter">
                {new Date(job.created_at).toLocaleDateString()} • {new Date(job.created_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="flex items-center gap-1.5 min-w-[80px] justify-end">
              <div className={`w-2 h-2 rounded-full ${
                isDone ? 'bg-emerald-500' : 
                isError ? 'bg-rose-500' : 
                'bg-indigo-500 animate-pulse'
              }`} />
              <span className={`text-[10px] font-black uppercase tracking-tighter ${
                isDone ? 'text-emerald-500' : 
                isError ? 'text-rose-500' : 
                'text-indigo-400'
              }`}>
                {job.status}
              </span>
            </div>
          </div>

          <h4 className="text-white font-bold text-sm tracking-tight line-clamp-2 leading-relaxed mb-3">
            {job.question}
          </h4>

          {isDone && job.executive_summary && (
            <p className="text-[11px] text-slate-400 leading-relaxed font-medium bg-white/5 p-3 rounded-xl border border-white/5 mb-3 italic">
              "{job.executive_summary}"
            </p>
          )}

          <div className="flex items-center gap-6 mt-4 pt-3 border-t border-slate-800/50">
            <div className="flex items-center gap-2">
               <Database className="w-3.5 h-3.5 text-slate-500" />
               <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Job Node: {job.id.slice(0, 8)}</span>
            </div>
            <div className={`flex items-center gap-2 ${job.id.startsWith('demo') ? 'opacity-100' : 'opacity-40'}`}>
               <Zap className={`w-3.5 h-3.5 ${job.id.startsWith('demo') ? 'text-amber-500' : 'text-slate-500'}`} />
               <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Contextual Recall: 100%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
