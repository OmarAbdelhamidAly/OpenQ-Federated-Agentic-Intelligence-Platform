import { useState, useEffect } from 'react';
import { DataSourcesAPI, AnalysisAPI } from '../../services/api';
import type { DataSource, AnalysisJob, PortalType } from '../../types';
import { useAppStore } from '../../store/appStore';
import { 
  FileText, 
  Database, 
  BookOpen, 
  Box, 
  TrendingUp, 
  Activity, 
  Clock, 
  ChevronRight,
  Search,
  Upload,
  X,
  Target,
  Code,
  Image as ImageIcon,
  Film,
  Mic
} from 'lucide-react';

interface PortalDashboardProps {
  type: PortalType;
}

export default function PortalDashboard({ type }: PortalDashboardProps) {
  const { selectSource } = useAppStore();
  const [sources, setSources] = useState<DataSource[]>([]);
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Two-Stage Upload Flow State
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploadCategory, setUploadCategory] = useState<string>('Finance');
  const [uploadAssetType, setUploadAssetType] = useState<string>('Select Type');
  const [indexingMode, setIndexingMode] = useState<'deep_vision' | 'fast_text' | 'hybrid_ocr' | 'strategic_nexus'>('strategic_nexus');
  const [uploading, setUploading] = useState(false);

  const TAXONOMY: Record<string, { label: string, types: { slug: string, label: string }[] }> = {
    "Finance": {
      label: "Finance & Accounting",
      types: [
        { slug: "invoice", label: "Invoice / Receipt" },
        { slug: "financial_report", label: "Financial Report" },
        { slug: "tax_return", label: "Tax Return / Declaration" },
        { slug: "bank_statement", label: "Bank / Account Statement" },
        { slug: "purchase_order", label: "Purchase Order" }
      ]
    },
    "Legal": {
      label: "Legal & Compliance",
      types: [
        { slug: "contract", label: "Legal Contract / Agreement" },
        { slug: "nda", label: "Non-Disclosure Agreement" },
        { slug: "policy", label: "Policy / Compliance Document" },
        { slug: "audit_report", label: "Audit / Compliance Report" }
      ]
    },
    "HR": {
      label: "Human Resources",
      types: [
        { slug: "hr_record", label: "HR / Personnel Record" },
        { slug: "resume", label: "Resume / CV" },
        { slug: "perf_review", label: "Performance Review" }
      ]
    },
    "Medical": {
      label: "Medical & Healthcare",
      types: [
        { slug: "medical_record", label: "Medical / Clinical Record" },
        { slug: "prescription", label: "Medical Prescription" },
        { slug: "lab_result", label: "Lab / Test Result" }
      ]
    },
    "Tech": {
      label: "Tech & Engineering",
      types: [
        { slug: "tech_spec", label: "Technical Specification" },
        { slug: "api_doc", label: "API / Developer Documentation" },
        { slug: "arch_diagram", label: "Architecture Diagram / Doc" }
      ]
    },
    "Logistics": {
      label: "Logistics & Supply Chain",
      types: [
        { slug: "bill_of_lading", label: "Bill of Lading" },
        { slug: "customs_decl", label: "Customs Declaration" },
        { slug: "inventory", label: "Inventory / Stock Report" }
      ]
    },
    "RealEstate": {
      label: "Real Estate",
      types: [
        { slug: "lease_agreement", label: "Lease / Rental Agreement" },
        { slug: "property_deed", label: "Property Deed / Title" }
      ]
    },
    "Construction": {
      label: "Construction & Engineering",
      types: [
        { slug: "floor_plan", label: "Floor Plan / Blueprint" }
      ]
    },
    "Business": {
      label: "General Business",
      types: [
        { slug: "business_report", label: "Business / Strategy Report" },
        { slug: "meeting_minutes", label: "Meeting Minutes" }
      ]
    },
    "Marketing": {
      label: "Marketing & Strategy",
      types: [
        { slug: "marketing_mat", label: "Marketing Material / Deck" }
      ]
    },
    "Literature": {
      label: "Literature & Education",
      types: [
        { slug: "other_book", label: "Book / E-Book" },
        { slug: "other_manual", label: "Instruction Manual" }
      ]
    },
    "Academic": {
      label: "Academic & Research",
      types: [
        { slug: "other_research", label: "Research Paper" },
        { slug: "other_article", label: "News Article / Blog" }
      ]
    },
    "Other": {
      label: "Other / Custom",
      types: [
        { slug: "other_misc", label: "General Document" }
      ]
    }
  };
  
  const DOMAINS = [
    { title: "Finance & Accounting", desc: "Balance sheets, tax, and audit trails." },
    { title: "Legal & Compliance", desc: "Contracts, NDAs, and regulatory filings." },
    { title: "Human Resources", desc: "Personnel records, resumes, and reviews." },
    { title: "Strategic Planning", desc: "Market research and business plans." }
  ];

  const ASSET_TYPES = [
    { title: "Financial Statement", desc: "High-precision fiscal data." },
    { title: "Legal Agreement", desc: "Binding contractual documentation." },
    { title: "Technical Spec", desc: "Engineering and architectural logic." },
    { title: "Strategic Report", desc: "Deep-market insights and analysis." }
  ];

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    
    // For PDF, we use header state. For others, we might still want the modal.
    if (type === 'pdf') {
      try {
        setUploading(true);
        const combinedHint = uploadAssetType; // Send just the SLUG for deterministic lookup
        await DataSourcesAPI.upload(file, combinedHint, indexingMode);
        setRefreshTrigger(prev => prev + 1);
      } catch (error) {
        console.error('Failed to upload file', error);
        alert('Upload failed.');
      } finally {
        setUploading(false);
        e.target.value = '';
      }
    } else {
      setPendingFile(file);
      setUploadCategory('Strategic Domain');
      setUploadAssetType('Analytical Report');
      e.target.value = ''; 
    }
  };

  const confirmUpload = async () => {
    if (!pendingFile) return;
    try {
      setUploading(true);
      const combinedHint = `Industry: ${uploadCategory} | Type: ${uploadAssetType}`;
      await DataSourcesAPI.upload(pendingFile, combinedHint);
      setRefreshTrigger(prev => prev + 1);
      setPendingFile(null);
    } catch (error) {
      console.error('Failed to upload file', error);
      alert('Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const portalConfig = {
    csv: { title: "CSV Center", icon: FileText, color: "indigo", desc: "Tabular Intelligence" },
    sql: { title: "SQL Oracle", icon: Database, color: "indigo", desc: "Relational Engine" },
    pdf: { title: "PDF Insight", icon: BookOpen, color: "red", desc: "Document Vision" },
    json: { title: "JSON Mapper", icon: Box, color: "orange", desc: "Object Graph" },
    codebase: { title: "Codebase Context", icon: Code, color: "emerald", desc: "Software Architecture" },
    image: { title: "Vision Analytics", icon: ImageIcon, color: "fuchsia", desc: "Spatial Insight" },
    audio: { title: "Audio Intersect", icon: Mic, color: "pink", desc: "Acoustic Intelligence" },
    video: { title: "Video Spatial", icon: Film, color: "purple", desc: "Temporal Analysis" },
  }[type];

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [srcs, hist] = await Promise.all([
          DataSourcesAPI.list(),
          AnalysisAPI.getHistory()
        ]);
        // Map 'document' type from API to 'pdf' in UI
        const filtered = srcs.filter(s => {
          if (type === 'pdf') return s.type === 'document' || s.type === 'pdf';
          return s.type === type;
        });
        setSources(filtered);
        setJobs(hist);
      } catch (e) {
        console.error("Failed to load portal data", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [type, refreshTrigger]);

  const healthStatus = jobs.some(j => j.status === 'error') ? "DEGRADED" : "OPTIMAL";
  const healthColor = healthStatus === "OPTIMAL" ? "text-emerald-400" : "text-amber-400";

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--primary)]/20 border-t-[var(--primary)] rounded-full animate-spin"></div>
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Synchronizing Portal...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto custom-scroll bg-[#0a0d17]/50">
      {/* Header Section */}
      <div className="p-8 pb-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[var(--primary)]/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2"></div>
        
        <div className="relative z-10 flex items-end justify-between">
          <div>
             <div className="flex items-center gap-3 mb-4">
                <div className={`p-2 rounded-xl bg-[var(--primary)]/10 border border-[var(--primary)]/20`}>
                   <portalConfig.icon className={`w-5 h-5 text-[var(--primary)]`} />
                </div>
                <span className="text-[10px] font-black text-[var(--primary)] uppercase tracking-[0.3em]">{portalConfig.desc}</span>
             </div>
             <h1 className="text-4xl font-black text-white tracking-tight">{portalConfig.title}</h1>
             <p className="text-slate-400 mt-2 font-medium max-w-xl">
               Manage, audit, and extract autonomous insights from your {type.toUpperCase()} data streams.
             </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
             {type === 'pdf' && (
               <>
                 <select 
                   value={uploadCategory}
                   onChange={(e) => {
                     setUploadCategory(e.target.value);
                     setUploadAssetType('Select Type');
                   }}
                   className="bg-black/40 border border-slate-700/50 rounded-xl px-4 py-3 text-sm font-bold text-white focus:outline-none focus:border-indigo-500/50 transition-all min-w-[200px] appearance-none cursor-pointer"
                 >
                   {Object.keys(TAXONOMY).map(key => <option key={key} value={key}>{TAXONOMY[key].label}</option>)}
                 </select>
 
                  <select 
                    value={uploadAssetType}
                    onChange={(e) => setUploadAssetType(e.target.value)}
                    className={`bg-black/40 border rounded-xl px-4 py-3 text-sm font-bold text-white focus:outline-none transition-all min-w-[200px] appearance-none cursor-pointer ${
                      uploadAssetType === 'Select Type' ? 'border-amber-500/50 text-amber-200/50' : 'border-slate-700/50'
                    }`}
                  >
                    <option disabled value="Select Type">Select Type</option>
                    {TAXONOMY[uploadCategory]?.types?.map(t => <option key={t.slug} value={t.slug}>{t.label}</option>)}
                  </select>

                  <div className="flex bg-black/40 border border-slate-700/50 p-1 rounded-2xl gap-1">
                    <button
                      onClick={() => setIndexingMode('deep_vision')}
                      className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                        indexingMode === 'deep_vision' 
                          ? 'bg-[var(--primary)] text-white shadow-lg' 
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Semantic
                    </button>
                    <button
                      onClick={() => setIndexingMode('fast_text')}
                      className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                        indexingMode === 'fast_text' 
                          ? 'bg-[var(--primary)] text-white shadow-lg' 
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Fast
                    </button>
                    <button
                      onClick={() => setIndexingMode('hybrid_ocr')}
                      className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                        indexingMode === 'hybrid_ocr' 
                          ? 'bg-[var(--primary)] text-white shadow-lg' 
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Hybrid
                    </button>
                    <button
                      onClick={() => setIndexingMode('strategic_nexus')}
                      className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                        indexingMode === 'strategic_nexus' 
                          ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/20' 
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Strategic
                    </button>
                  </div>
                </>
              )}

              {type === 'pdf' ? (
                <button
                  onClick={() => {
                    if (uploadAssetType === 'Select Type') {
                      alert("⚠️ Strategic Protocols Required: Please select a specific Document Classification before initializing analysis.");
                      return;
                    }
                    document.getElementById('pdf-upload-input')?.click();
                  }}
                  disabled={uploading}
                  className="bg-[var(--primary)] hover:brightness-110 border border-white/10 px-6 py-3 rounded-2xl text-sm font-bold text-white transition-all cursor-pointer flex items-center gap-2 group shadow-xl shadow-[var(--primary)]/20 disabled:opacity-50"
                >
                  <Upload className="w-4 h-4 text-white/70 group-hover:text-white transition-colors" /> 
                  <span>{uploading ? "Analyzing..." : `Analyze PDF`}</span>
                  <input 
                    id="pdf-upload-input"
                    type="file" 
                    className="hidden" 
                    onChange={handleFileSelect} 
                    accept=".pdf"
                  />
                </button>
              ) : (
                <label className="bg-[var(--primary)] hover:brightness-110 border border-white/10 px-6 py-3 rounded-2xl text-sm font-bold text-white transition-all cursor-pointer flex items-center gap-2 group shadow-xl shadow-[var(--primary)]/20">
                   <Upload className="w-4 h-4 text-white/70 group-hover:text-white transition-colors" /> 
                   <span>{uploading ? "Analyzing..." : `Analyze ${type.toUpperCase()}`}</span>
                   <input 
                     type="file" 
                     disabled={uploading}
                     className="hidden" 
                     onChange={handleFileSelect} 
                     accept={
                       type === 'csv' ? '.csv,.xlsx' : 
                       type === 'sql' ? '.sqlite,.db,.sql' : 
                       type === 'codebase' ? '.zip' : 
                       '.json'
                     } 
                   />
                </label>
              )}
          </div>
        </div>
      </div>

      {/* Grid Content */}
      <div className="px-8 pb-12 grid grid-cols-12 gap-6">
        
        {/* Stats Column */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] p-6 backdrop-blur-xl">
            <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6">Portal Intelligence</h3>
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                    <Activity className="w-5 h-5" />
                  </div>
                  <span className="text-sm font-bold text-slate-300">Active Streams</span>
                </div>
                <span className="text-2xl font-black text-white tabular-nums">{sources.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <span className="text-sm font-bold text-slate-300">Jobs Executed</span>
                </div>
                <span className="text-2xl font-black text-white tabular-nums">{jobs.filter(j => j.status === 'done').length}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-500">
                    <Clock className="w-5 h-5" />
                  </div>
                  <span className="text-sm font-bold text-slate-300">Health Status</span>
                </div>
                <span className={`text-xs font-black uppercase tracking-widest ${healthColor}`}>{healthStatus}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Main List Column */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] overflow-hidden backdrop-blur-xl">
            <div className="p-6 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Connected Assets</h3>
              <div className="relative">
                 <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
                 <input type="text" placeholder="Filter assets..." className="bg-black/20 border border-slate-800 rounded-lg py-1.5 pl-9 pr-4 text-xs font-bold text-white focus:outline-none focus:border-indigo-500/40 transition-all w-48" />
              </div>
            </div>
            
            <div className="divide-y divide-slate-800/50">
              {sources.length === 0 ? (
                <div className="p-20 text-center flex flex-col items-center gap-4">
                   <div className="w-16 h-16 rounded-full bg-slate-800/30 flex items-center justify-center">
                      <portalConfig.icon className="w-6 h-6 text-slate-700" />
                   </div>
                   <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">No {type.toUpperCase()} assets detected in this portal</p>
                </div>
              ) : (
                sources.map((source) => (
                  <div 
                    key={source.id}
                    onClick={() => selectSource(source.id, 'dashboard')}
                    className="p-5 hover:bg-white/5 transition-all cursor-pointer group flex items-start justify-between"
                  >
                    <div className="flex items-start gap-4">
                       <div className="w-12 h-12 rounded-2xl bg-slate-800/50 flex items-center justify-center text-slate-500 group-hover:bg-indigo-500/10 group-hover:text-indigo-400 transition-all shrink-0">
                          <portalConfig.icon className="w-5 h-5" />
                       </div>
                       <div>
                          <div className="flex items-center gap-3">
                            <p className="font-bold text-white group-hover:text-indigo-400 transition-colors uppercase text-sm tracking-tight">{source.name}</p>
                            <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 uppercase tracking-widest border border-indigo-500/20">Heritage Engine V2</span>
                            {source.type === 'document' && (
                              <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 uppercase tracking-widest border border-emerald-500/20">Semantic Index Ready</span>
                            )}
                          </div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase mt-1 tracking-widest">
                             {source.type.toUpperCase()} • {new Date(source.created_at).toLocaleDateString()}
                          </p>
                          
                          {/* Heritage Feature: Semantic Density Meter */}
                          {type === 'pdf' && (
                            <div className="mt-3 flex items-center gap-3">
                               <div className="h-1 w-24 bg-slate-800 rounded-full overflow-hidden">
                                  <div className={`h-full transition-all duration-1000 ${
                                    source.indexing_status === 'done' ? 'bg-emerald-500 w-full' : 
                                    source.indexing_status === 'running' ? 'bg-indigo-500 w-1/2 animate-pulse' : 
                                    source.indexing_status === 'failed' ? 'bg-rose-500 w-full' : 'bg-slate-700 w-0'
                                  }`} />
                               </div>
                               <span className={`text-[8px] font-black uppercase tracking-widest flex items-center gap-1.5 ${
                                 source.indexing_status === 'done' ? 'text-emerald-500' : 
                                 source.indexing_status === 'running' ? 'text-indigo-400' : 
                                 source.indexing_status === 'failed' ? 'text-rose-500' : 'text-slate-500'
                               }`}>
                                 {source.schema_json?.indexing_mode === 'fast_text' && (
                                   <span className="bg-sky-500/10 text-sky-400 px-1.5 py-0.5 rounded border border-sky-500/20 leading-none">FAST</span>
                                 )}
                                 {source.schema_json?.indexing_mode === 'strategic_nexus' && (
                                   <span className="bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/20 leading-none">STRATEGIC</span>
                                 )}
                                 {source.indexing_status === 'done' ? 'Semantic Sync: 100%' : 
                                  source.indexing_status === 'running' ? 'Indexing Vectors...' : 
                                  source.indexing_status === 'failed' ? 'Sync Failed' : 'Pending Ingestion'}
                               </span>
                            </div>
                          )}

                          {/* Heritage Feature: Auto-Analysis Snippet */}
                          {type === 'pdf' && (
                            <div className={`mt-4 p-3 rounded-xl border transition-all ${
                              source.auto_analysis_status === 'done' ? 'bg-emerald-500/5 border-emerald-500/20' : 
                              source.auto_analysis_status === 'running' ? 'bg-indigo-500/5 border-indigo-500/20 animate-pulse' : 
                              'bg-black/30 border-slate-800'
                            }`}>
                               <p className={`text-[9px] font-black uppercase tracking-widest mb-1 flex items-center gap-1.5 ${
                                 source.auto_analysis_status === 'done' ? 'text-emerald-500' : 
                                 source.auto_analysis_status === 'running' ? 'text-indigo-400' : 'text-slate-600'
                               }`}>
                                 <Activity className="w-3 h-3" /> 
                                 {source.auto_analysis_status === 'done' ? 'Heritage Strategic Insight' : 'Deep Research Protocol'}
                               </p>
                               <p className="text-[11px] text-slate-400 leading-relaxed italic">
                                 {source.auto_analysis_status === 'done' 
                                   ? (source.auto_analysis_json?.summary || "Strategic signals extracted successfully.")
                                   : source.auto_analysis_status === 'running'
                                   ? "Synthesizing heritage strategic signals from vector nexus..."
                                   : "Awaiting primary signal synchronization..."}
                               </p>
                            </div>
                          )}
                       </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-700 group-hover:text-white group-hover:translate-x-1 transition-all mt-3" />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>

      {/* Heritage Feature: Upload Enrichment Modal */}
      {pendingFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0a0d17] border border-slate-800 rounded-3xl w-full max-w-2xl max-h-[90vh] overflow-y-auto custom-scroll shadow-2xl relative">
            {/* Header */}
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/40 relative overflow-hidden">
               <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-500/10 blur-[80px] rounded-full -translate-y-1/2 translate-x-1/2"></div>
               <div className="relative z-10 flex items-center gap-4">
                 <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                   <Target className="w-6 h-6 text-indigo-400" />
                 </div>
                 <div>
                   <h2 className="text-xl font-black text-white tracking-tight">Intelligence Enrichment</h2>
                   <p className="text-xs font-bold text-slate-400 tracking-widest uppercase mt-1">Classify the strategic domain of this asset</p>
                 </div>
               </div>
               <button 
                 onClick={() => setPendingFile(null)} 
                 className="relative z-10 p-2 hover:bg-white/10 rounded-xl transition-colors text-slate-400 hover:text-white"
                 disabled={uploading}
               >
                 <X className="w-5 h-5" />
               </button>
            </div>

            {/* Content */}
            <div className="p-8">
               <div className="mb-6 p-4 bg-white/5 border border-white/10 rounded-2xl flex items-center justify-between">
                  <div className="flex items-center gap-3">
                     <FileText className="w-5 h-5 text-indigo-400" />
                     <span className="font-bold text-white tracking-tight">{pendingFile.name}</span>
                  </div>
                  <span className="text-xs font-black text-slate-500 uppercase tracking-widest bg-black/30 px-2 py-1 rounded-lg">
                    {(pendingFile.size / 1024 / 1024).toFixed(2)} MB
                  </span>
               </div>

                <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-4">Select Domain Trajectory</h3>
                <div className="grid grid-cols-2 gap-3 mb-6">
                  {DOMAINS.map((category: any) => (
                    <button
                      key={category.title}
                      onClick={() => setUploadCategory(category.title)}
                      disabled={uploading}
                      className={`p-4 rounded-2xl border text-left transition-all ${
                        uploadCategory === category.title 
                          ? 'bg-indigo-500/10 border-indigo-500/50 -translate-y-1 shadow-[0_4px_20px_rgba(99,102,241,0.1)]' 
                          : 'bg-black/20 border-slate-800 hover:border-slate-600 hover:bg-slate-800/40 opacity-70 hover:opacity-100'
                      }`}
                    >
                      <p className={`text-sm font-bold tracking-tight mb-1 ${uploadCategory === category.title ? 'text-indigo-400' : 'text-slate-300'}`}>
                        {category.title}
                      </p>
                      <p className="text-[10px] leading-relaxed text-slate-500">{category.desc}</p>
                    </button>
                  ))}
                </div>

                <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-4">Select Asset Classification</h3>
                <div className="grid grid-cols-2 gap-3 mb-8">
                  {ASSET_TYPES.map((atype: any) => (
                    <button
                      key={atype.title}
                      onClick={() => setUploadAssetType(atype.title)}
                      disabled={uploading}
                      className={`p-4 rounded-2xl border text-left transition-all ${
                        uploadAssetType === atype.title 
                          ? 'bg-emerald-500/10 border-emerald-500/50 -translate-y-1 shadow-[0_4px_20px_rgba(16,185,129,0.1)]' 
                          : 'bg-black/20 border-slate-800 hover:border-slate-600 hover:bg-slate-800/40 opacity-70 hover:opacity-100'
                      }`}
                    >
                      <p className={`text-sm font-bold tracking-tight mb-1 ${uploadAssetType === atype.title ? 'text-emerald-400' : 'text-slate-300'}`}>
                        {atype.title}
                      </p>
                      <p className="text-[10px] leading-relaxed text-slate-500">{atype.desc}</p>
                    </button>
                  ))}
                </div>

               <div className="flex justify-end gap-3 pt-4 border-t border-slate-800/50">
                 <button 
                   onClick={() => setPendingFile(null)}
                   disabled={uploading}
                   className="px-6 py-3 rounded-xl font-bold text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                 >
                   Cancel Flow
                 </button>
                 <button 
                   onClick={confirmUpload}
                   disabled={uploading}
                   className="px-8 py-3 rounded-xl font-bold text-sm bg-indigo-500 hover:bg-indigo-400 text-white shadow-lg shadow-indigo-500/20 transition-all flex items-center justify-center min-w-[160px]"
                 >
                   {uploading ? (
                     <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                   ) : (
                     "Initialize Heritage Sync"
                   )}
                 </button>
               </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
