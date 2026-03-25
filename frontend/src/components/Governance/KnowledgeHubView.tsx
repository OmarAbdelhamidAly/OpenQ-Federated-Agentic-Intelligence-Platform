import { useState, useEffect } from 'react';
import { 
  Book, 
  Database, 
  Plus, 
  Trash2, 
  Upload, 
  ChevronRight, 
  FileText, 
  BookOpen,
  Brain,
  Zap,
  Loader2,
  X,
  Target
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { KnowledgeAPI, MetricsAPI } from '../../services/api';

export default function KnowledgeHubView() {
  const [activeTab, setActiveTab] = useState<'kb' | 'metrics'>('kb');
  const [kbList, setKbList] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isKbModalOpen, setIsKbModalOpen] = useState(false);
  const [isMetricModalOpen, setIsMetricModalOpen] = useState(false);
  const [selectedKb, setSelectedKb] = useState<any | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [kbs, mets] = await Promise.all([
        KnowledgeAPI.list(),
        MetricsAPI.list()
      ]);
      setKbList(kbs);
      setMetrics(mets);
    } catch (e) {
      console.error("Failed to fetch Knowledge Hub data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleKbClick = async (kb: any) => {
    try {
      setSelectedKb(kb);
      const docs = await KnowledgeAPI.listDocuments(kb.id);
      setDocuments(docs);
    } catch (e) {
      console.error("Failed to fetch documents", e);
    }
  };

  const handleCreateKb = async (e: any) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
      await KnowledgeAPI.create({
        name: formData.get('name') as string,
        description: formData.get('description') as string
      });
      fetchData();
      setIsKbModalOpen(false);
    } catch (e) {
      alert("Failed to create collection.");
    }
  };

  const handleCreateMetric = async (e: any) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
      await MetricsAPI.create({
        name: formData.get('name') as string,
        definition: formData.get('definition') as string,
        formula: formData.get('formula') as string
      });
      fetchData();
      setIsMetricModalOpen(false);
    } catch (e) {
      alert("Failed to define metric.");
    }
  };

  const handleDeleteKb = async (id: string) => {
    if (!confirm("Delete this entire knowledge collection and all vectors?")) return;
    try {
      await KnowledgeAPI.delete(id);
      fetchData();
      setSelectedKb(null);
    } catch (e) {
      alert("Delete failed.");
    }
  };

  const handleDeleteMetric = async (id: string) => {
    if (!confirm("Remove this business logic definition?")) return;
    try {
      await MetricsAPI.delete(id);
      fetchData();
    } catch (e) {
      alert("Delete failed.");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length || !selectedKb) return;
    const file = e.target.files[0];
    setIsUploading(true);
    try {
      await KnowledgeAPI.uploadDocument(selectedKb.id, file);
      const docs = await KnowledgeAPI.listDocuments(selectedKb.id);
      setDocuments(docs);
    } catch (e) {
      alert("Upload failed.");
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKb) return;
    try {
      await KnowledgeAPI.deleteDocument(selectedKb.id, docId);
      const docs = await KnowledgeAPI.listDocuments(selectedKb.id);
      setDocuments(docs);
    } catch (e) {
      console.error("Failed to delete document", e);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#0a0d17]/50 relative">
      {/* Modals */}
      <AnimatePresence>
        {isKbModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setIsKbModalOpen(false)} className="absolute inset-0 bg-black/60 backdrop-blur-md" />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="relative w-full max-w-lg bg-[#171c2a] border border-slate-700/50 rounded-[32px] overflow-hidden">
               <div className="p-8 border-b border-slate-800 flex items-center justify-between">
                  <h2 className="text-xl font-black text-white">New Knowledge Collection</h2>
                  <button onClick={() => setIsKbModalOpen(false)} className="p-2 hover:bg-white/5 rounded-xl"><X className="w-5 h-5 text-slate-500" /></button>
               </div>
               <form onSubmit={handleCreateKb} className="p-8 space-y-6">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Collection Identity</label>
                    <input name="name" required placeholder="e.g. Legal Contracts 2024" className="w-full bg-black/20 border border-slate-800 rounded-2xl px-5 py-4 text-white text-sm font-bold" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Description</label>
                    <textarea name="description" rows={3} placeholder="Describe the semantic scope..." className="w-full bg-black/20 border border-slate-800 rounded-2xl px-5 py-4 text-white text-sm font-bold" />
                  </div>
                  <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-black py-4 rounded-2xl transition-all">Establish Repository</button>
               </form>
            </motion.div>
          </div>
        )}

        {isMetricModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setIsMetricModalOpen(false)} className="absolute inset-0 bg-black/60 backdrop-blur-md" />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="relative w-full max-w-lg bg-[#171c2a] border border-slate-700/50 rounded-[32px] overflow-hidden">
               <div className="p-8 border-b border-slate-800 flex items-center justify-between">
                  <h2 className="text-xl font-black text-white">Define Business Logic</h2>
                  <button onClick={() => setIsMetricModalOpen(false)} className="p-2 hover:bg-white/5 rounded-xl"><X className="w-5 h-5 text-slate-500" /></button>
               </div>
               <form onSubmit={handleCreateMetric} className="p-8 space-y-6">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Metric Identity</label>
                    <input name="name" required placeholder="e.g. EBIDTA Margin" className="w-full bg-black/20 border border-slate-800 rounded-2xl px-5 py-4 text-white text-sm font-bold" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Definition</label>
                    <textarea name="definition" rows={2} required placeholder="Business meaning of this metric..." className="w-full bg-black/20 border border-slate-800 rounded-2xl px-5 py-4 text-white text-sm font-bold" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Formula Constraint</label>
                    <input name="formula" placeholder="e.g. (Revenue - COGS) / Revenue" className="w-full bg-black/20 border border-slate-800 rounded-2xl px-5 py-4 text-white text-sm font-mono font-bold text-indigo-400" />
                  </div>
                  <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-black py-4 rounded-2xl transition-all">Sync Dictionary</button>
               </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="p-8 pb-8 relative overflow-hidden shrink-0">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-500/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2"></div>
        
        <div className="relative z-10 flex items-end justify-between">
          <div>
             <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                   <Brain className="w-5 h-5 text-indigo-400" />
                </div>
                <span className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.3em]">Intelligence Hub — Enterprise RAG</span>
             </div>
             <h1 className="text-4xl font-black text-white tracking-tight">Intelligence Hub</h1>
             <p className="text-slate-400 mt-2 font-medium max-w-xl">
               Manage semantic repositories and business logic dictionaries to ground autonomous reasoning.
             </p>
          </div>

          <div className="flex bg-slate-900/60 p-1.5 rounded-2xl border border-slate-800 backdrop-blur-xl">
             <button onClick={() => setActiveTab('kb')} className={`px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'kb' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-white'}`}>Repositories</button>
             <button onClick={() => setActiveTab('metrics')} className={`px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'metrics' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-white'}`}>Dictionary</button>
          </div>
        </div>
      </div>

      {/* Onboarding / Intro Cards */}
      <div className="px-8 mb-8 shrink-0">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-6 bg-indigo-600/5 border border-indigo-500/20 rounded-[32px] flex items-start gap-5 group hover:bg-indigo-600/10 transition-all">
            <div className="w-12 h-12 shrink-0 rounded-2xl bg-indigo-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-black text-white uppercase tracking-wider mb-1">Semantic Repositories <span className="text-indigo-400 font-medium ml-2">| مستودعات المعرفة</span></h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Connect your private documents (PDF, Doc) to ground the AI. It uses this context to answer questions specifically about your files.
                <br />
                <span className="text-[10px] text-slate-500 mt-1 block italic text-right">ارفع ملفاتك هنا ليتمكن الذكاء الاصطناعي من الإجابة بناءً على محتواها الخاص.</span>
              </p>
            </div>
          </div>
          <div className="p-6 bg-purple-600/5 border border-purple-500/20 rounded-[32px] flex items-start gap-5 group hover:bg-purple-600/10 transition-all">
            <div className="w-12 h-12 shrink-0 rounded-2xl bg-purple-500 flex items-center justify-center text-white shadow-lg shadow-purple-500/20">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-black text-white uppercase tracking-wider mb-1">Logic Dictionary <span className="text-purple-400 font-medium ml-2">| قاموس المنطق</span></h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Define your custom business metrics (like ROI or EBIDTA) to ensure the AI uses your exact formulas and math correctly.
                <br />
                <span className="text-[10px] text-slate-500 mt-1 block italic text-right">عرف معادلات عملك الخاصة لضمان دقة العمليات الحسابية والنتائج.</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Areas */}
      <div className="flex-1 overflow-hidden px-8 pb-8 flex gap-8">
        
        {activeTab === 'kb' ? (
          <>
            {/* KB List Sidebar */}
            <div className="w-[450px] flex flex-col gap-6 overflow-y-auto pr-2 custom-scroll">
               <div className="flex items-center justify-between">
                  <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Semantic Collections</h3>
                  <button onClick={() => setIsKbModalOpen(true)} className="p-1.5 hover:bg-white/5 rounded-lg text-indigo-400 transition-all"><Plus className="w-5 h-5" /></button>
               </div>
               
               {loading ? (
                 <div className="p-12 flex flex-col items-center gap-4 bg-slate-900/40 border border-slate-800 rounded-[32px]">
                   <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Syncing Vector Store...</p>
                 </div>
               ) : kbList.length === 0 ? (
                 <div className="p-12 text-center bg-slate-900/40 border border-slate-800 rounded-[32px]">
                    <div className="w-12 h-12 bg-slate-800/50 rounded-2xl flex items-center justify-center mx-auto mb-4"><Book className="w-6 h-6 text-slate-600" /></div>
                    <p className="text-xs font-bold text-slate-600 uppercase tracking-widest">No Collections Established</p>
                 </div>
               ) : (
                 kbList.map((kb) => (
                   <div 
                     key={kb.id} 
                     onClick={() => handleKbClick(kb)}
                     className={`p-6 rounded-[32px] border transition-all cursor-pointer group flex flex-col gap-4 relative overflow-hidden ${selectedKb?.id === kb.id ? 'bg-indigo-600/10 border-indigo-500/50' : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'}`}
                   >
                     {selectedKb?.id === kb.id && <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/10 blur-2xl rounded-full translate-x-1/2 -translate-y-1/2" />}
                     <div className="flex items-center justify-between">
                        <div className={`p-2.5 rounded-xl border transition-all ${selectedKb?.id === kb.id ? 'bg-indigo-500 text-white border-indigo-400' : 'bg-slate-800/50 text-slate-400 border-slate-700'}`}>
                           <Database className="w-5 h-5" />
                        </div>
                        <span className="text-[8px] font-black px-2 py-1 rounded bg-black/40 text-slate-500 uppercase tracking-widest">RAG Optimized</span>
                     </div>
                     <div>
                        <h4 className="font-black text-white text-lg tracking-tight group-hover:text-indigo-400 transition-colors uppercase">{kb.name}</h4>
                        <p className="text-xs text-slate-500 font-medium line-clamp-2 mt-1">{kb.description || 'Enterprise semantic repository.'}</p>
                     </div>
                     <div className="flex items-center justify-between pt-4 border-t border-slate-800/50">
                        <div className="flex items-center gap-4">
                           <div>
                              <p className="text-[8px] font-black text-slate-600 uppercase tracking-widest">Vectors</p>
                              <p className="text-xs font-black text-white">{kb.document_count || 0}</p>
                           </div>
                           <div>
                              <p className="text-[8px] font-black text-slate-600 uppercase tracking-widest">Latency</p>
                              <p className="text-xs font-black text-emerald-400">12ms</p>
                           </div>
                        </div>
                        <ChevronRight className={`w-5 h-5 transition-all ${selectedKb?.id === kb.id ? 'text-indigo-400 translate-x-1' : 'text-slate-700'}`} />
                     </div>
                   </div>
                 ))
               )}
            </div>

            {/* Document Detail View */}
            <div className="flex-1 flex flex-col gap-6 bg-slate-900/40 border border-slate-800 rounded-[40px] overflow-hidden backdrop-blur-xl">
               {selectedKb ? (
                 <>
                   <div className="p-8 border-b border-slate-800 flex items-center justify-between bg-gradient-to-r from-indigo-500/5 to-transparent">
                      <div>
                         <h3 className="text-xl font-black text-white uppercase tracking-tight">{selectedKb.name}</h3>
                         <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mt-1">Repository Control Plane</p>
                      </div>
                      <div className="flex gap-3">
                         <label className="bg-white/5 hover:bg-white/10 border border-white/10 px-6 py-2.5 rounded-xl text-xs font-bold text-white transition-all cursor-pointer flex items-center gap-2 group">
                            <Upload className="w-4 h-4 text-slate-400 group-hover:text-white transition-colors" /> 
                            <span>Sync Documentation</span>
                            <input type="file" className="hidden" onChange={handleFileUpload} accept=".pdf,.txt,.docx" />
                         </label>
                         <button onClick={() => handleDeleteKb(selectedKb.id)} className="p-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-xl transition-all">
                            <Trash2 className="w-4 h-4" />
                         </button>
                      </div>
                   </div>

                   <div className="flex-1 overflow-y-auto px-8 py-6 custom-scroll">
                      {isUploading && (
                        <div className="mb-6 p-6 rounded-2xl bg-indigo-500/5 border border-indigo-500/30 animate-pulse flex items-center justify-between">
                           <div className="flex items-center gap-4">
                              <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />
                              <span className="text-sm font-black text-white uppercase tracking-widest">Ingesting Context into Neural Layer...</span>
                           </div>
                           <span className="text-xs font-black text-indigo-400">54%</span>
                        </div>
                      )}

                      <div className="space-y-2">
                         {documents.length === 0 ? (
                           <div className="p-20 text-center flex flex-col items-center gap-4">
                              <FileText className="w-12 h-12 text-slate-800 opacity-20" />
                              <p className="text-xs font-bold text-slate-600 uppercase tracking-widest">No documents indexed in this collection</p>
                           </div>
                         ) : (
                           documents.map((doc) => (
                             <div key={doc.id} className="p-6 hover:bg-white/5 rounded-2xl transition-all group flex items-center justify-between border border-transparent hover:border-slate-800">
                                <div className="flex items-center gap-5">
                                   <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center text-slate-500 group-hover:bg-indigo-500/10 group-hover:text-indigo-400 transition-all">
                                      <BookOpen className="w-5 h-5" />
                                   </div>
                                   <div>
                                      <p className="font-bold text-white uppercase text-sm">{doc.name}</p>
                                      <div className="flex items-center gap-3 mt-1">
                                         <span className={`text-[8px] font-black px-1.5 py-0.5 rounded uppercase tracking-widest ${doc.status === 'indexed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
                                            {doc.status}
                                         </span>
                                         <span className="text-[8px] font-bold text-slate-600 uppercase">Synchronized {new Date(doc.created_at).toLocaleDateString()}</span>
                                      </div>
                                   </div>
                                </div>
                                <button onClick={() => handleDeleteDoc(doc.id)} className="opacity-0 group-hover:opacity-100 p-2 text-slate-700 hover:text-red-400 transition-all">
                                   <Trash2 className="w-4 h-4" />
                                </button>
                             </div>
                           ))
                         )}
                      </div>
                   </div>
                 </>
               ) : (
                 <div className="flex-1 flex flex-col items-center justify-center text-center p-20 gap-6">
                     <div className="relative">
                        <div className="absolute inset-0 bg-indigo-500/20 blur-3xl rounded-full" />
                        <Brain className="w-20 h-20 text-indigo-500/40 relative z-10" />
                     </div>
                     <div>
                        <h3 className="text-2xl font-black text-white italic tracking-tight uppercase">Select a Neutral Repository</h3>
                        <p className="text-slate-500 max-w-sm mt-3 font-bold uppercase text-[10px] tracking-widest leading-loose">
                           Choose a semantic collection to manage its indexed corpus or review its neural health metrics.
                           <br />
                           <span className="text-indigo-400/60 block mt-2">اختر مستودعاً لبدء إدارة ملفاته المضافة.</span>
                        </p>
                     </div>
                 </div>
               )}
            </div>
          </>
        ) : (
          /* Metrics Dictionary View */
          <div className="flex-1 flex flex-col gap-6 bg-slate-900/40 border border-slate-800 rounded-[40px] overflow-hidden backdrop-blur-xl">
             <div className="p-8 border-b border-slate-800 flex items-center justify-between">
                <div>
                   <h3 className="text-xl font-black text-white uppercase tracking-tight">Metric Dictionary</h3>
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mt-1">Semantic Logic Registry</p>
                </div>
                <button 
                   onClick={() => setIsMetricModalOpen(true)}
                   className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 rounded-xl text-xs font-bold shadow-xl transition-all flex items-center gap-2"
                >
                   <Plus className="w-4 h-4" /> Define Metric
                </button>
             </div>

             <div className="flex-1 overflow-y-auto px-8 pb-8 custom-scroll">
                {loading ? (
                  <div className="p-20 text-center"><Loader2 className="w-10 h-10 text-indigo-500 animate-spin mx-auto" /></div>
                ) : metrics.length === 0 ? (
                  <div className="p-20 text-center flex flex-col items-center gap-4">
                     <Target className="w-12 h-12 text-slate-800 opacity-20" />
                     <p className="text-xs font-bold text-slate-600 uppercase tracking-widest">No business metrics defined</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     {metrics.map((m) => (
                       <div key={m.id} className="p-6 bg-black/20 border border-slate-800/50 rounded-3xl hover:border-indigo-500/30 transition-all group">
                          <div className="flex items-center justify-between mb-4">
                             <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                                   <Target className="w-4 h-4" />
                                </div>
                                <h4 className="font-black text-white uppercase text-sm tracking-tight">{m.name}</h4>
                             </div>
                             <button onClick={() => handleDeleteMetric(m.id)} className="opacity-0 group-hover:opacity-100 p-2 text-slate-700 hover:text-red-400 transition-all">
                                <Trash2 className="w-4 h-4" />
                             </button>
                          </div>
                          <p className="text-xs text-slate-400 font-medium mb-4 line-clamp-2">{m.definition}</p>
                          <div className="p-3 bg-indigo-500/5 border border-indigo-500/10 rounded-xl font-mono text-[10px] text-indigo-400 flex items-center justify-between">
                             <span className="truncate">{m.formula || 'DYNAMIC_RESOLVE'}</span>
                             <Zap className="w-3 h-3 text-indigo-600 shrink-0 ml-2" />
                          </div>
                       </div>
                     ))}
                  </div>
                )}
             </div>
          </div>
        )}

      </div>
    </div>
  );
}
