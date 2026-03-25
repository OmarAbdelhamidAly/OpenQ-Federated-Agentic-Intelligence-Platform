import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  Brain, 
  UserCheck, 
  Play, 
  BarChart3, 
  FileText, 
  ShieldCheck, 
  Lightbulb, 
  RefreshCcw,
  Network,
  Database,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileJson,
  FileDown,
  Layers
} from 'lucide-react';
import React from 'react';

interface ThinkingStep {
  node: string;
  status: string;
  timestamp: string;
}

interface VisualizerProps {
  steps: ThinkingStep[];
  currentStatus: string;
  sourceType?: string;
}

interface EdgeDef {
  from: string;
  to: string;
  curve?: 'right' | 'left' | 'bottom';
}

interface Topology {
  nodes: Record<string, { x: number, y: number, label: string, icon: React.ReactNode }>;
  edges: EdgeDef[];
}

// ── Graph Topologies ────────────────────────────────────────────────────────────

const SQL_TOPOLOGY: Topology = {
  nodes: {
    data_discovery: { x: 100, y: 50, label: 'Data Discovery', icon: <Search className="w-5 h-5" /> },
    analysis_generator: { x: 300, y: 50, label: 'Analysis Strategy', icon: <Brain className="w-5 h-5" /> },
    backtrack: { x: 300, y: 150, label: 'Optimization Loop', icon: <RefreshCcw className="w-5 h-5" /> },
    human_approval: { x: 500, y: 50, label: 'Human Approval', icon: <UserCheck className="w-5 h-5" /> },
    execution: { x: 700, y: 50, label: 'Execution', icon: <Play className="w-5 h-5" /> },
    hybrid_fusion: { x: 700, y: 150, label: 'Context Fusion', icon: <Database className="w-5 h-5" /> },
    visualization: { x: 700, y: 250, label: 'Visualization', icon: <BarChart3 className="w-5 h-5" /> },
    insight: { x: 500, y: 250, label: 'Insight Extraction', icon: <Lightbulb className="w-5 h-5" /> },
    verifier: { x: 300, y: 250, label: 'AI Verification', icon: <ShieldCheck className="w-5 h-5" /> },
    recommendation: { x: 100, y: 250, label: 'Recommendation', icon: <Lightbulb className="w-5 h-5" /> },
    output_assembler: { x: 100, y: 150, label: 'Output Assembly', icon: <FileText className="w-5 h-5" /> },
  },
  edges: [
    { from: 'data_discovery', to: 'analysis_generator' },
    { from: 'analysis_generator', to: 'backtrack', curve: 'right' },
    { from: 'backtrack', to: 'analysis_generator', curve: 'left' },
    { from: 'analysis_generator', to: 'human_approval' },
    { from: 'human_approval', to: 'execution' },
    { from: 'execution', to: 'backtrack', curve: 'bottom' },
    { from: 'execution', to: 'hybrid_fusion' },
    { from: 'hybrid_fusion', to: 'visualization' },
    { from: 'visualization', to: 'insight' },
    { from: 'insight', to: 'verifier' },
    { from: 'verifier', to: 'recommendation' },
    { from: 'recommendation', to: 'output_assembler' },
  ]
};

const CSV_TOPOLOGY: Topology = {
  nodes: {
    data_discovery: { x: 100, y: 50, label: 'Data Discovery', icon: <Search className="w-5 h-5" /> },
    data_cleaning: { x: 300, y: 50, label: 'Auto-Cleaning', icon: <Layers className="w-5 h-5" /> },
    analysis: { x: 500, y: 50, label: 'CSV Analysis', icon: <Brain className="w-5 h-5" /> },
    visualization: { x: 700, y: 50, label: 'Visualization', icon: <BarChart3 className="w-5 h-5" /> },
    insight: { x: 700, y: 150, label: 'Insight', icon: <Lightbulb className="w-5 h-5" /> },
    recommendation: { x: 500, y: 150, label: 'Recommendation', icon: <Lightbulb className="w-5 h-5" /> },
    output_assembler: { x: 300, y: 150, label: 'Output Assembly', icon: <FileText className="w-5 h-5" /> },
  },
  edges: [
    { from: 'data_discovery', to: 'data_cleaning' },
    { from: 'data_discovery', to: 'analysis' },
    { from: 'data_cleaning', to: 'analysis' },
    { from: 'analysis', to: 'visualization' },
    { from: 'visualization', to: 'insight' },
    { from: 'insight', to: 'recommendation' },
    { from: 'recommendation', to: 'output_assembler' },
  ]
};

const JSON_TOPOLOGY: Topology = {
  nodes: {
    json_analysis: { x: 200, y: 100, label: 'JSON Parsing', icon: <FileJson className="w-5 h-5" /> },
    output_assembler: { x: 500, y: 100, label: 'Output Assembly', icon: <FileText className="w-5 h-5" /> },
  },
  edges: [
    { from: 'json_analysis', to: 'output_assembler' },
  ]
};

const PDF_TOPOLOGY: Topology = {
  nodes: {
    colpali_retrieval: { x: 200, y: 100, label: 'Visual RAG (ColPali)', icon: <FileDown className="w-5 h-5" /> },
    output_assembler: { x: 500, y: 100, label: 'Output Assembly', icon: <FileText className="w-5 h-5" /> },
  },
  edges: [
    { from: 'colpali_retrieval', to: 'output_assembler' },
  ]
};

// ── Component ──────────────────────────────────────────────────────────────────

export function LangGraphVisualizer({ steps, currentStatus, sourceType = 'sql' }: VisualizerProps) {
  // Select topology based on source type
  const topology = React.useMemo(() => {
    const type = (sourceType || 'sql').toLowerCase();
    if (type === 'csv') return CSV_TOPOLOGY;
    if (type === 'json') return JSON_TOPOLOGY;
    if (type === 'pdf') return PDF_TOPOLOGY;
    return SQL_TOPOLOGY; // Default to SQL for anything else
  }, [sourceType]);

  const getNodeStatus = (nodeId: string) => {
    const step = steps.find(s => s.node === nodeId);
    if (step) return step.status;
    if (currentStatus === 'done') return 'completed';
    return 'pending';
  };

  return (
    <div className="w-full bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-xl relative overflow-hidden group">
      {/* Background Decor */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(14,165,233,0.1),transparent)] opacity-50" />
      
      <div className="flex items-center justify-between mb-8 relative z-10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-sky-500/10 rounded-lg">
            <Network className="w-5 h-5 text-sky-400 animate-pulse" />
          </div>
          <div>
            <h3 className="text-white font-medium capitalize">{sourceType} Research Agent Flow</h3>
            <p className="text-slate-400 text-xs">Dynamic multi-service orchestration visualization</p>
          </div>
        </div>
        <div className="px-3 py-1 rounded-full bg-slate-800/50 border border-slate-700/50 text-[10px] text-slate-400 font-bold uppercase tracking-widest">
          {sourceType}
        </div>
      </div>

      <div className="relative w-full h-[320px] mb-6 select-none overflow-x-auto overflow-y-hidden no-scrollbar">
        <svg className="absolute inset-0 w-[800px] h-[300px]" style={{ minWidth: '800px' }}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#334155" />
            </marker>
            <marker id="arrow-active" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#0ea5e9" />
            </marker>
          </defs>

          {/* Render Edges */}
          {topology.edges.map((edge, i) => {
            const startNode = topology.nodes[edge.from];
            const endNode = topology.nodes[edge.to];
            if (!startNode || !endNode) return null;

            const isActive = getNodeStatus(edge.from) === 'completed' && getNodeStatus(edge.to) !== 'pending';
            
            // Generate path
            let d = `M ${startNode.x} ${startNode.y} L ${endNode.x} ${endNode.y}`;
            if (edge.curve === 'right') d = `M ${startNode.x+20} ${startNode.y} Q ${startNode.x+60} ${startNode.y+50} ${endNode.x} ${endNode.y-20}`;
            if (edge.curve === 'left') d = `M ${startNode.x-20} ${startNode.y} Q ${startNode.x-60} ${startNode.y-50} ${endNode.x} ${endNode.y+20}`;
            if (edge.curve === 'bottom') d = `M ${startNode.x} ${startNode.y+20} Q ${startNode.x} ${startNode.y+80} ${(topology.nodes.backtrack?.x || 0)+60} ${(topology.nodes.backtrack?.y || 0)}`;

            return (
              <motion.path
                key={i}
                d={d}
                stroke={isActive ? '#0ea5e9' : '#334155'}
                strokeWidth={isActive ? 2 : 1.5}
                fill="none"
                markerEnd={isActive ? 'url(#arrow-active)' : 'url(#arrow)'}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 1, delay: i * 0.1 }}
              />
            );
          })}

          {/* Render Nodes */}
          {Object.entries(topology.nodes).map(([id, node]) => {
            const status = getNodeStatus(id);
            const isCompleted = status === 'completed';
            const isRunning = status === 'running';

            return (
              <g key={id} transform={`translate(${node.x - 25}, ${node.y - 25})`}>
                <motion.rect
                  width={50}
                  height={50}
                  rx={12}
                  className={`${
                    isCompleted ? 'fill-sky-500/10 stroke-sky-500/40' : 
                    isRunning ? 'fill-sky-500/20 stroke-sky-400' : 
                    'fill-slate-800/40 stroke-slate-700/50'
                  }`}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  whileHover={{ scale: 1.1 }}
                />
                <foreignObject width={50} height={50}>
                  <div className={`w-full h-full flex items-center justify-center transition-colors duration-300 ${
                    isCompleted ? 'text-sky-400' : isRunning ? 'text-sky-300 animate-pulse' : 'text-slate-500'
                  }`}>
                    {node.icon}
                  </div>
                </foreignObject>
                
                {/* Node Label */}
                <foreignObject x={-40} y={55} width={130} height={40}>
                  <div className={`text-[10px] text-center font-medium px-1 rounded transition-colors duration-300 ${
                    isCompleted ? 'text-sky-400' : isRunning ? 'text-sky-300' : 'text-slate-500'
                  }`}>
                    {node.label}
                  </div>
                </foreignObject>

                {/* Status Indicator */}
                {isCompleted && (
                  <motion.circle
                    cx={45} cy={5} r={8}
                    className="fill-sky-500"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                  />
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Recent Activity List */}
      <div className="space-y-3 relative z-10 max-h-[120px] overflow-y-auto pr-2 custom-scrollbar">
        <AnimatePresence initial={false}>
          {steps.slice(-3).reverse().map((step, idx) => (
            <motion.div
              key={step.timestamp + idx}
              initial={{ x: -20, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center justify-between p-3 rounded-xl bg-slate-800/30 border border-slate-700/30"
            >
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${step.status === 'completed' ? 'bg-sky-500 shadow-[0_0_8px_#0ea5e9]' : 'bg-sky-400 animate-ping'}`} />
                <div className="flex flex-col">
                  <span className="text-[8px] font-black text-slate-500 uppercase tracking-widest">Logic Stream</span>
                  <span className="text-xs text-slate-200 font-bold capitalize">
                    {step.node === 'data_discovery' ? 'Signal Acquisition' : 
                     step.node === 'analysis_generator' ? 'Logic Synthesis' :
                     step.node === 'hybrid_fusion' ? 'Contextual Grounding' :
                     step.node === 'insight' ? 'Strategic Insight' :
                     step.node.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-3 h-3 text-slate-500" />
                <span className="text-[10px] text-slate-500">
                  {new Date(step.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                {step.status === 'completed' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                ) : step.status === 'error' ? (
                  <AlertCircle className="w-4 h-4 text-rose-500" />
                ) : (
                  <div className="w-4 h-4 rounded-full border-2 border-sky-500 border-t-transparent animate-spin" />
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
