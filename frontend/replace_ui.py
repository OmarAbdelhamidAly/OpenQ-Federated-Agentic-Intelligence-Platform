import os

p = r'C:\Users\Lenovo\Downloads\finalproject\frontend\src\components\Dashboard\PortalDashboard.tsx'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()

old_ui = """                 <div className="relative flex items-center bg-black/20 p-0.5 rounded-lg border border-white/5 shadow-inner">
                   <div 
                     className="absolute top-0.5 bottom-0.5 w-[calc(50%-2px)] bg-[var(--primary)] rounded-md transition-all duration-300 shadow-md pointer-events-none"
                     style={{
                       left: indexingMode === 'deep_vision' ? '2px' : 'calc(50%)'
                     }}
                   />
                   
                   <button
                     type="button"
                     onClick={() => setIndexingMode('deep_vision')}
                     className={`relative z-10 px-3 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-all w-28 text-center ${
                       indexingMode === 'deep_vision' ? 'text-white' : 'text-slate-500 hover:text-slate-300'
                     }`}
                     title="Uses ColPali Vision-Language Model. Accurately reads charts, graphs, and images. Slow indexing."
                   >
                     Deep Vision
                   </button>
                   <button
                     type="button"
                     onClick={() => setIndexingMode('fast_text')}
                     className={`relative z-10 px-3 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-all w-28 text-center ${
                       indexingMode === 'fast_text' ? 'text-white' : 'text-slate-500 hover:text-slate-300'
                     }`}
                     title="Uses FastEmbed & text chunking. Ignores images/charts. Sub-second indexing."
                   >
                     Fast Text
                   </button>
                 </div>"""

new_ui = """                 <div className="relative flex items-center bg-black/20 p-0.5 rounded-lg border border-white/5 shadow-inner w-full max-w-sm">
                   <div 
                     className="absolute top-0.5 bottom-0.5 w-[calc(33.33%-1px)] bg-[var(--primary)] rounded-md transition-all duration-300 shadow-md pointer-events-none"
                     style={{
                       left: indexingMode === 'deep_vision' ? '2px' : indexingMode === 'hybrid_ocr' ? 'calc(33.33% + 1px)' : 'calc(66.66% + 0px)'
                     }}
                   />
                   
                   <button
                     type="button"
                     onClick={() => setIndexingMode('deep_vision')}
                     className={`relative z-10 px-2 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-all flex-1 text-center ${
                       indexingMode === 'deep_vision' ? 'text-white' : 'text-slate-500 hover:text-slate-300'
                     }`}
                     title="Uses ColPali Vision-Language Model. Accurately reads charts, graphs, and images. Slow indexing."
                   >
                     Deep Vision
                   </button>
                   <button
                     type="button"
                     onClick={() => setIndexingMode('hybrid_ocr')}
                     className={`relative z-10 px-2 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-all flex-1 text-center ${
                       indexingMode === 'hybrid_ocr' ? 'text-white' : 'text-slate-500 hover:text-slate-300'
                     }`}
                     title="Segmenter + Selective OCR. Best of both worlds."
                   >
                     Hybrid OCR
                   </button>
                   <button
                     type="button"
                     onClick={() => setIndexingMode('fast_text')}
                     className={`relative z-10 px-2 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-all flex-1 text-center ${
                       indexingMode === 'fast_text' ? 'text-white' : 'text-slate-500 hover:text-slate-300'
                     }`}
                     title="Uses FastEmbed & text chunking. Ignores images/charts. Sub-second indexing."
                   >
                     Fast Text
                   </button>
                 </div>"""

if old_ui in content:
    content = content.replace(old_ui, new_ui)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    print("UI successfully replaced.")
else:
    print("Could not find the exact old_ui block in PortalDashboard.tsx.")
