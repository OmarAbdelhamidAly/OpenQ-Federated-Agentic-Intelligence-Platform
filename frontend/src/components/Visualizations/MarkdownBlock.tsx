import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Props {
  content: string;
}

export default function MarkdownBlock({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({node, ...props}: any) => (
          <div className="overflow-x-auto my-6 rounded-xl border border-slate-700/50 shadow-xl bg-slate-900/50">
            <table className="w-full text-left border-collapse" {...props} />
          </div>
        ),
        thead: ({node, ...props}: any) => (
          <thead className="bg-[#171033] border-b border-indigo-500/30 text-indigo-300" {...props} />
        ),
        th: ({node, ...props}: any) => (
          <th className="px-4 py-3 font-semibold text-sm tracking-wide uppercase" {...props} />
        ),
        td: ({node, ...props}: any) => (
          <td className="px-4 py-3 text-sm border-t border-slate-800 text-slate-300 group-hover:bg-slate-800/20 transition-colors" {...props} />
        ),
        tr: ({node, ...props}: any) => (
          <tr className="group hover:bg-slate-800/10 transition-colors" {...props} />
        ),
        code({node, inline, className, children, ...props}: any) {
          const match = /language-(\w+)/.exec(className || '');
          const isSql = match && match[1] === 'sql';
          
          return !inline && match ? (
            <div className={`relative my-6 rounded-xl overflow-hidden border ${isSql ? 'border-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.15)]' : 'border-slate-800'}`}>
              {isSql && (
                <div className="absolute top-0 right-0 left-0 px-4 py-2 bg-[#171033] border-b border-indigo-500/30 text-xs font-semibold text-indigo-300 tracking-wider flex justify-between items-center">
                  <span>GENERATED SQL</span>
                </div>
              )}
              <div className={isSql ? 'pt-8' : ''}>
                <SyntaxHighlighter
                  style={vscDarkPlus as any}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{ margin: 0, background: '#0a041f' }}
                  {...props}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              </div>
            </div>
          ) : (
            <code className="bg-indigo-500/10 text-indigo-300 px-1.5 py-0.5 rounded-md text-sm font-mono" {...props}>
              {children}
            </code>
          );
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
