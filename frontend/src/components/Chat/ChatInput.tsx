import { useState } from 'react';
import { Send, Mic, Loader2 } from 'lucide-react';
import { VoiceAPI } from '../../services/api';
import { recorder } from '../../utils/audio';

interface ChatInputProps {
  input: string;
  setInput: (val: string) => void;
  handleSubmit: (e: React.FormEvent) => void;
  isProcessing: boolean;
  disabled: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
}

export default function ChatInput({
  input,
  setInput,
  handleSubmit,
  isProcessing,
  disabled,
  inputRef,
}: ChatInputProps) {
  const [isRecording, setIsRecording] = useState(false);

  const handleVoiceSearch = async () => {
    if (isRecording) {
      try {
        const blob = await recorder.stop();
        setIsRecording(false);
        const { text } = await VoiceAPI.stt(blob);
        if (text) setInput(text);
      } catch (e) {
        console.error('STT failed', e);
        setIsRecording(false);
      }
    } else {
      try {
        await recorder.start();
        setIsRecording(true);
      } catch (e) {
        console.error('Mic access failed', e);
        alert('Microphone access denied.');
      }
    }
  };

  return (
    <div className="absolute bottom-0 w-full bg-gradient-to-t from-[#0a0d17] via-[#0a0d17]/95 to-transparent pt-20 pb-8 px-6 pointer-events-none">
      <div className="max-w-full xl:max-w-[80%] mx-auto relative group pointer-events-auto px-4">
        <div className="absolute -inset-1.5 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-[34px] opacity-10 group-focus-within:opacity-40 group-hover:opacity-25 blur-2xl transition-all duration-700"></div>
        <form
          onSubmit={handleSubmit}
          className="relative flex items-center bg-[#0d111c]/90 backdrop-blur-3xl border border-white/5 rounded-[28px] p-2.5 shadow-[0_20px_50px_rgba(0,0,0,0.5)] transition-all group-focus-within:border-indigo-500/50 group-focus-within:bg-[#0a0d17]"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              disabled && !isProcessing
                ? 'Awaiting command — respond to the checkpoint above...'
                : isProcessing
                ? 'Processing... you can type your next question'
                : isRecording
                ? 'Listening to directive...'
                : 'Execute a complex analytical inquiry...'
            }
            disabled={disabled}
            className={`resize-none flex-1 bg-transparent text-slate-200 placeholder-slate-600 px-5 py-4 outline-none min-h-[64px] custom-scroll text-sm font-bold transition-all ${
              isRecording ? 'text-red-400' : ''
            } ${disabled ? 'opacity-40' : ''}`}
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
              className={`p-3.5 rounded-2xl transition-all ${
                isRecording
                  ? 'text-red-500 bg-red-500/10 animate-pulse'
                  : 'text-slate-600 hover:text-[var(--primary)] hover:bg-[var(--primary)]/10'
              }`}
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
        <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Groq Llama-3.3-70B</p>
      </div>
    </div>
  );
}
