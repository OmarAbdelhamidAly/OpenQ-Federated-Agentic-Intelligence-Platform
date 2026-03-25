import { CheckCircle2, CircleDashed, Loader2 } from 'lucide-react';

interface Step {
  node: string;
  status: string;
  timestamp: string;
}

interface Props {
  steps: Step[];
  isStreaming?: boolean;
}

const formatNodeName = (node: string) => {
  const mapping: Record<string, string> = {
    'starting_governance': 'Initializing Governance',
    'intake_analysis': 'Analyzing Intent & Scope',
    'safety_shield': 'Applying Safety Guardrails',
    'sql_generation': 'Generating SQL Query',
    'execute_query': 'Running Data Retrieval',
    'insight_generation': 'Synthesizing Insights',
  };
  return mapping[node] || node.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
};

export default function ThinkingIndicator({ steps, isStreaming }: Props) {
  return (
    <div className="flex flex-col gap-3 p-4 bg-[#171033]/50 border border-indigo-500/20 rounded-xl w-full">
      <div className="flex items-center gap-2 mb-2">
        {isStreaming ? (
           <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
        ) : (
           <CheckCircle2 className="w-4 h-4 text-green-400" />
        )}
        <span className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
          {isStreaming ? 'Autonomous Agents Analyzing...' : 'Analysis Complete'}
        </span>
      </div>
      
      <div className="flex flex-col gap-2 relative pl-2">
        {/* Connection Line */}
        <div className="absolute left-[11px] top-2 bottom-2 w-px bg-slate-700/50" />

        {steps.map((step, idx) => (
          <div key={`${step.node}-${idx}`} className="flex items-center gap-3 z-10 animate-in fade-in duration-500">
            <div className={`w-2 h-2 rounded-full ring-4 ring-[#171033] ${
              idx === steps.length - 1 && isStreaming 
                ? 'bg-purple-400 animate-pulse' 
                : 'bg-green-400'
            }`} />
            <span className={`text-sm ${
              idx === steps.length - 1 && isStreaming 
                ? 'text-purple-300 font-medium' 
                : 'text-slate-400'
            }`}>
              {formatNodeName(step.node)}
            </span>
          </div>
        ))}
        
        {isStreaming && (
          <div className="flex items-center gap-3 z-10 mt-1 opacity-70">
            <CircleDashed className="w-3 h-3 text-slate-500 animate-spin ml-[3px]" />
            <span className="text-xs text-slate-500">Processing next node...</span>
          </div>
        )}
      </div>
    </div>
  );
}
