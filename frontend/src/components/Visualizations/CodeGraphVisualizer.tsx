import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Loader2, Share2, ZoomIn } from 'lucide-react';
import type { CodeGraphResponse } from '../../services/api';

interface CodeGraphVisualizerProps {
  data: CodeGraphResponse | null;
  loading: boolean;
}

export default function CodeGraphVisualizer({ data, loading }: CodeGraphVisualizerProps) {
  const option = useMemo(() => {
    if (!data) return {};

    const categories = [
      { name: 'Directory', itemStyle: { color: '#facc15' } },
      { name: 'File', itemStyle: { color: '#60a5fa' } },
      { name: 'Class', itemStyle: { color: '#c084fc' } },
      { name: 'Function', itemStyle: { color: '#4ade80' } }
    ];

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        borderColor: 'rgba(51, 65, 85, 0.5)',
        textStyle: { color: '#f8fafc', fontSize: 12 },
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const node = params.data;
            return `
              <div class="p-2 min-w-[200px]">
                <div class="flex items-center gap-2 mb-1">
                  <div class="w-2 h-2 rounded-full" style="background-color: ${params.color}"></div>
                  <span class="text-[10px] uppercase font-black tracking-widest text-slate-500">${node.category}</span>
                </div>
                <div class="font-bold text-slate-200 mb-2">${node.name}</div>
                ${node.path ? `<div class="text-[10px] text-slate-400 font-mono mb-2 break-all">${node.path}</div>` : ''}
                ${node.summary ? `<div class="text-[11px] leading-relaxed text-slate-300 italic border-t border-slate-800 pt-2">${node.summary}</div>` : ''}
              </div>
            `;
          }
          return `${params.data.type || 'Connection'}`;
        }
      },
      legend: [
        {
          data: categories.map(c => c.name),
          orient: 'horizontal',
          bottom: 20,
          textStyle: { color: '#94a3b8', fontSize: 10, fontWeight: 'bold' }
        }
      ],
      series: [
        {
          type: 'graph',
          layout: 'force',
          data: data.nodes.map(n => ({
            id: n.id.toString(),
            name: n.name || n.path?.split('/').pop() || 'Unknown',
            path: n.path,
            summary: n.summary,
            category: n.type,
            symbolSize: n.type === 'Directory' ? 25 : n.type === 'File' ? 18 : 12,
            label: {
                show: n.type === 'Directory' || n.type === 'File',
                position: 'right',
                fontSize: 10,
                color: '#cbd5e1'
            }
          })),
          links: data.links.map(l => ({
            source: l.source.toString(),
            target: l.target.toString(),
            type: l.type,
            lineStyle: {
              color: l.type === 'CALLS' ? '#4ade80' : l.type === 'DEPENDS_ON' ? '#60a5fa' : '#334155',
              width: 1,
              opacity: 0.4,
              curveness: 0.1
            }
          })),
          categories: categories,
          roam: true,
          force: {
            repulsion: 150,
            edgeLength: 100,
            gravity: 0.1
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 4, opacity: 1 }
          }
        }
      ]
    };
  }, [data]);

  if (loading) {
    return (
      <div className="w-full h-[600px] flex flex-col items-center justify-center bg-slate-900/10 border border-slate-800/20 rounded-[2.5rem] backdrop-blur-3xl relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent animate-pulse" />
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4 relative z-10" />
        <p className="text-slate-400 text-xs font-black uppercase tracking-[0.3em] animate-pulse relative z-10">Mapping Knowledge Graph</p>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="w-full h-[600px] flex flex-col items-center justify-center bg-slate-900/10 border border-slate-800/20 rounded-[2.5rem] backdrop-blur-3xl text-center">
        <Share2 className="w-12 h-12 text-slate-700 mb-6" />
        <h3 className="text-slate-400 font-bold uppercase tracking-widest text-sm">No Graph Data Available</h3>
        <p className="text-slate-600 text-xs mt-2 max-w-xs">Once indexing is complete, the structural intelligence will manifest here.</p>
      </div>
    );
  }

  return (
    <div className="w-full h-[700px] p-6 rounded-[2.5rem] bg-[#0a0d17]/40 border border-white/5 shadow-2xl backdrop-blur-md relative group animate-in fade-in zoom-in duration-1000">
      <div className="absolute top-8 left-8 flex items-center gap-3 z-10 pointer-events-none">
        <div className="w-2 h-2 rounded-full bg-indigo-500 shadow-[0_0_12px_#6366f1] animate-pulse" />
        <ZoomIn className="w-3.5 h-3.5 text-indigo-400/70" />
        <span className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-black">Codebase Structural Topology</span>
      </div>

      <div className="absolute top-8 right-8 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="px-3 py-1 bg-slate-900/80 rounded-full border border-slate-800 text-[9px] text-slate-500 font-bold uppercase tracking-tighter">
            Graph: {data.nodes.length} nodes • {data.links.length} relationships
        </div>
      </div>

      <ReactECharts 
        option={option} 
        style={{ height: '100%', width: '100%' }}
        theme="dark"
        notMerge={true}
        lazyUpdate={true}
      />
      
      <div className="absolute bottom-6 right-10 opacity-40">
         <span className="text-[8px] font-black uppercase tracking-tighter text-indigo-500">Neural Network Visualization Engine</span>
      </div>
    </div>
  );
}
