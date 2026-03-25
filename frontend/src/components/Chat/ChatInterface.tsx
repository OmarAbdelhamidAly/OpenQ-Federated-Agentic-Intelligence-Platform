import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Loader2, Database, MessageSquare, Mic, Zap } from 'lucide-react';
import { AnalysisAPI, DataSourcesAPI, VoiceAPI } from '../../services/api';
import { recorder } from '../../utils/audio';
import MessageBubble from './MessageBubble';
import { useAnalysisPolling } from '../../hooks/useAnalysisPolling';
import type { Message } from '../../hooks/useAnalysisPolling';
import DataProfiler from '../Dashboard/DataProfiler';

interface ChatInterfaceProps {
  activeSourceIds: string[];
}

export default function ChatInterface({ activeSourceIds }: ChatInterfaceProps) {
  const [depthIndex, setDepthIndex] = useState(3);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [viewMode, setViewMode] = useState<'chat' | 'profile'>('chat');
  
  // Storage key based on active sources
  const storageKey = activeSourceIds.length > 0 ? `chat_history_${activeSourceIds.join('_')}` : null;

  // Load chat history from localStorage when source changes
  useEffect(() => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        try { setMessages(JSON.parse(saved)); } catch (e) { setMessages([]); }
      } else {
        setMessages([]);
      }
    } else {
      setMessages([]);
    }
  }, [storageKey]);

  // Save chat history to localStorage whenever it changes
  useEffect(() => {
    if (storageKey && messages.length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(messages));
    }
  }, [messages, storageKey]);
  const [schema, setSchema] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { isProcessing, setIsProcessing, startPolling } = useAnalysisPolling();

  const scrollToBottom = () => {
    if (viewMode === 'chat') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, viewMode]);

  useEffect(() => {
    if (activeSourceIds.length === 1) {
      DataSourcesAPI.get(activeSourceIds[0])
        .then(res => setSchema(res.schema_json))
        .catch(err => console.error("Failed to fetch schema", err));
    } else {
      setSchema(null);
      setViewMode('chat');
    }
  }, [activeSourceIds]);

  const onMessageUpdate = (id: string, updates: Partial<Message>) => {
    setMessages(prev => prev.map(msg => 
      msg.id === id ? { ...msg, ...updates } : msg
    ));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || activeSourceIds.length === 0 || isProcessing) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input };
    const systemId = (Date.now() + 1).toString();
    const systemMessage: Message = { id: systemId, role: 'assistant', isStreaming: true };

    setMessages(prev => [...prev, userMessage, systemMessage]);
    setInput('');

    try {
      const validHistory = messages

        .slice(-3)
        .map(m => ({ role: m.role, content: m.content || "" }));

      const { job_id } = await AnalysisAPI.submitQuery(
        userMessage.content!, 
        activeSourceIds[0], 
        activeSourceIds.length > 1 ? activeSourceIds : undefined,
        depthIndex,
        validHistory
      );
      await startPolling(job_id, systemId, onMessageUpdate, () => {});
    } catch (error) {
      console.error("Submit error", error);
      onMessageUpdate(systemId, { 
        content: "Sorry, there was an error submitting your request.", 
        isStreaming: false 
      });
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full relative z-0">
      {/* View Toggle - Only for single source profiling */}
      {activeSourceIds.length === 1 && (
        <div className="absolute top-4 right-8 z-10 flex gap-1 bg-[#171033]/60 backdrop-blur-xl p-1 border border-slate-700/50 rounded-2xl shadow-2xl">
          <button 
            onClick={() => setViewMode('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${viewMode === 'chat' ? 'bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/20' : 'text-slate-500 hover:text-slate-200'}`}
          >
            <MessageSquare className="w-3.5 h-3.5" /> Intelligence
          </button>
          <button 
            onClick={() => setViewMode('profile')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${viewMode === 'profile' ? 'bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/20' : 'text-slate-500 hover:text-slate-200'}`}
          >
            <Database className="w-3.5 h-3.5" /> Profiler
          </button>
        </div>
      )}

      {viewMode === 'profile' ? (
        <div className="flex-1 overflow-hidden p-8 pt-4 custom-scroll">
          <DataProfiler schema={schema} />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-4 pt-4 sm:px-8 xl:px-20 custom-scroll">
          {activeSourceIds.length === 0 ? (
            <EmptyStateSelectSource />
          ) : messages.length === 0 ? (
            <EmptyStateWelcome setInput={setInput} schema={schema} />
          ) : (
            <div className="max-w-5xl mx-auto space-y-8 pb-32">
              {Array.isArray(messages) && messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      )}

      <ChatInput 
        input={input}
        setInput={setInput}
        handleSubmit={handleSubmit}
        isProcessing={isProcessing}
        disabled={activeSourceIds.length === 0 || viewMode === 'profile'}
        depthIndex={depthIndex}
        setDepthIndex={setDepthIndex}
      />
    </div>
  );
}

// Sub-components for better readability
function EmptyStateSelectSource() {
  const steps = [
    { 
      id: "01", 
      title: "Target Sources", 
      ar: "حدد المصادر",
      desc: "Select CSV, SQL, or PDFs from the nexus sidebar to begin.",
      icon: <Database className="w-5 h-5" />
    },
    { 
      id: "02", 
      title: "Cross-Correlate", 
      ar: "ربط البيانات",
      desc: "OpenQ.AI automatically links disparate sources in memory.",
      icon: <Sparkles className="w-5 h-5" />
    },
    { 
      id: "03", 
      title: "Synthesize", 
      ar: "التركيب الذكي",
      desc: "Generate autonomous executive insights and unified reports.",
      icon: <Zap className="w-5 h-5" />
    }
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4 animate-in fade-in zoom-in duration-1000">
      <div className="mb-12">
        <div className="w-20 h-20 rounded-[32px] bg-[var(--primary)]/10 flex items-center justify-center mx-auto mb-6 relative">
            <div className="absolute -inset-4 bg-[var(--primary)]/5 blur-2xl rounded-full animate-pulse"></div>
            <Sparkles className="w-8 h-8 text-[var(--primary)] relative z-10" />
        </div>
        <h2 className="text-3xl font-black text-white tracking-tighter uppercase mb-2">Sovereign Intelligence</h2>
        <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.3em]">Autonomous Multi-Source Synthesis</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl w-full">
        {steps.map((step) => (
          <div key={step.id} className="p-6 bg-white/5 border border-slate-800/50 rounded-[32px] flex flex-col items-center gap-4 group hover:border-[var(--primary)]/30 hover:bg-[var(--primary)]/5 transition-all">
            <div className="w-10 h-10 rounded-2xl bg-slate-800 flex items-center justify-center text-slate-400 group-hover:bg-[var(--primary)] group-hover:text-white transition-all">
              {step.icon}
            </div>
            <div>
              <p className="text-[10px] font-black text-[var(--primary)] uppercase tracking-widest mb-1">Step {step.id}</p>
              <h4 className="font-black text-white uppercase text-sm mb-1">{step.title}</h4>
              <p className="text-[10px] text-slate-500 font-bold uppercase mb-3">{step.ar}</p>
              <p className="text-[11px] text-slate-400 leading-relaxed font-medium">{step.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 flex items-center gap-3 py-2 px-4 rounded-full bg-slate-900/50 border border-slate-800">
        <div className="w-2 h-2 rounded-full bg-[var(--primary)] animate-pulse" />
        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Awaiting Nexus Directive...</span>
      </div>
    </div>
  );
}

function EmptyStateWelcome({ setInput, schema }: { setInput: (v: string) => void, schema?: any }) {
  const suggestions: string[] = schema?.suggested_questions && schema.suggested_questions.length > 0 
    ? schema.suggested_questions 
    : [
    "Summarize key anomalies in this dataset",
    "Predict trends for the next fiscal quarter",
    "Identify cross-source correlations",
    "Analyze data quality and suggest fixes"
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
             <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest group-hover:text-[var(--primary)] mb-1">Inquiry Vector 0{i+1}</p>
             <p className="text-xs font-bold text-slate-300 group-hover:text-white">{s}</p>
           </button>
         ))}
      </div>
    </div>
  );
}

interface ChatInputProps {
  input: string;
  setInput: (val: string) => void;
  handleSubmit: (e: React.FormEvent) => void;
  isProcessing: boolean;
  disabled: boolean;
  depthIndex: number;
  setDepthIndex: (val: number) => void;
}

function ChatInput({ input, setInput, handleSubmit, isProcessing, disabled, depthIndex, setDepthIndex }: ChatInputProps) {
  const [isRecording, setIsRecording] = useState(false);

  const handleVoiceSearch = async () => {
    if (isRecording) {
      try {
        const blob = await recorder.stop();
        setIsRecording(false);
        const { text } = await VoiceAPI.stt(blob);
        if (text) setInput(text);
      } catch (e) {
        console.error("STT failed", e);
        setIsRecording(false);
      }
    } else {
      try {
        await recorder.start();
        setIsRecording(true);
      } catch (e) {
        console.error("Mic access failed", e);
        alert("Microphone access denied.");
      }
    }
  };

  const depths = [
    { value: 1, label: 'Fast', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { value: 3, label: 'Deep', color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
    { value: 5, label: 'Full Scan', color: 'text-red-400', bg: 'bg-red-500/10' }
  ];

  return (
    <div className="absolute bottom-0 w-full bg-gradient-to-t from-[#0a0d17] via-[#0a0d17]/95 to-transparent pt-20 pb-8 px-6 pointer-events-none">
      <div className="max-w-4xl mx-auto relative group pointer-events-auto">
        
        {/* Heritage Feature: Depth Index Pills */}
        {!disabled && (
          <div className="flex items-center justify-center gap-2 mb-4 animate-in fade-in slide-in-from-bottom-2">
            <div className="bg-[#171033]/60 backdrop-blur-xl p-1 border border-slate-700/50 rounded-2xl flex gap-1 shadow-2xl">
              {depths.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  onClick={() => setDepthIndex(d.value)}
                  className={`px-4 py-2 rounded-xl text-[9px] font-black uppercase tracking-[0.15em] transition-all ${depthIndex === d.value ? `${d.bg} ${d.color} shadow-lg shadow-indigo-500/10 scale-105` : 'text-slate-500 hover:text-slate-300'}`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="absolute -inset-1 bg-gradient-to-r from-[var(--primary)] to-[var(--primary-alt)] rounded-[32px] opacity-10 group-hover:opacity-20 blur-xl transition duration-500"></div>
        <form onSubmit={handleSubmit} className="relative flex items-center bg-[#0a0d17]/80 backdrop-blur-3xl border border-slate-800/50 rounded-[28px] p-2.5 shadow-2xl transition-all group-focus-within:border-[var(--primary)]/40">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isRecording ? "Listening to directive..." : !disabled ? "Execute a complex analytical inquiry..." : "Establish a data nexus to begin..."}
            disabled={disabled || isProcessing}
            className={`resize-none flex-1 bg-transparent text-slate-200 placeholder-slate-600 px-5 py-4 outline-none min-h-[64px] custom-scroll text-sm font-bold transition-all ${isRecording ? 'text-red-400' : ''}`}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <div className="flex items-center gap-2 pr-2">
            <button 
              type="button"
              onClick={handleVoiceSearch}
              disabled={disabled || isProcessing}
              className={`p-3.5 rounded-2xl transition-all ${isRecording ? 'text-red-500 bg-red-500/10 animate-pulse' : 'text-slate-600 hover:text-[var(--primary)] hover:bg-[var(--primary)]/10'}`}
            >
              {isRecording ? <Loader2 className="w-5 h-5 animate-spin" /> : <Mic className="w-5 h-5" />}
            </button>
            <button 
              type="submit"
              disabled={!input.trim() || disabled || isProcessing}
              className="p-4 bg-[var(--primary)] hover:brightness-110 text-white rounded-2xl shadow-xl shadow-[var(--primary)]/20 disabled:opacity-30 disabled:grayscale transition-all active:scale-95 flex items-center justify-center shrink-0"
            >
              {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
        </form>
        <div className="flex items-center justify-center gap-6 mt-4 opacity-40">
           <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Groq Llama-3.3-70B</p>
           <div className="w-1 h-1 rounded-full bg-slate-800"></div>
           <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Depth Index: {depths.find(d => d.value === depthIndex)?.label.toUpperCase()}</p>
        </div>
      </div>
    </div>
  );
}
