import { useState, useEffect, useMemo } from 'react';
import { AlertCircle, Loader2, TrendingUp } from 'lucide-react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';
const Plot = createPlotlyComponent(Plotly);

interface DynamicChartProps {
  config: any; 
}

export default function DynamicChart({ config }: DynamicChartProps) {
  const [loading, setLoading] = useState(true);
  const [error] = useState<string | null>(null);
  const isPlotly = config?.data && config?.layout; 

  useEffect(() => {
    setLoading(false);
  }, [config]);

  const plotlyLayout = useMemo(() => {
    if (!isPlotly) return null;
    return {
      ...config.layout,
      autosize: true,
      useResizeHandler: true,
      legend: {
        orientation: "h",
        yanchor: "bottom",
        y: -0.2,
        xanchor: "center",
        x: 0.5,
        bgcolor: "rgba(0,0,0,0)",
        font: { color: "#94a3b8", size: 10 }
      },
      margin: { l: 50, r: 20, t: 70, b: 80 },
    };
  }, [config, isPlotly]);

  if (loading) {
    return (
      <div className="w-full h-[450px] flex flex-col items-center justify-center bg-slate-900/10 border border-slate-800/20 rounded-[2rem] backdrop-blur-3xl relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent animate-pulse" />
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4 relative z-10" />
        <p className="text-slate-400 text-xs font-black uppercase tracking-[0.3em] animate-pulse relative z-10">Initializing Native Trace</p>
      </div>
    );
  }

  if (isPlotly) {
    return (
      <div className="w-full h-full min-h-[480px] p-6 rounded-[2rem] bg-[#0a0d17]/40 border border-white/5 shadow-2xl backdrop-blur-md relative animate-in fade-in zoom-in duration-1000 group">
         <div className="absolute top-6 left-8 flex items-center gap-2.5 z-10 pointer-events-none transition-transform group-hover:translate-x-1">
            <div className="w-2 h-2 rounded-full bg-indigo-500 shadow-[0_0_12px_#6366f1] animate-pulse" />
            <TrendingUp className="w-3.5 h-3.5 text-indigo-400/70" />
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-black">Analytical Intelligence Node</span>
         </div>
        
        <Plot
          data={config.data}
          layout={plotlyLayout as any}
          config={{ 
            responsive: true, 
            displayModeBar: false,
            frameMargins: 0.1
          }}
          style={{ width: "100%", height: "400px" }}
          className="mt-8 transition-opacity duration-1000"
        />
        
        <div className="absolute bottom-4 right-8 opacity-0 group-hover:opacity-100 transition-all duration-500 translate-y-2 group-hover:translate-y-0">
           <span className="text-[8px] font-black uppercase tracking-tighter text-indigo-500/40">Powered by Plotly.js Engine</span>
        </div>
      </div>
    );
  }


  return (
    <div className="p-16 border border-slate-800/60 rounded-[2.5rem] bg-slate-950/20 text-center backdrop-blur-sm relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-rose-500/5 to-transparent pointer-events-none" />
      <AlertCircle className="w-12 h-12 text-rose-500/30 mx-auto mb-6" />
      <h3 className="text-slate-200 font-black uppercase tracking-[0.15em] mb-2">Visualization Port Offline</h3>
      <p className="text-slate-500 text-xs italic max-w-xs mx-auto leading-relaxed">
        {error || "The analytical engine generated results, but the visualization format was incompatible with the primary rendering interface."}
      </p>
      <button className="mt-8 px-6 py-2 bg-slate-800 hover:bg-slate-700 text-[10px] font-black uppercase text-slate-400 hover:text-white rounded-xl transition-all border border-slate-700/50">
        Re-engage Analysis Engine
      </button>
    </div>
  );
}
