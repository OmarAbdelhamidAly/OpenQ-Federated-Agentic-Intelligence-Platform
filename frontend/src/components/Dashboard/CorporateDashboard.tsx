import React from 'react';
import { motion } from 'framer-motion';
import { 
  Building2, 
  Target, 
  ShieldCheck, 
  Users, 
  BarChart3, 
  TrendingUp,
  Network,
  Loader2
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { useCorporate } from '../../hooks/useCorporate';

const CorporateDashboard: React.FC = () => {
  const { stats, loading, error } = useCorporate();
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  const chartOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      axisLine: { lineStyle: { color: '#334155' } }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#1e293b' } },
      axisLine: { show: false }
    },
    series: [{
      data: [820, 932, 901, 934, 1290, 1330, 1320],
      type: 'line',
      smooth: true,
      color: '#10b981',
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(16, 185, 129, 0.3)' }, { offset: 1, color: 'rgba(16, 185, 129, 0)' }]
        }
      }
    }]
  };

  const StatCard = ({ icon: Icon, label, value, color }: any) => (
    <motion.div variants={item} className="bg-slate-900/40 border border-slate-800 p-6 rounded-3xl backdrop-blur-xl">
      <div className={`w-12 h-12 rounded-2xl ${color} flex items-center justify-center mb-4`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <p className="text-slate-400 text-sm font-bold uppercase tracking-wider">{label}</p>
      <h3 className="text-3xl font-black text-white mt-1">{value}</h3>
    </motion.div>
  );

  return (
    <motion.div 
      variants={container}
      initial="hidden"
      animate="show"
      className="p-8 space-y-8 max-w-7xl mx-auto"
    >
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-black text-white tracking-tight">Corporate Strategy</h1>
          <p className="text-slate-400 mt-2 font-medium">Governance, Hierarchy & Strategic Alignment</p>
        </div>
        <div className="bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-xl flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-emerald-500 text-xs font-black uppercase">Live Strategic Map</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard icon={Network} label="Org Nodes" value={stats.nodes} color="bg-indigo-500" />
        <StatCard icon={Target} label="Active Goals" value={stats.goals} color="bg-emerald-500" />
        <StatCard icon={ShieldCheck} label="Policies" value={stats.policies} color="bg-amber-500" />
        <StatCard icon={Users} label="Alignment" value="94%" color="bg-cyan-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div variants={item} className="lg:col-span-2 bg-slate-900/40 border border-slate-800 p-8 rounded-[2rem] backdrop-blur-xl">
          <div className="flex justify-between items-center mb-8">
            <h3 className="text-xl font-black text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-500" />
              Strategic Execution Trend
            </h3>
          </div>
          <ReactECharts option={chartOption} style={{ height: '300px' }} />
        </motion.div>

        <motion.div variants={item} className="bg-slate-900/40 border border-slate-800 p-8 rounded-[2rem] backdrop-blur-xl">
          <h3 className="text-xl font-black text-white mb-6">Hierarchy Insight</h3>
          <div className="space-y-4">
            {[
              { name: 'Engineering', status: 'High Alignment', progress: 92 },
              { name: 'Marketing', status: 'On Track', progress: 78 },
              { name: 'Operations', status: 'Requires Review', progress: 45 },
            ].map((node, i) => (
              <div key={i} className="p-4 bg-slate-800/40 rounded-2xl border border-slate-700/50">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold text-white">{node.name}</span>
                  <span className="text-[10px] font-black uppercase text-slate-500">{node.status}</span>
                </div>
                <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-emerald-500 rounded-full" 
                    style={{ width: `${node.progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default CorporateDashboard;
