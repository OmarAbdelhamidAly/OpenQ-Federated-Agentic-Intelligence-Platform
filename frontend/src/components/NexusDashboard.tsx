import React, { useState } from 'react';
import SourcePicker from './SourcePicker';
import { nexusApi, type AnalysisQueryRequest } from '../services/nexus.api';
const NexusDashboard: React.FC = () => {
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [question, setQuestion] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [_job, setJob] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const handleStartAnalysis = async () => {
    if (selectedSourceIds.length === 0 || !question.trim()) return;

    setIsAnalyzing(true);
    setResult(null);
    setLogs(['Initiating Strategic Nexus...', 'Initializing autonomous router...']);
    
    try {
      const queryData: AnalysisQueryRequest = {
        source_ids: selectedSourceIds,
        question: question,
      };

      const newJob = await nexusApi.submitQuery(queryData);
      setJob(newJob);
      
      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const status = await nexusApi.getJobStatus(newJob.id);
          setJob(status);
          
          if (status.status === 'done') {
            clearInterval(pollInterval);
            const finalResult = await nexusApi.getResult(newJob.id);
            setResult(finalResult);
            setIsAnalyzing(false);
          } else if (status.status === 'error') {
            clearInterval(pollInterval);
            setIsAnalyzing(false);
            setLogs(prev => [...prev, 'Analysis failed. Check worker logs.']);
          } else {
            // Simulate logs based on nodes if available
            if (status.thinking_steps?.length) {
              const lastNode = status.thinking_steps[status.thinking_steps.length - 1];
              setLogs(prev => [...prev, `[${lastNode.node}] ${lastNode.status}`]);
            }
          }
        } catch (pollErr) {
          console.error("Polling error", pollErr);
          clearInterval(pollInterval);
          setIsAnalyzing(false);
        }
      }, 3000);

    } catch (err) {
      console.error(err);
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="space-y-2">
        <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400">
          Strategic Intelligence Nexus
        </h1>
        <p className="text-slate-400 max-w-2xl text-lg">
          Cross-pillar autonomous reasoning. Select multiple data sources to discover hidden relationships and synthesize high-level strategic intelligence.
        </p>
      </header>

      <section className="space-y-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <span className="w-8 h-8 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">1</span>
          Select Intelligence Pillars
        </h2>
        <SourcePicker onSelectionChange={setSelectedSourceIds} />
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <span className="w-8 h-8 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">2</span>
          Define Objectives
        </h2>
        <div className="relative group">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a strategic question across your selected sources (e.g. 'How does the current code performance relate to the financial spikes in our SQL tables?')"
            className="w-full h-32 bg-slate-900 border-2 border-slate-800 rounded-2xl p-6 text-xl placeholder-slate-600 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all outline-none resize-none"
          />
          <button
            onClick={handleStartAnalysis}
            disabled={isAnalyzing || selectedSourceIds.length === 0 || !question.trim()}
            className={`absolute bottom-4 right-4 px-8 py-3 rounded-xl font-bold text-lg shadow-2xl transition-all ${
              isAnalyzing || selectedSourceIds.length === 0 || !question.trim()
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:scale-105 active:scale-95 text-white'
            }`}
          >
            {isAnalyzing ? (
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Orchestrating...
              </div>
            ) : 'Launch Nexus Intelligence'}
          </button>
        </div>
      </section>

      {isAnalyzing && (
        <section className="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-mono text-slate-500 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            Autonomous Reasoning Trace
          </h3>
          <div className="font-mono text-sm space-y-1">
            {logs.map((log, i) => (
              <p key={i} className="text-slate-400">
                <span className="text-slate-600 mr-2">[{i}]</span> {log}
              </p>
            ))}
          </div>
        </section>
      )}

      {result && (
        <section className="bg-slate-900/50 border border-slate-800 rounded-3xl p-8 space-y-6 animate-in zoom-in-95 duration-500">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-2xl">
              <span className="text-3xl">✨</span>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-slate-100">Strategic Intelligence Report</h3>
              <p className="text-slate-500 font-mono text-sm italic">Synthesized from {selectedSourceIds.length} Pillars</p>
            </div>
          </div>

          <div className="prose prose-invert max-w-none text-slate-300 leading-relaxed">
            {/* Simple Markdown-ish render */}
            {result.insight_report.split('\n').map((line: string, i: number) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default NexusDashboard;
