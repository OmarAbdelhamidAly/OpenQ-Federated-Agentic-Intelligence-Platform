import { useState } from 'react';
import type { Message } from '../../hooks/useAnalysisPolling';
import { LangGraphVisualizer } from './LangGraphVisualizer';
import DynamicChart from '../Visualizations/DynamicChart';
import MarkdownBlock from '../Visualizations/MarkdownBlock';
import { User, Bot, ShieldAlert, CheckCircle2, Terminal, Volume2, VolumeX, Globe, Eye, Box, Lightbulb, ChevronRight, BarChart2 } from 'lucide-react';
import { AnalysisAPI } from '../../services/api';
import { speaker } from '../../utils/speech';
import { motion, AnimatePresence } from 'framer-motion';

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const [isApproving, setIsApproving] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  const toggleSpeech = () => {
    if (isSpeaking) {
      speaker.stop();
      setIsSpeaking(false);
    } else {
      if (message.job?.insight_report) {
        setIsSpeaking(true);
        speaker.speak(message.job.insight_report, () => setIsSpeaking(false));
      }
    }
  };

  const handleApprove = async () => {
    if (!message.job?.id) return;
    setIsApproving(true);
    try {
      await AnalysisAPI.approveJob(message.job.id);
    } catch (e) {
      console.error('Approval failed', e);
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
      {/* Avatar */}
      <div className={`shrink-0 w-10 h-10 rounded-2xl flex items-center justify-center shadow-2xl relative z-10 ${
        isUser
          ? 'bg-gradient-to-br from-[var(--primary)] to-[var(--primary-alt)] text-white shadow-[var(--primary)]/20'
          : 'bg-[#0f172a] border border-slate-800 text-[var(--primary)] shadow-black/40'
      }`}>
        {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
        {!isUser && <div className="absolute -inset-1 bg-[var(--primary)]/10 blur-lg rounded-full -z-10" />}
      </div>

      {/* Bubble */}
      <div className={`${isUser ? 'max-w-[85%]' : 'max-w-[95%]'} rounded-[24px] p-6 backdrop-blur-3xl shadow-2xl relative ${
        isUser
          ? 'bg-[var(--primary)]/10 border border-[var(--primary)]/20 text-white rounded-tr-sm self-end'
          : 'bg-[#0a0d17]/80 border border-slate-800/50 text-slate-200 rounded-tl-sm self-start w-full'
      }`}>
        {isUser ? (
          <p className="text-base leading-relaxed break-words">{message.content}</p>
        ) : (
          <div className="flex flex-col gap-6 w-full">

            {/* ── 1. LangGraph Workflow Visualizer ──────────────────── */}
            {message.job?.thinking_steps && message.job.thinking_steps.length > 0 && (
              <LangGraphVisualizer
                steps={message.job.thinking_steps}
                currentStatus={message.job.status}
                sourceType={message.job.source_type}
              />
            )}

            {/* ── 2. Awaiting Approval ──────────────────────────────── */}
            {message.job?.status === 'awaiting_approval' && (
              <div className="border border-amber-500/30 bg-amber-500/5 rounded-2xl overflow-hidden animate-in fade-in zoom-in duration-500">
                <div className="p-4 bg-amber-500/10 flex items-center gap-3 border-b border-amber-500/20">
                  <ShieldAlert className="w-5 h-5 text-amber-500" />
                  <h4 className="text-xs font-black text-amber-500 uppercase tracking-widest">Governance Intercept — Authorization Required</h4>
                </div>
                <div className="p-5 space-y-4">
                  <p className="text-sm text-slate-300 font-medium">
                    The autonomous analyst has formulated a SQL execution plan. Please review the query before granting data access.
                  </p>
                  {message.job.generated_sql && (
                    <div className="bg-black/40 rounded-xl p-4 border border-slate-800 font-mono text-[11px] text-indigo-300 overflow-x-auto custom-scroll relative group">
                      <Terminal className="absolute right-3 top-3 w-3 h-3 text-slate-600 group-hover:text-indigo-400 transition-colors" />
                      <code className="whitespace-pre">{message.job.generated_sql}</code>
                    </div>
                  )}
                  <button
                    disabled={isApproving}
                    onClick={handleApprove}
                    className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-3 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 active:scale-[0.98] disabled:opacity-50"
                  >
                    {isApproving ? (
                      <span className="animate-pulse">Authorizing...</span>
                    ) : (
                      <><CheckCircle2 className="w-4 h-4" /> Approve &amp; Execute Query</>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* ── 3. Error ──────────────────────────────────────────── */}
            {message.job?.status === 'error' && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
                <p className="font-black mb-1 uppercase text-xs tracking-widest">Analysis Failure</p>
                <p className="text-sm font-medium">{message.job.error_message}</p>
              </div>
            )}

            {/* ── 4. Done — Structured Output ───────────────────────── */}
            {message.job?.status === 'done' && (
              <div className="flex flex-col gap-5 animate-in fade-in slide-in-from-bottom-2 duration-700">

                {/* Insight Report */}
                {message.job.insight_report && (
                  <div className="relative">
                    <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-800/70">
                      <div className="w-1.5 h-1.5 rounded-full bg-sky-400 shadow-[0_0_6px_#38bdf8]" />
                      <span className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-400">Insight Report</span>
                      <button
                        onClick={toggleSpeech}
                        title={isSpeaking ? 'Stop Reading' : 'Read Aloud'}
                        className={`ml-auto p-1.5 rounded-lg border transition-all ${isSpeaking ? 'bg-indigo-600 border-indigo-500 text-white animate-pulse' : 'bg-transparent border-slate-700 text-slate-500 hover:text-white hover:border-indigo-500'}`}
                      >
                        {isSpeaking ? <VolumeX className="w-3 h-3" /> : <Volume2 className="w-3 h-3" />}
                      </button>
                    </div>
                    <div className="prose prose-invert prose-indigo max-w-none prose-sm prose-p:leading-relaxed prose-p:text-slate-300 prose-headings:text-white prose-strong:text-white prose-li:text-slate-300">
                      <MarkdownBlock content={message.job.insight_report} />
                    </div>
                  </div>
                )}

                {/* Strategic Recommendations */}
                {message.job.recommendations_json && message.job.recommendations_json.length > 0 && (
                  <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-2xl overflow-hidden">
                    <div className="px-4 py-3 bg-emerald-500/10 flex items-center gap-2 border-b border-emerald-500/20">
                      <Lightbulb className="w-4 h-4 text-emerald-400" />
                      <h4 className="text-[10px] font-black text-emerald-400 uppercase tracking-[0.18em]">Strategic Recommendations</h4>
                    </div>
                    <div className="p-4 flex flex-col gap-3">
                      {message.job.recommendations_json.map((rec: any, i: number) => (
                        <div key={i} className="flex gap-3 items-start p-3 rounded-xl bg-white/[0.03] border border-white/5 hover:border-emerald-500/20 transition-all">
                          <div className="shrink-0 w-6 h-6 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-[10px] font-black text-emerald-400">{i + 1}</div>
                          <div className="flex-1 min-w-0">
                            {typeof rec === 'string' ? (
                              <p className="text-sm text-slate-300 leading-relaxed">{rec}</p>
                            ) : (
                              <>
                                {rec.title && <p className="text-sm font-bold text-white mb-1">{rec.title}</p>}
                                {rec.description && <p className="text-sm text-slate-400 leading-relaxed">{rec.description}</p>}
                                {rec.action && (
                                  <p className="text-xs text-emerald-400 mt-1.5 flex items-center gap-1">
                                    <ChevronRight className="w-3 h-3" />{rec.action}
                                  </p>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Follow-up Suggestions */}
                {message.job.follow_up_suggestions && message.job.follow_up_suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest w-full mb-0.5">Suggested Follow-ups</span>
                    {message.job.follow_up_suggestions.map((q: string, i: number) => (
                      <div key={i} className="text-xs text-slate-400 bg-white/[0.04] border border-white/10 px-3 py-1.5 rounded-full hover:border-[var(--primary)]/40 hover:text-white transition-all cursor-default">
                        {q}
                      </div>
                    ))}
                  </div>
                )}

                {/* Global Intelligence Synthesis (Multi-Source) */}
                {message.job.synthesis_report && (
                  <div className="border border-indigo-500/30 bg-indigo-500/5 rounded-2xl overflow-hidden animate-in fade-in zoom-in duration-700">
                    <div className="p-3 bg-indigo-500/10 flex items-center gap-2 border-b border-indigo-500/20">
                      <Globe className="w-4 h-4 text-indigo-400" />
                      <h4 className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em]">Global Intelligence Synthesis</h4>
                    </div>
                    <div className="p-5 prose prose-invert prose-indigo max-w-none prose-sm leading-relaxed">
                      <MarkdownBlock content={message.job.synthesis_report} />
                    </div>
                  </div>
                )}

                {/* Visual Grounding (PDF pages) */}
                {message.job.visual_context && message.job.visual_context.length > 0 && (
                  <div>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-2">Visual Grounding</span>
                    <div className="flex gap-3 overflow-x-auto pb-2 custom-scroll">
                      {message.job.visual_context.map((ctx, idx) => (
                        <div
                          key={idx}
                          onClick={() => setSelectedImage(ctx.image_base64)}
                          className="shrink-0 group/thumb cursor-pointer relative"
                        >
                          <img
                            src={ctx.image_base64}
                            className="w-24 h-32 rounded-xl object-cover border border-slate-800 group-hover/thumb:border-[var(--primary)]/50 transition-all shadow-lg"
                          />
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 transition-opacity flex items-center justify-center rounded-xl">
                            <Eye className="w-5 h-5 text-white" />
                          </div>
                          <p className="text-[10px] font-black text-slate-500 uppercase mt-1.5 text-center tracking-widest">Pg {ctx.page_number}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Structured JSON */}
                {message.job.structured_data && (
                  <div className="bg-black/40 border border-slate-800 rounded-2xl p-4 overflow-hidden">
                    <div className="flex items-center gap-2 mb-3">
                      <Box className="w-3.5 h-3.5 text-pink-400" />
                      <h4 className="text-[10px] font-black text-pink-400 uppercase tracking-widest">Structured Intelligence Node</h4>
                    </div>
                    <pre className="text-[11px] font-mono text-slate-400 overflow-x-auto custom-scroll max-h-60">
                      {JSON.stringify(message.job.structured_data, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Chart / Superset Dashboard */}
                {message.job.chart_json && (
                  <div className="w-full rounded-2xl overflow-hidden border border-slate-700/50 shadow-xl">
                    <div className="px-4 py-2.5 bg-slate-900/60 border-b border-slate-800 flex items-center gap-2">
                      <BarChart2 className="w-3.5 h-3.5 text-violet-400" />
                      <span className="text-[10px] font-black uppercase tracking-widest text-violet-400">Live Analytics Dashboard</span>
                    </div>
                    <DynamicChart config={message.job.chart_json} />
                  </div>
                )}
              </div>
            )}

            {/* Fallback: no job */}
            {message.content && !message.job && (
              <p className="text-sm text-red-400">{message.content}</p>
            )}
          </div>
        )}
      </div>

      {/* Full-screen Visual Modal */}
      <AnimatePresence>
        {selectedImage && (
          <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-8 backdrop-blur-xl bg-black/80"
            onClick={() => setSelectedImage(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="relative max-w-5xl bg-[#171c2a] rounded-[32px] overflow-hidden border border-slate-700 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <img src={selectedImage} className="max-w-full max-h-[80vh] object-contain" alt="Visual grounding" />
              <div className="p-6 bg-slate-900/90 border-t border-slate-800 flex items-center justify-between">
                <span className="text-xs font-black text-slate-400 uppercase tracking-widest">
                  Page {message.job?.visual_context?.find(c => c.image_base64 === selectedImage)?.page_number} / {message.job?.visual_context?.length}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const idx = message.job?.visual_context?.findIndex(c => c.image_base64 === selectedImage) ?? 0;
                      if (idx > 0) setSelectedImage(message.job!.visual_context![idx - 1].image_base64);
                    }}
                    disabled={(message.job?.visual_context?.findIndex(c => c.image_base64 === selectedImage) ?? 0) === 0}
                    className="bg-white/5 hover:bg-white/10 disabled:opacity-20 text-white px-3 py-2 rounded-xl text-[10px] font-black uppercase transition-all"
                  >Prev</button>
                  <button
                    onClick={() => {
                      const idx = message.job?.visual_context?.findIndex(c => c.image_base64 === selectedImage) ?? 0;
                      if (idx < (message.job?.visual_context?.length ?? 0) - 1) setSelectedImage(message.job!.visual_context![idx + 1].image_base64);
                    }}
                    disabled={(message.job?.visual_context?.findIndex(c => c.image_base64 === selectedImage) ?? 0) === (message.job?.visual_context?.length ?? 0) - 1}
                    className="bg-white/5 hover:bg-white/10 disabled:opacity-20 text-white px-3 py-2 rounded-xl text-[10px] font-black uppercase transition-all"
                  >Next</button>
                  <div className="w-px h-6 bg-slate-800 mx-2" />
                  <button
                    onClick={() => setSelectedImage(null)}
                    className="bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2 rounded-xl text-[10px] font-black uppercase transition-all"
                  >Exit Vision</button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
