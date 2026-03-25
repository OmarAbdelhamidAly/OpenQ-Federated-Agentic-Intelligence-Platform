import { useState } from 'react';
import { Mail, Lock, Building, ArrowRight, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { AuthAPI } from '../../services/api';
import openqLogo from '../../assets/openq-logo.png';

interface AuthPageProps {
  onLogin: (token: string, refreshToken: string, user: any) => void;
}

export default function AuthPage({ onLogin }: AuthPageProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [tenantName, setTenantName] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isLogin) {
        const data = await AuthAPI.login({ email, password });
        if (data.access_token && data.user) {
          onLogin(data.access_token, data.refresh_token, data.user);
        } else {
          throw new Error("Invalid response from server. Missing user data.");
        }
      } else {
        const data = await AuthAPI.register({ 
          email, 
          password, 
          tenant_name: tenantName 
        });
        if (data.access_token && data.user) {
          onLogin(data.access_token, data.refresh_token, data.user);
        } else {
          throw new Error("Registration successful, but missing user data in response.");
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#0a041f] relative overflow-hidden">
      {/* Background Decorative Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-500/10 blur-[120px] rounded-full"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 blur-[120px] rounded-full"></div>
      </div>

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-md z-10"
      >
        <div className="text-center mb-10">
          <div className="flex justify-center mb-6">
            <img src={openqLogo} alt="OpenQ.AI Logo" className="h-28 object-contain rounded-[32px] mix-blend-screen shadow-2xl shadow-indigo-500/20" />
          </div>
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-indigo-200 tracking-tight mb-3">
            {isLogin ? "Welcome Back" : "Create Account"}
          </h1>
          <p className="text-slate-400 text-sm font-medium">
            {isLogin 
              ? "Access your autonomous data analyst" 
              : "Start your journey into AI-powered insights"}
          </p>
        </div>

        <div className="bg-[#171033]/60 backdrop-blur-2xl border border-slate-700/50 rounded-3xl p-8 shadow-2xl overflow-hidden relative group">
          {/* Internal Glow */}
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-purple-500/5 pointer-events-none"></div>

          <form onSubmit={handleSubmit} className="relative z-10 space-y-5">
            <AnimatePresence mode="popLayout">
              {!isLogin && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-2"
                >
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                    <Building className="w-3 h-3" /> Organization Name
                  </label>
                  <input
                    type="text"
                    required
                    value={tenantName}
                    onChange={(e) => setTenantName(e.target.value)}
                    placeholder="Acme Analytics"
                    className="w-full bg-[#0a041f]/50 border border-slate-700/50 focus:border-indigo-500/50 focus:ring-4 focus:ring-indigo-500/10 outline-none rounded-xl px-4 py-3 text-slate-100 transition-all placeholder:text-slate-600"
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                <Mail className="w-3 h-3" /> Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full bg-[#0a041f]/50 border border-slate-700/50 focus:border-indigo-500/50 focus:ring-4 focus:ring-indigo-500/10 outline-none rounded-xl px-4 py-3 text-slate-100 transition-all placeholder:text-slate-600"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                <Lock className="w-3 h-3" /> Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-[#0a041f]/50 border border-slate-700/50 focus:border-indigo-500/50 focus:ring-4 focus:ring-indigo-500/10 outline-none rounded-xl px-4 py-3 text-slate-100 transition-all placeholder:text-slate-600"
              />
            </div>

            {error && (
              <motion.div 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs font-medium"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold py-4 rounded-xl shadow-xl shadow-indigo-500/20 transition-all flex items-center justify-center gap-2 active:scale-[0.98] disabled:opacity-70 group"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  {isLogin ? "Sign In" : "Get Started"}
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 text-center relative z-10">
            <button 
              onClick={() => setIsLogin(!isLogin)}
              className="text-slate-400 hover:text-indigo-400 text-sm transition-colors"
            >
              {isLogin ? (
                <>Don't have an account? <span className="text-indigo-400 font-bold ml-1">Sign Up</span></>
              ) : (
                <>Already have an account? <span className="text-indigo-400 font-bold ml-1">Sign In</span></>
              )}
            </button>
          </div>
        </div>

        <p className="mt-8 text-center text-[10px] text-slate-600 uppercase tracking-[0.2em] font-black">
          Powered by DeepMind Analytics • Secured by LangGraph
        </p>
      </motion.div>
    </div>
  );
}
