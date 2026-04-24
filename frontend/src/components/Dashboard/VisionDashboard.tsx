import React from 'react';
import { motion } from 'framer-motion';
import { 
  Camera, 
  Clock, 
  BrainCircuit,
  AlertCircle,
  Play,
  Loader2
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { useVision } from '../../hooks/useVision';

const VisionDashboard: React.FC = () => {
  const { cameras, loading } = useVision();
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const item = {
    hidden: { opacity: 0, scale: 0.95 },
    show: { opacity: 1, scale: 1 }
  };

  const engagementOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [
      {
        name: 'Engagement',
        type: 'pie',
        radius: ['60%', '80%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#0f172a', borderWidth: 5 },
        label: { show: false },
        data: [
          { value: 70, name: 'Focused', itemStyle: { color: '#22d3ee' } },
          { value: 20, name: 'Away', itemStyle: { color: '#6366f1' } },
          { value: 10, name: 'On Phone', itemStyle: { color: '#f43f5e' } },
        ]
      }
    ]
  };

  return (
    <motion.div 
      variants={container}
      initial="hidden"
      animate="show"
      className="p-8 space-y-8 max-w-7xl mx-auto"
    >
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-black text-white tracking-tight flex items-center gap-3">
            <BrainCircuit className="w-10 h-10 text-cyan-400" />
            Vision Intelligence
          </h1>
          <p className="text-slate-400 mt-2 font-medium">Real-time Employee Engagement & Spatial Analysis</p>
        </div>
        <div className="flex gap-4">
          <button className="bg-cyan-500/10 border border-cyan-500/20 px-6 py-2 rounded-xl text-cyan-400 font-black text-xs uppercase hover:bg-cyan-500/20 transition-all">
            Add Camera
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Cameras */}
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          {loading ? (
            <div className="col-span-2 flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
            </div>
          ) : cameras.length === 0 ? (
            <div className="col-span-2 flex flex-col items-center justify-center py-20 bg-slate-900/20 border border-dashed border-slate-800 rounded-[2rem]">
               <Camera className="w-10 h-10 text-slate-700 mb-4" />
               <p className="text-slate-500 font-bold uppercase text-xs">No active cameras found</p>
            </div>
          ) : cameras.map((cam, i) => (
            <motion.div 
              variants={item} 
              key={cam.id || i}
              className="bg-slate-900/40 border border-slate-800 rounded-[2rem] p-6 backdrop-blur-xl relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 p-4">
                 <div className={`w-2 h-2 rounded-full ${cam.status === 'active' ? 'bg-cyan-500 animate-pulse' : 'bg-slate-600'}`} />
              </div>
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center group-hover:bg-cyan-500/20 transition-colors">
                  <Camera className="w-6 h-6 text-cyan-400" />
                </div>
                <div>
                  <h4 className="font-black text-white">{cam.name}</h4>
                  <p className="text-[10px] font-black uppercase text-slate-500">{cam.status}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-800/40 p-3 rounded-2xl">
                  <p className="text-[10px] font-black text-slate-500 uppercase">Sampling</p>
                  <p className="text-xl font-black text-white">10 <span className="text-xs">SEC</span></p>
                </div>
                <div className="bg-slate-800/40 p-3 rounded-2xl">
                  <p className="text-[10px] font-black text-slate-500 uppercase">Status</p>
                  <p className="text-sm font-black text-white uppercase">{cam.status}</p>
                </div>
              </div>
              <button className="w-full mt-4 py-3 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-black text-white uppercase flex items-center justify-center gap-2 transition-all">
                <Play className="w-3 h-3 fill-white" /> View Stream
              </button>
            </motion.div>
          ))}
        </div>

        {/* Global Engagement */}
        <motion.div variants={item} className="bg-slate-900/40 border border-slate-800 p-8 rounded-[2rem] backdrop-blur-xl flex flex-col items-center">
          <h3 className="text-xl font-black text-white mb-8 w-full text-left">Global Engagement</h3>
          <ReactECharts option={engagementOption} style={{ height: '240px', width: '100%' }} />
          <div className="mt-8 space-y-4 w-full">
            <div className="flex justify-between items-center text-xs font-bold">
              <span className="text-cyan-400 flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-cyan-400"/> Focused</span>
              <span className="text-white">70%</span>
            </div>
            <div className="flex justify-between items-center text-xs font-bold">
              <span className="text-indigo-400 flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-indigo-400"/> Away</span>
              <span className="text-white">20%</span>
            </div>
            <div className="flex justify-between items-center text-xs font-bold">
              <span className="text-rose-400 flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-rose-400"/> On Phone</span>
              <span className="text-white">10%</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Recent Alerts */}
      <motion.div variants={item} className="bg-slate-900/40 border border-slate-800 p-8 rounded-[2rem] backdrop-blur-xl">
        <h3 className="text-xl font-black text-white mb-6 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-500" />
          Vision Anomalies
        </h3>
        <div className="space-y-4">
          {[
            { time: '10:45 AM', msg: 'Unauthorized person detected in Server Room', severity: 'High' },
            { time: '09:30 AM', msg: 'Extended "Away" state detected for Team Alpha', severity: 'Medium' },
          ].map((alert, i) => (
            <div key={i} className="flex items-center justify-between p-4 bg-rose-500/5 border border-rose-500/10 rounded-2xl">
              <div className="flex items-center gap-4">
                <Clock className="w-4 h-4 text-slate-500" />
                <div>
                  <p className="text-sm font-bold text-white">{alert.msg}</p>
                  <p className="text-[10px] font-black uppercase text-slate-500">{alert.time}</p>
                </div>
              </div>
              <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase ${alert.severity === 'High' ? 'bg-rose-500 text-white' : 'bg-amber-500 text-black'}`}>
                {alert.severity}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
};

export default VisionDashboard;
