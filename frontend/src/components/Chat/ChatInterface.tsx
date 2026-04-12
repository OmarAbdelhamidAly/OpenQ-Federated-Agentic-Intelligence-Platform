import { useState, useRef, useEffect, useCallback } from 'react';
import { Database, MessageSquare, RefreshCw } from 'lucide-react';
import { AnalysisAPI, DataSourcesAPI } from '../../services/api';
import { useAppStore } from '../../store/appStore';
import type { AnalysisJob, Message } from '../../types';
import MessageBubble from './MessageBubble';
import { useAnalysisPolling } from '../../hooks/useAnalysisPolling';
import DataProfiler from '../Dashboard/DataProfiler';
import HITLCard from './HITLCard';
import ChatInput from './ChatInput';
import { EmptyStateSelectSource, EmptyStateWelcome } from './EmptyStates';

interface HITLState {
  jobId: string;
  job: AnalysisJob;
  isActing: boolean;
}

export default function ChatInterface() {
  const { activeSourceIds } = useAppStore();
  const depthIndex = 3;
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [viewMode, setViewMode] = useState<'chat' | 'profile'>('chat');
  const [hitlState, setHitlState] = useState<HITLState | null>(null);
  const [sessionId, setSessionId] = useState<string>('');

  // Storage key based on active sources
  const storageKey = activeSourceIds.length > 0 ? `chat_history_${activeSourceIds.join('_')}` : null;

  // Load chat history from localStorage when source changes
  useEffect(() => {
    setHitlState(null);
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        try {
          setMessages(JSON.parse(saved));
        } catch (e) {
          setMessages([]);
        }
      } else {
        setMessages([]);
      }
    } else {
      setMessages([]);
    }
  }, [storageKey]);

  // Generate a new session ID when sources change
  useEffect(() => {
    if (activeSourceIds.length > 0) {
      setSessionId(crypto.randomUUID());
    } else {
      setSessionId('');
    }
  }, [activeSourceIds]);

  // Save chat history to localStorage whenever it changes
  useEffect(() => {
    if (storageKey && messages.length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(messages));
    }
  }, [messages, storageKey]);

  const handleNewChat = () => {
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setHitlState(null);
    if (storageKey) {
      localStorage.removeItem(storageKey);
    }
  };

  const [schema, setSchema] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const userScrolledUp = useRef(false);
  const { isProcessing, setIsProcessing, startPolling } = useAnalysisPolling();

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    userScrolledUp.current = distanceFromBottom > 150;
  }, []);

  const scrollToBottom = useCallback(
    (force = false) => {
      if (viewMode !== 'chat') return;
      if (!force && userScrolledUp.current) return;
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    },
    [viewMode]
  );

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (viewMode === 'chat') {
      userScrolledUp.current = false;
      scrollToBottom(true);
    }
  }, [viewMode, scrollToBottom]);

  useEffect(() => {
    if (!isProcessing) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isProcessing]);

  useEffect(() => {
    if (activeSourceIds.length === 1) {
      DataSourcesAPI.get(activeSourceIds[0])
        .then((res) => setSchema(res.schema_json))
        .catch((err) => console.error('Failed to fetch schema', err));
    } else {
      setSchema(null);
      setViewMode('chat');
    }
  }, [activeSourceIds]);

  const onMessageUpdate = (id: string, updates: Partial<Message>) => {
    setMessages((prev) => prev.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg)));
  };

  const handleHITL = (jobId: string, job: AnalysisJob) => {
    setHitlState({ jobId, job, isActing: false });
  };

  const handleContinue = async () => {
    if (!hitlState) return;
    setHitlState((prev) => (prev ? { ...prev, isActing: true } : null));
    try {
      await AnalysisAPI.approveJob(hitlState.jobId);
      setHitlState(null);
      const continuedMsgId = Date.now().toString();
      const continuedMsg: Message = {
        id: continuedMsgId,
        role: 'assistant',
        isStreaming: true,
        job: { ...hitlState.job, status: 'running' },
      };
      setMessages((prev) => [...prev, continuedMsg]);
      await startPolling(hitlState.jobId, continuedMsgId, onMessageUpdate, () => {}, handleHITL);
    } catch (e) {
      console.error('Continue failed', e);
      setHitlState((prev) => (prev ? { ...prev, isActing: false } : null));
    }
  };

  const handleFinalize = async () => {
    if (!hitlState) return;
    setHitlState(null);
    const finalMsg: Message = {
      id: Date.now().toString(),
      role: 'assistant',
      isStreaming: false,
      job: { ...hitlState.job, status: 'done' },
      content: hitlState.job.synthesis_report || 'Analysis finalized with available insights.',
    };
    setMessages((prev) => [...prev, finalMsg]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || activeSourceIds.length === 0 || isProcessing) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input };
    const systemId = (Date.now() + 1).toString();
    const systemMessage: Message = { id: systemId, role: 'assistant', isStreaming: true };

    setMessages((prev) => [...prev, userMessage, systemMessage]);
    setHitlState(null);
    setInput('');

    try {
      const validHistory = messages
        .slice(-3)
        .map((m) => ({ role: m.role, content: m.content || '' }));

      const primarySourceId = activeSourceIds[0];
      const multiSourceIds = activeSourceIds.length > 1 ? activeSourceIds.slice(1) : undefined;

      const { job_id } = await AnalysisAPI.submitQuery(
        userMessage.content!,
        primarySourceId,
        multiSourceIds,
        depthIndex,
        validHistory,
        sessionId
      );
      await startPolling(job_id, systemId, onMessageUpdate, () => {}, handleHITL);
    } catch (error: any) {
      console.error('Submit error', error);
      let errorMessage = 'Sorry, there was an error submitting your request.';
      if (error.response) {
        if (error.response.status === 423) {
          errorMessage =
            error.response.data?.detail ||
            '⏳ PDF is still being indexed. Please wait before asking questions.';
        } else if (error.response.status === 422) {
          errorMessage =
            error.response.data?.detail || '❌ PDF indexing failed. Please re-upload the document.';
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }
      }
      onMessageUpdate(systemId, { content: errorMessage, isStreaming: false });
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full relative z-0 overflow-hidden bg-[#05070a]">
      {/* ── Background Ambiance ───────────────────────────────── */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10">
        <div className="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] bg-indigo-500/10 blur-[120px] rounded-full animate-blob opacity-60"></div>
        <div className="absolute bottom-[-10%] right-[-5%] w-[30%] h-[30%] bg-purple-500/10 blur-[100px] rounded-full animate-blob delay-1000 opacity-40"></div>
        <div className="absolute top-[30%] right-[10%] w-[20%] h-[20%] bg-sky-500/5 blur-[80px] rounded-full animate-blob delay-500"></div>
      </div>

      {/* New Chat Button */}
      {activeSourceIds.length > 0 && (
        <div className="absolute top-4 left-8 z-10 flex gap-1 bg-[#171033]/60 backdrop-blur-xl p-1 border border-slate-700/50 rounded-2xl shadow-2xl">
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all text-slate-500 hover:text-emerald-400 hover:bg-emerald-500/10"
          >
            <RefreshCw className="w-3.5 h-3.5" /> New Chat
          </button>
        </div>
      )}

      {/* View Toggle - Only for single source profiling */}
      {activeSourceIds.length === 1 && (
        <div className="absolute top-4 right-8 z-10 flex gap-1 bg-[#171033]/60 backdrop-blur-xl p-1 border border-slate-700/50 rounded-2xl shadow-2xl">
          <button
            onClick={() => setViewMode('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
              viewMode === 'chat'
                ? 'bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/20'
                : 'text-slate-500 hover:text-slate-200'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" /> Intelligence
          </button>
          <button
            onClick={() => setViewMode('profile')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
              viewMode === 'profile'
                ? 'bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/20'
                : 'text-slate-500 hover:text-slate-200'
            }`}
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
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-4 py-4 pt-4 sm:px-8 xl:px-20 custom-scroll"
        >
          {activeSourceIds.length === 0 ? (
            <EmptyStateSelectSource />
          ) : messages.length === 0 ? (
            <EmptyStateWelcome setInput={setInput} schema={schema} />
          ) : (
            <div className="max-w-full xl:max-w-[95%] mx-auto space-y-8 pb-64 px-2">
              {Array.isArray(messages) &&
                messages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    onApproveSuccess={() => {
                      if (msg.job?.id) {
                        startPolling(msg.job.id, msg.id, onMessageUpdate, () => {}, handleHITL);
                      }
                    }}
                  />
                ))}

              {/* ── HITL Approval Card ───────────────────────────────── */}
              {hitlState && (
                <HITLCard
                  job={hitlState.job}
                  isActing={hitlState.isActing}
                  onContinue={handleContinue}
                  onFinalize={handleFinalize}
                />
              )}

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
        disabled={activeSourceIds.length === 0 || viewMode === 'profile' || !!hitlState}
        inputRef={inputRef}
      />
    </div>
  );
}
