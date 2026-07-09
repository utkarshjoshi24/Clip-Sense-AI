import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { useAuthStore } from "../store/authStore";

export function Login() {
  const navigate = useNavigate();
  const { setAccessToken, setUser } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  // Background parallax effect
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const moveX = (e.clientX - window.innerWidth / 2) / 50;
      const moveY = (e.clientY - window.innerHeight / 2) / 50;
      const nodes = document.querySelectorAll('.ai-node');
      nodes.forEach((node, index) => {
        const factor = index === 0 ? 1 : -0.5;
        (node as HTMLElement).style.transform = `translate(${moveX * factor}px, ${moveY * factor}px)`;
      });
    };
    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const token = await authApi.login(email, password);
      setAccessToken(token);
      const user = await authApi.me();
      setUser(user);
      navigate("/dashboard");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-background text-on-background font-body-md min-h-screen flex flex-col relative overflow-hidden">
      {/* Background Atmospheric AI Nodes */}
      <div className="absolute top-[10%] left-[15%] w-32 h-32 bg-primary/10 rounded-full blur-[80px] ai-node animate-[pulse_4s_ease-in-out_infinite]" />
      <div className="absolute bottom-[10%] right-[15%] w-48 h-48 bg-secondary/10 rounded-full blur-[100px] ai-node animate-[pulse_4s_ease-in-out_infinite]" />
      
      <main className="relative z-10 flex-grow flex items-center justify-center px-container-margin py-stack-lg">
        <div className="w-full max-w-[440px] flex flex-col gap-stack-lg">
          {/* Branding Header */}
          <div className="text-center flex flex-col items-center gap-stack-sm animate-fade-in">
            <Link to="/">
              <div className="w-12 h-12 bg-primary-container rounded-xl flex items-center justify-center shadow-lg mb-stack-sm hover:scale-105 transition-transform">
                <span className="text-on-primary-container text-[28px]">✨</span>
              </div>
            </Link>
            <h1 className="font-headline-md text-headline-md text-on-surface tracking-tight">ClipSense</h1>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-[280px]">Professional Video Intelligence for high-performance creators.</p>
          </div>

          {/* Authentication Card */}
          <div className={`bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl border border-white/5 p-stack-lg rounded-xl shadow-2xl transition-all duration-300 ${isFocused ? 'ring-1 ring-primary/20' : ''}`}>
            <form className="flex flex-col gap-stack-md" onSubmit={handleSubmit}>
              {/* Email Field */}
              <div className="flex flex-col gap-unit">
                <label className="font-label-caps text-label-caps text-on-surface-variant ml-unit" htmlFor="email">Email Address</label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-outline text-[16px]">✉️</span>
                  <input 
                    id="email" type="email" placeholder="name@company.com" required
                    className="w-full bg-surface-container-lowest border border-white/5 rounded-lg py-3 pl-10 pr-4 text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all font-body-sm"
                    value={email} onChange={(e) => setEmail(e.target.value)}
                    onFocus={() => setIsFocused(true)} onBlur={() => setIsFocused(false)}
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="flex flex-col gap-unit">
                <div className="flex justify-between items-center ml-unit">
                  <label className="font-label-caps text-label-caps text-on-surface-variant" htmlFor="password">Password</label>
                  <Link to="/forgot-password" className="font-label-caps text-label-caps text-primary hover:underline">Forgot?</Link>
                </div>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-outline text-[16px]">🔒</span>
                  <input 
                    id="password" type="password" placeholder="••••••••" required
                    className="w-full bg-surface-container-lowest border border-white/5 rounded-lg py-3 pl-10 pr-4 text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all font-body-sm"
                    value={password} onChange={(e) => setPassword(e.target.value)}
                    onFocus={() => setIsFocused(true)} onBlur={() => setIsFocused(false)}
                  />
                </div>
              </div>

              {error && (
                <p className="text-error font-body-sm bg-error/10 border border-error/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              {/* Primary Action */}
              <button 
                type="submit" disabled={loading}
                className="w-full bg-primary-container hover:bg-primary text-on-primary-container font-headline-sm text-body-md py-3.5 rounded-lg shadow-lg active:scale-[0.98] transition-all flex items-center justify-center gap-2 mt-stack-sm disabled:opacity-50"
              >
                {loading ? "Signing In..." : "Sign In"}
                <span className="text-[18px]">→</span>
              </button>

              {/* Divider */}
              <div className="relative py-stack-sm flex items-center gap-stack-md">
                <div className="h-px flex-grow bg-white/5"></div>
                <span className="font-label-caps text-label-caps text-outline/60">OR</span>
                <div className="h-px flex-grow bg-white/5"></div>
              </div>

              {/* Secondary Action: Google */}
              <button 
                type="button" onClick={() => authApi.googleLogin()}
                className="w-full bg-transparent border border-white/10 hover:bg-white/5 text-on-surface font-body-md py-3 rounded-lg flex items-center justify-center gap-3 transition-all active:scale-[0.98]"
              >
                <svg height="18" viewBox="0 0 18 18" width="18">
                  <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"></path>
                  <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"></path>
                  <path d="M3.964 10.711c-.18-.54-.282-1.117-.282-1.711s.102-1.171.282-1.711V4.957H.957A8.996 8.996 0 0 0 0 9c0 1.497.366 2.91 1.014 4.152l2.95-2.441z" fill="#FBBC05"></path>
                  <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.483 0 2.443 2.017.957 4.958L3.964 7.29c.708-2.127 2.692-3.71 5.036-3.71z" fill="#EA4335"></path>
                </svg>
                Continue with Google
              </button>
            </form>
          </div>

          {/* Footer Links */}
          <div className="flex justify-center items-center gap-stack-lg">
            <p className="font-body-sm text-body-sm text-on-surface-variant">Don't have an account?</p>
            <Link to="/signup" className="font-headline-sm text-body-sm text-primary hover:underline">Get Started</Link>
          </div>
        </div>
      </main>

      {/* Global Footer */}
      <footer className="relative z-10 w-full py-stack-lg px-container-margin border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-stack-md bg-surface-dim/50 backdrop-blur-sm">
        <span className="font-label-caps text-label-caps text-on-surface-variant opacity-60">© 2024 ClipSense AI. Professional Video Intelligence.</span>
        <nav className="flex gap-stack-lg">
          <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-all" href="#">Privacy Policy</a>
          <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-all" href="#">Terms of Service</a>
          <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-all" href="#">Support</a>
        </nav>
      </footer>
    </div>
  );
}
