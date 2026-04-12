import { useState } from 'react';
import { LayoutDashboard, FileWarning, Hash, Type, Share2 } from 'lucide-react';
import MermaidViewer from '../Visualizations/MermaidViewer';
import CodeGraphVisualizer from '../Visualizations/CodeGraphVisualizer';
import { CodebaseAPI } from '../../services/api';
import type { CodeGraphResponse } from '../../services/api';
import { useAppStore } from '../../store/appStore';
import { useEffect } from 'react';

interface DataProfilerProps {
  schema: any;
}

export default function DataProfiler({ schema }: DataProfilerProps) {
  const { activeSourceIds } = useAppStore();
  const [activeTab, setActiveTab] = useState<'overview' | 'erd' | 'cleaning' | 'numeric' | 'categorical' | 'graph' | 'intelligence' | 'transcript'>('overview');
  const [graphData, setGraphData] = useState<CodeGraphResponse | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

  if (!schema) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        No profiling data available for this source.
      </div>
    );
  }

  // Robust SQL detection
  const isSQL = 
    schema.source_type === 'sql' || 
    schema.source_type === 'sqlite' || 
    schema.dialect === 'sqlite' || 
    (schema.tables && schema.tables.length > 0) ||
    (schema.mermaid_erd && schema.mermaid_erd.length > 10);

  const isCodebase = schema.source_type === 'codebase' || schema.type === 'codebase';
  const isImage = schema.source_type === 'image';
  const isAudio = schema.source_type === 'audio';
  const isVideo = schema.source_type === 'video';
  const isMedia = isImage || isAudio || isVideo;

  useEffect(() => {
    if (activeTab === 'graph' && !graphData && activeSourceIds.length === 1) {
      setGraphLoading(true);
      CodebaseAPI.getGraph(activeSourceIds[0])
        .then(res => setGraphData(res))
        .catch(err => console.error("Failed to fetch graph data", err))
        .finally(() => setGraphLoading(false));
    }
  }, [activeTab, graphData, activeSourceIds]);

  const columns = schema.columns || [];
  
  // Categorize columns with more robust filters for SQLite
  const numericCols = columns.filter((c: any) => {
    const dtype = (c.dtype || '').toLowerCase();
    return dtype.includes('int') || dtype.includes('float') || dtype.includes('number') || 
           dtype.includes('decimal') || dtype.includes('real') || dtype.includes('double');
  });
  
  const categoricalCols = columns.filter((c: any) => {
    const dtype = (c.dtype || '').toLowerCase();
    return dtype.includes('object') || dtype.includes('str') || dtype.includes('char') || 
           dtype.includes('text') || dtype.includes('varchar');
  });

  const totalMissing = columns.reduce((acc: number, c: any) => acc + (c.null_count || 0), 0);
  const rowCount = schema.row_count || 0;
  const colCount = schema.column_count || columns.length || 1;
  const totalCells = rowCount * colCount;
  const calculatedScore = totalCells > 0 ? Math.max(0, 100 - (totalMissing / totalCells * 100)) : 100;

  return (
    <div className="flex flex-col h-full bg-[#0a0d17]/50 rounded-[32px] border border-slate-800 backdrop-blur-3xl overflow-hidden shadow-2xl">
      {/* Header & Tabs */}
      <div className="border-b border-slate-800 bg-slate-900/40 p-4 shrink-0 px-6">
        <div className="flex items-center justify-between mb-4">
           <div>
              <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mb-1">Pillar Profiling Nexus</p>
              <h2 className="text-xl font-black text-white uppercase tracking-tight">Data Profile</h2>
           </div>
           {isSQL && (
             <span className="text-[8px] font-black bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded border border-indigo-500/20 uppercase tracking-[0.2em]">Relational Database Detected</span>
           )}
        </div>
        <div className="flex gap-2 pb-2 overflow-x-auto custom-scroll">
          <TabButton 
            active={activeTab === 'overview'} 
            onClick={() => setActiveTab('overview')} 
            icon={<LayoutDashboard className="w-4 h-4" />} 
            label="Overview" 
          />
          {isSQL && schema.mermaid_erd && (
            <TabButton 
              active={activeTab === 'erd'} 
              onClick={() => setActiveTab('erd')} 
              icon={<Share2 className="w-4 h-4" />} 
              label="Relational ERD" 
            />
          )}
          {isCodebase && (
            <TabButton 
              active={activeTab === 'graph'} 
              onClick={() => setActiveTab('graph')} 
              icon={<Share2 className="w-4 h-4" />} 
              label="Structural Graph" 
            />
          )}
          {isMedia && (
            <TabButton 
              active={activeTab === 'intelligence'} 
              onClick={() => setActiveTab('intelligence')} 
              icon={<LayoutDashboard className="w-4 h-4" />} 
              label="Intelligence" 
            />
          )}
          {(isAudio || isVideo) && (
            <TabButton 
              active={activeTab === 'transcript'} 
              onClick={() => setActiveTab('transcript')} 
              icon={<Type className="w-4 h-4" />} 
              label={isVideo ? "Events" : "Transcript"} 
            />
          )}
          {!isMedia && (
            <>
              <TabButton 
                active={activeTab === 'cleaning'} 
                onClick={() => setActiveTab('cleaning')} 
                icon={<FileWarning className="w-4 h-4" />} 
                label="Cleaning" 
              />
              <TabButton 
                active={activeTab === 'numeric'} 
                onClick={() => setActiveTab('numeric')} 
                icon={<Hash className="w-4 h-4" />} 
                label={`Numeric (${numericCols.length})`} 
              />
              <TabButton 
                active={activeTab === 'categorical'} 
                onClick={() => setActiveTab('categorical')} 
                icon={<Type className="w-4 h-4" />} 
                label={`Categorical (${categoricalCols.length})`} 
              />
            </>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6 custom-scroll">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 pb-2">
              <StatCard label={isSQL ? "Total Rows" : "Rows"} value={rowCount.toLocaleString() || 'N/A'} />
              <StatCard label={isSQL ? "Total Tables" : "Columns"} value={isSQL ? (schema.table_count || schema.tables?.length || 'N/A') : colCount} />
              <StatCard label="Missing Cells" value={totalMissing.toLocaleString()} />
              <StatCard label="Data Score" value={`${calculatedScore.toFixed(1)}%`} color={calculatedScore > 90 ? 'text-emerald-400' : 'text-amber-400'} />
            </div>

            {isMedia && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white/5 border border-slate-800 p-6 rounded-[24px]">
                   <p className="text-[10px] text-indigo-400 font-black uppercase tracking-widest mb-4">Strategic Summary</p>
                   <p className="text-sm text-slate-300 leading-relaxed italic">"{schema.description || schema.summary || 'Analyzing media content...'}"</p>
                </div>
                <div className="bg-white/5 border border-slate-800 p-6 rounded-[24px]">
                   <p className="text-[10px] text-indigo-400 font-black uppercase tracking-widest mb-4">Metadata Analysis</p>
                   <div className="space-y-3">
                      <div className="flex justify-between border-b border-slate-800/50 pb-2">
                         <span className="text-[10px] text-slate-500 font-black uppercase">Format</span>
                         <span className="text-[10px] text-white font-black uppercase">{schema.format || 'Detected'}</span>
                      </div>
                      {schema.dimensions && (
                        <div className="flex justify-between border-b border-slate-800/50 pb-2">
                           <span className="text-[10px] text-slate-500 font-black uppercase">Resolution</span>
                           <span className="text-[10px] text-white font-black uppercase">{schema.dimensions}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                         <span className="text-[10px] text-slate-500 font-black uppercase">Quality Grade</span>
                         <span className="text-[10px] text-emerald-400 font-black uppercase">High Fidelity / OCR Ready</span>
                      </div>
                   </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'intelligence' && (
           <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                 {(schema.tags || []).map((tag: string) => (
                    <span key={tag} className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-4 py-2 rounded-xl text-[10px] font-black uppercase text-center tracking-widest">
                       {tag}
                    </span>
                 ))}
              </div>

              {schema.detected_text && (
                 <div className="bg-slate-900/40 border border-slate-800/50 p-6 rounded-[24px]">
                    <p className="text-[10px] text-indigo-400 font-black uppercase tracking-widest mb-4">Detected Text (OCR)</p>
                    <div className="text-xs text-slate-400 font-mono bg-black/20 p-4 rounded-xl border border-slate-800/50 whitespace-pre-wrap">
                       {schema.detected_text}
                    </div>
                 </div>
              )}

              {isVideo && schema.events_preview && (
                 <div className="space-y-4">
                    <p className="text-[10px] text-indigo-400 font-black uppercase tracking-widest mb-4">Temporal Analysis Preview</p>
                    {schema.events_preview.map((ev: any, i: number) => (
                       <div key={i} className="flex gap-4 p-4 bg-white/5 border border-slate-800 rounded-2xl">
                          <span className="text-xs font-black text-indigo-400 tabular-nums shrink-0">{ev.time}</span>
                          <span className="text-xs text-slate-300 font-bold">{ev.event}</span>
                       </div>
                    ))}
                 </div>
              )}
           </div>
        )}

        {activeTab === 'transcript' && (
           <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900/40 border border-slate-800/50 p-8 rounded-[32px]">
                 <div className="flex items-center gap-4 mb-6">
                    <div className="w-10 h-10 rounded-full bg-indigo-500/10 flex items-center justify-center">
                       <Type className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div>
                       <p className="text-[10px] text-indigo-400 font-black uppercase tracking-widest">Natural Language Transcription</p>
                       <p className="text-xs text-slate-500 font-bold uppercase mt-1">Multi-modal AI Engine Output</p>
                    </div>
                 </div>
                 <div className="text-sm text-slate-300 leading-relaxed font-medium bg-black/20 p-6 rounded-2xl border border-slate-800/50">
                    {schema.transcript_preview || schema.summary || "No transcript available for this segment."}
                 </div>
              </div>
           </div>
        )}

        {activeTab === 'erd' && schema.mermaid_erd && (
          <div className="h-full space-y-4 animate-in fade-in zoom-in duration-300 flex flex-col">
            <div className="flex items-center justify-between px-2 shrink-0">
              <div>
                <p className="text-[10px] text-indigo-400 font-black uppercase tracking-widest">Entity Relationship Model</p>
                <p className="text-xs text-slate-500 font-bold uppercase mt-1">Multi-Table Schema Topology</p>
              </div>
              <span className="text-[8px] font-black bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded border border-indigo-500/20 uppercase tracking-[0.2em]">Live Generator</span>
            </div>
            <div className="flex-1 bg-black/20 rounded-3xl border border-slate-800/50 overflow-hidden relative">
               <MermaidViewer chart={schema.mermaid_erd} />
            </div>
          </div>
        )}

        {activeTab === 'cleaning' && (
          <div className="space-y-4">
            {columns.map((col: any) => (
              col.null_count > 0 && (
                <div key={col.name} className="flex items-center justify-between p-4 bg-red-500/5 border border-red-500/10 rounded-2xl">
                  <div>
                    <p className="font-bold text-white transition-colors uppercase tracking-tight">{col.name}</p>
                    <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none mt-1">Found Missing Values</p>
                  </div>
                  <span className="text-red-400 font-black tabular-nums">{col.null_count}</span>
                </div>
              )
            ))}
            {totalMissing === 0 && (
              <div className="p-12 text-center rounded-[32px] border border-emerald-500/10 bg-emerald-500/5 flex flex-col items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
                  <FileWarning className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <p className="text-xs font-black text-emerald-400 uppercase tracking-[0.2em]">Dataset Integrity: Optimized</p>
                  <p className="text-[10px] text-slate-500 font-bold uppercase mt-2">No missing values detected in the schema</p>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'numeric' && (
          <div className="space-y-6">
            {numericCols.map((col: any) => (
              <div key={col.name} className="bg-slate-900/40 p-5 rounded-[24px] border border-slate-800/50 hover:border-[var(--primary)]/30 transition-all">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-black text-[var(--primary)] text-sm uppercase tracking-tight">{col.name}</h3>
                  <span className="text-[10px] bg-slate-800 px-3 py-1 rounded-full text-slate-500 font-black uppercase tracking-widest">{col.dtype}</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <StatSub label="Unique" value={col.unique_count || 'N/A'} />
                  {col.mean !== undefined && <StatSub label="Mean" value={Number(col.mean).toFixed(2)} />}
                  {col.min !== undefined && <StatSub label="Min" value={col.min} />}
                  {col.max !== undefined && <StatSub label="Max" value={col.max} />}
                </div>
              </div>
            ))}
            {numericCols.length === 0 && (
               <div className="py-20 text-center flex flex-col items-center gap-4">
                 <Hash className="w-8 h-8 text-slate-800" />
                 <p className="text-[10px] text-slate-600 font-black uppercase tracking-widest">No numeric features detected</p>
               </div>
            )}
          </div>
        )}

        {activeTab === 'categorical' && (
          <div className="space-y-6">
            {categoricalCols.map((col: any) => (
              <div key={col.name} className="bg-slate-900/40 p-5 rounded-[24px] border border-slate-800/50 hover:border-[var(--primary)]/30 transition-all">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-black text-[var(--primary)] text-sm uppercase tracking-tight">{col.name}</h3>
                  <span className="text-[10px] bg-slate-800 px-3 py-1 rounded-full text-slate-500 font-black uppercase tracking-widest">{col.dtype}</span>
                </div>
                <div className="mb-4">
                  <p className="text-[8px] text-slate-600 font-black uppercase tracking-widest mb-1">Unique Cardinals</p>
                  <p className="text-xl font-black text-white tabular-nums">{col.unique_count || 'N/A'}</p>
                </div>
                {col.sample_values && col.sample_values.length > 0 && (
                  <div>
                    <p className="text-[8px] text-slate-600 font-black uppercase tracking-widest mb-2">Sample Spectrum</p>
                    <div className="flex flex-wrap gap-2">
                      {col.sample_values.slice(0, 5).map((val: any, idx: number) => (
                        <span key={idx} className="text-[10px] bg-slate-800/80 text-slate-400 px-2.5 py-1 rounded-lg font-bold uppercase tracking-tight">
                          {String(val)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {categoricalCols.length === 0 && (
               <div className="py-20 text-center flex flex-col items-center gap-4">
                 <Type className="w-8 h-8 text-slate-800" />
                 <p className="text-[10px] text-slate-600 font-black uppercase tracking-widest">No categorical features detected</p>
               </div>
            )}
          </div>
        )}

        {activeTab === 'graph' && (
          <div className="h-full animate-in fade-in zoom-in duration-500">
             <CodeGraphVisualizer data={graphData} loading={graphLoading} />
          </div>
        )}
      </div>
    </div>
  );
}

function StatSub({ label, value }: { label: string, value: any }) {
  return (
    <div>
      <p className="text-[8px] text-slate-600 font-black uppercase tracking-widest mb-1">{label}</p>
      <p className="text-sm font-black text-slate-300 tabular-nums leading-none">{value}</p>
    </div>
  );
}

function TabButton({ active, onClick, icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap
        ${active 
          ? 'bg-[var(--primary)] text-white shadow-xl shadow-[var(--primary)]/20' 
          : 'bg-white/5 text-slate-500 hover:bg-white/10 hover:text-slate-300'}`}
    >
      {icon}
      {label}
    </button>
  );
}

function StatCard({ label, value, color = 'text-white' }: { label: string, value: string | number, color?: string }) {
  return (
    <div className="bg-slate-900/40 border border-slate-800/50 p-6 rounded-[24px] flex flex-col justify-center items-center text-center group hover:border-[var(--primary)]/20 transition-all flex-1 min-w-[120px]">
      <span className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-2">{label}</span>
      <span className={`text-2xl font-black tabular-nums transition-colors ${color}`}>{value}</span>
    </div>
  );
}
