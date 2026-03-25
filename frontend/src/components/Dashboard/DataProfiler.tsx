import { useState } from 'react';
import { LayoutDashboard, FileWarning, Hash, Type } from 'lucide-react';

interface DataProfilerProps {
  schema: any;
}

export default function DataProfiler({ schema }: DataProfilerProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'cleaning' | 'numeric' | 'categorical'>('overview');

  if (!schema) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        No profiling data available for this source.
      </div>
    );
  }

  const columns = schema.columns || [];
  
  // Categorize columns
  const numericCols = columns.filter((c: any) => 
    c.dtype?.includes('int') || c.dtype?.includes('float') || c.dtype === 'number'
  );
  
  const categoricalCols = columns.filter((c: any) => 
    c.dtype?.includes('object') || c.dtype?.includes('str') || c.dtype === 'string'
  );

  const totalMissing = columns.reduce((acc: number, c: any) => acc + (c.null_count || 0), 0);
  const totalCells = (schema.row_count || 0) * (schema.column_count || columns.length || 1);
  const calculatedScore = totalCells > 0 ? Math.max(0, 100 - (totalMissing / totalCells * 100)) : 100;

  return (
    <div className="flex flex-col h-full bg-[#0a0d17]/50 rounded-[32px] border border-slate-800 backdrop-blur-3xl overflow-hidden shadow-2xl">
      {/* Header & Tabs */}
      <div className="border-b border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-xl font-black text-white mb-4 px-2 uppercase tracking-tight">Data Profile</h2>
        <div className="flex gap-2 px-2 overflow-x-auto custom-scroll pb-2">
          <TabButton 
            active={activeTab === 'overview'} 
            onClick={() => setActiveTab('overview')} 
            icon={<LayoutDashboard className="w-4 h-4" />} 
            label="Overview" 
          />
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
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6 custom-scroll">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Rows" value={schema.row_count || schema.total_documents || 'N/A'} />
            <StatCard label="Columns" value={schema.column_count || columns.length || 'N/A'} />
            <StatCard label="Missing Cells" value={totalMissing} />
            <StatCard label="Data Score" value={`${calculatedScore.toFixed(1)}%`} color={calculatedScore > 90 ? 'text-emerald-400' : 'text-amber-400'} />
          </div>
        )}

        {activeTab === 'cleaning' && (
          <div className="space-y-4">
            {columns.map((col: any) => (
              col.null_count > 0 && (
                <div key={col.name} className="flex items-center justify-between p-4 bg-red-500/5 border border-red-500/10 rounded-2xl">
                  <div>
                    <p className="font-bold text-white transition-colors">{col.name}</p>
                    <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none mt-1">Found Missing Values</p>
                  </div>
                  <span className="text-red-400 font-black tabular-nums">{col.null_count}</span>
                </div>
              )
            ))}
            {totalMissing === 0 && (
              <div className="p-12 text-center rounded-[32px] border border-emerald-500/10 bg-emerald-500/5">
                <p className="text-xs font-black text-emerald-400 uppercase tracking-[0.2em]">Dataset Integrity: Optimized</p>
                <p className="text-[10px] text-slate-500 font-bold uppercase mt-2">No missing values detected in the schema</p>
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
                {(col.hurst_exponent || col.change_points) && (
                  <div className="mt-4 pt-4 border-t border-slate-800/50 flex gap-4">
                    {col.hurst_exponent && (
                      <span className="text-[8px] font-black text-amber-400 bg-amber-400/10 px-2.5 py-1 rounded uppercase tracking-widest">
                        Hurst: {Number(col.hurst_exponent).toFixed(3)}
                      </span>
                    )}
                    {col.change_points && col.change_points.length > 0 && (
                      <span className="text-[8px] font-black text-red-400 bg-red-400/10 px-2.5 py-1 rounded uppercase tracking-widest">
                        {col.change_points.length} Anomaly Points
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
            {numericCols.length === 0 && <p className="text-slate-500 text-center py-8">No numeric columns found.</p>}
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
            {categoricalCols.length === 0 && <p className="text-slate-500 text-center py-8">No categorical columns found.</p>}
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
    <div className="bg-slate-900/40 border border-slate-800/50 p-6 rounded-[24px] flex flex-col justify-center items-center text-center group hover:border-[var(--primary)]/20 transition-all">
      <span className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-2">{label}</span>
      <span className={`text-2xl font-black tabular-nums transition-colors ${color}`}>{value}</span>
    </div>
  );
}
