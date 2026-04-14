import { Database, Sparkles, Zap } from 'lucide-react';

export function EmptyStateSelectSource() {
  const steps = [
    {
      id: '01',
      title: 'Target Sources',
      ar: 'حدد المصادر',
      desc: 'Select CSV, SQL, PDFs, Code, or Media from the nexus sidebar to begin.',
      icon: <Database className="w-5 h-5" />,
    },
    {
      id: '02',
      title: 'Cross-Correlate',
      ar: 'ربط البيانات',
      desc: 'Insightify automatically links disparate sources in memory.',
      icon: <Sparkles className="w-5 h-5" />,
    },
    {
      id: '03',
      title: 'Synthesize',
      ar: 'التركيب الذكي',
      desc: 'Generate autonomous executive insights and unified reports.',
      icon: <Zap className="w-5 h-5" />,
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4 animate-in fade-in zoom-in duration-1000">
      <div className="mb-12">
        <div className="w-20 h-20 rounded-[32px] bg-[var(--primary)]/10 flex items-center justify-center mx-auto mb-6 relative">
          <div className="absolute -inset-4 bg-[var(--primary)]/5 blur-2xl rounded-full animate-pulse"></div>
          <Sparkles className="w-8 h-8 text-[var(--primary)] relative z-10" />
        </div>
        <h2 className="text-3xl font-black text-white tracking-tighter uppercase mb-2">Insightify</h2>
        <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.3em]">
          Autonomous Multi-Source Synthesis
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl w-full">
        {steps.map((step) => (
          <div
            key={step.id}
            className="p-6 bg-white/5 border border-slate-800/50 rounded-[32px] flex flex-col items-center gap-4 group hover:border-[var(--primary)]/30 hover:bg-[var(--primary)]/5 transition-all"
          >
            <div className="w-10 h-10 rounded-2xl bg-slate-800 flex items-center justify-center text-slate-400 group-hover:bg-[var(--primary)] group-hover:text-white transition-all">
              {step.icon}
            </div>
            <div>
              <p className="text-[10px] font-black text-[var(--primary)] uppercase tracking-widest mb-1">
                Step {step.id}
              </p>
              <h4 className="font-black text-white uppercase text-sm mb-1">{step.title}</h4>
              <p className="text-[10px] text-slate-500 font-bold uppercase mb-3">{step.ar}</p>
              <p className="text-[11px] text-slate-400 leading-relaxed font-medium">{step.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 flex items-center gap-3 py-2 px-4 rounded-full bg-slate-900/50 border border-slate-800">
        <div className="w-2 h-2 rounded-full bg-[var(--primary)] animate-pulse" />
        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
          Awaiting Nexus Directive...
        </span>
      </div>
    </div>
  );
}

export function EmptyStateWelcome({
  setInput,
  schema,
}: {
  setInput: (v: string) => void;
  schema?: any;
}) {
  const suggestions: string[] =
    schema?.suggested_questions && schema.suggested_questions.length > 0
      ? schema.suggested_questions
      : [
          'Summarize key anomalies in this dataset',
          'Predict trends for the next fiscal quarter',
          'Identify cross-source correlations',
          'Analyze data quality and suggest fixes',
        ];

  return (
    <div className="flex flex-col items-center justify-center h-full mt-20 text-center animate-in fade-in slide-in-from-bottom-8 duration-1000">
      <h2 className="text-4xl font-black mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-slate-500 tracking-tighter uppercase p-2">
        Awaiting Directive
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl w-full">
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => setInput(s)}
            className="p-4 bg-white/5 border border-slate-800/50 rounded-2xl text-left hover:border-[var(--primary)]/40 hover:bg-[var(--primary)]/5 transition-all group"
          >
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest group-hover:text-[var(--primary)] mb-1">
              Inquiry Vector 0{i + 1}
            </p>
            <p className="text-xs font-bold text-slate-300 group-white">{s}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
