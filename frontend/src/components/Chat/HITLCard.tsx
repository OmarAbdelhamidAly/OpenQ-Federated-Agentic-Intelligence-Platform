import { Loader2, ArrowRight, Flag, CheckCircle, ShieldCheck } from 'lucide-react';
import type { AnalysisJob } from '../../types';

interface HITLCardProps {
  job: AnalysisJob;
  isActing: boolean;
  onContinue: () => void;
  onFinalize: () => void;
}

export default function HITLCard({
  job,
  isActing,
  onContinue,
  onFinalize,
}: HITLCardProps) {
  const pillars = job.required_pillars || [];
  const currentIndex = job.complexity_index ?? 1; // 1-based, already completed

  const nextPillarName = pillars[currentIndex]
    ? pillars[currentIndex].toUpperCase()
    : null;

  return (
    <div className="animate-in slide-in-from-bottom-4 duration-500">
      {/* Progress Stepper */}
      <div className="flex items-center justify-center gap-2 mb-6">
        {pillars.map((pillar: string, i: number) => {
          const isDone = i < currentIndex;
          const isCurrent = i === currentIndex - 1;
          const isNext = i === currentIndex;
          return (
            <div key={i} className="flex items-center gap-2">
              <div className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border transition-all
                ${isDone ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : ''}
                ${isCurrent ? 'bg-[var(--primary)]/10 border-[var(--primary)]/40 text-[var(--primary)]' : ''}
                ${isNext ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 animate-pulse' : ''}
                ${!isDone && !isCurrent && !isNext ? 'bg-slate-800/50 border-slate-700/30 text-slate-600' : ''}
              `}>
                {isDone && <CheckCircle className="w-3 h-3" />}
                {isCurrent && <ShieldCheck className="w-3 h-3" />}
                {isNext && <ArrowRight className="w-3 h-3" />}
                {pillar.toUpperCase()}
              </div>
              {i < pillars.length - 1 && (
                <div className={`w-6 h-px ${i < currentIndex - 1 ? 'bg-emerald-500' : 'bg-slate-700'}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Main Card */}
      <div className="relative rounded-[28px] border border-amber-500/20 bg-gradient-to-br from-amber-500/5 via-slate-900/80 to-slate-900/80 backdrop-blur-xl p-6 shadow-2xl shadow-amber-500/5">
        <div className="absolute -inset-px rounded-[28px] bg-gradient-to-br from-amber-500/10 to-transparent opacity-50 pointer-events-none" />

        <div className="flex items-start gap-4 mb-5">
          <div className="w-10 h-10 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <p className="text-[10px] font-black text-amber-400 uppercase tracking-[0.2em] mb-1">
              🛡️ Insightify — Governance Checkpoint {currentIndex}/{pillars.length}
            </p>
            <h3 className="text-white font-black text-base">
              Step {currentIndex} Complete — Awaiting Command
            </h3>
            <p className="text-slate-400 text-xs font-medium mt-1">
              {pillars[currentIndex - 1]?.toUpperCase()} specialist has delivered its findings.
              {nextPillarName
                ? ` Ready to deploy ${nextPillarName} specialist.`
                : ' All specialists have reported. Ready to finalize.'}
            </p>
          </div>
        </div>

        {/* Partial Synthesis Preview */}
        {job.synthesis_report && (
          <div className="mb-5 p-4 rounded-2xl bg-slate-900/60 border border-slate-700/30">
            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">
              📋 Accumulated Intelligence
            </p>
            <p className="text-xs text-slate-300 leading-relaxed line-clamp-4 font-medium">
              {job.synthesis_report.replace(/###.*?\n/g, '').trim()}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3">
          {nextPillarName && (
            <button
              onClick={onContinue}
              disabled={isActing}
              className="flex-1 flex items-center justify-center gap-2 py-3.5 px-5 rounded-2xl bg-[var(--primary)] hover:brightness-110 text-white text-xs font-black uppercase tracking-widest transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-[var(--primary)]/20"
            >
              {isActing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              Continue → {nextPillarName} Specialist
            </button>
          )}
          <button
            onClick={onFinalize}
            disabled={isActing}
            className="flex items-center justify-center gap-2 py-3.5 px-5 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-black uppercase tracking-widest border border-slate-700/50 transition-all active:scale-95 disabled:opacity-50"
          >
            <Flag className="w-4 h-4" />
            Finalize Report
          </button>
        </div>
      </div>
    </div>
  );
}
