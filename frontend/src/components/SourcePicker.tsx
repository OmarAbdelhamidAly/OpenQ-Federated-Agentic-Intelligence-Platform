import React, { useState, useEffect } from 'react';
import type { DataSource } from '../types';
import { DataSourcesAPI as dataSourcesApi } from '../services/api';

interface SourcePickerProps {
  onSelectionChange: (selectedIds: string[]) => void;
}

const SourcePicker: React.FC<SourcePickerProps> = ({ onSelectionChange }) => {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSources = async () => {
      try {
        const data = await dataSourcesApi.list();
        setSources(data);
      } catch (err) {
        console.error("Failed to fetch sources", err);
      } finally {
        setLoading(false);
      }
    };
    fetchSources();
  }, []);

  const toggleSource = (sid: string) => {
    const newSelection = selectedIds.includes(sid)
      ? selectedIds.filter(id => id !== sid)
      : [...selectedIds, sid];
    
    setSelectedIds(newSelection);
    onSelectionChange(newSelection);
  };

  if (loading) return <div className="p-4 text-slate-400">Loading sources...</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
      {sources.map((src: DataSource) => (
        <div 
          key={src.id}
          onClick={() => toggleSource(src.id)}
          className={`cursor-pointer p-4 rounded-xl border-2 transition-all duration-200 flex items-center justify-between ${
            selectedIds.includes(src.id) 
              ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/10' 
              : 'border-slate-800 bg-slate-900/50 hover:border-slate-700'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              selectedIds.includes(src.id) ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-400'
            }`}>
              <span className="text-xl">
                 {src.type === 'pdf' ? '📄' : src.type === 'sql' ? '🗄️' : src.type === 'csv' ? '📊' : src.type === 'image' ? '🖼️' : src.type === 'audio' ? '🎵' : src.type === 'video' ? '🎬' : src.type === 'json' ? '📦' : '💻'}
              </span>
            </div>
            <div>
              <p className="font-semibold text-slate-200 text-sm line-clamp-1">{src.name}</p>
              <p className="text-xs text-slate-500 uppercase font-mono">{src.type}</p>
            </div>
          </div>
          <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
            selectedIds.includes(src.id) ? 'border-blue-500 bg-blue-500' : 'border-slate-700'
          }`}>
             {selectedIds.includes(src.id) && <span className="text-white text-xs">✓</span>}
          </div>
        </div>
      ))}
    </div>
  );
};

export default SourcePicker;
