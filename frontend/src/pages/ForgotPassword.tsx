import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../api/auth";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
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
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
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
            <h1 className="font-headline-md text-headline-md text-on-surface tracking-tight">Reset Password</h1>
            {!sent && <p className="font-body-md text-body-md text-on-surface-variant max-w-[280px]">Enter your email and we'll send a reset link.</p>}
          </div>

          {/* Authentication Card */}
          <div className={`bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl border border-white/5 p-stack-lg rounded-xl shadow-2xl transition-all duration-300 ${isFocused ? 'ring-1 ring-primary/20' : ''}`}>
            {sent ? (
              <div className="text-center space-y-4 animate-fade-in">
                <div className="w-16 h-16 mx-auto bg-primary-container rounded-full flex items-center justify-center shadow-lg mb-stack-sm hover:scale-105 transition-transform">
                  <span className="text-on-primary-container text-3xl">📧</span>
                </div>
                <h2 className="font-headline-sm text-headline-sm text-white">Check your email</h2>
                <p className="font-body-sm text-on-surface-variant">
                  If that address is registered, you'll receive a reset link shortly.
                </p>
                <Link to="/login" className="w-full bg-primary-container hover:bg-primary text-on-primary-container font-headline-sm text-body-md py-3.5 rounded-lg shadow-lg active:scale-[0.98] transition-all flex items-center justify-center mt-stack-sm">
                  Back to Sign In
                </Link>
              </div>
            ) : (
              <form className="flex flex-col gap-stack-md" onSubmit={handleSubmit}>
                {/* Email Field */}
                <div className="flex flex-col gap-unit">
                  <label className="font-label-caps text-label-caps text-on-surface-variant ml-unit" htmlFor="email">Email Address</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-outline text-[16px]">✉️</span>
                    <input 
                      id="email" type="email" placeholder="you@example.com" required
                      className="w-full bg-surface-container-lowest border border-white/5 rounded-lg py-3 pl-10 pr-4 text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all font-body-sm"
                      value={email} onChange={(e) => setEmail(e.target.value)}
                      onFocus={() => setIsFocused(true)} onBlur={() => setIsFocused(false)}
                    />
                  </div>
                </div>

                {/* Primary Action */}
                <button 
                  type="submit" disabled={loading}
                  className="w-full bg-primary-container hover:bg-primary text-on-primary-container font-headline-sm text-body-md py-3.5 rounded-lg shadow-lg active:scale-[0.98] transition-all flex items-center justify-center gap-2 mt-stack-sm disabled:opacity-50"
                >
                  {loading ? "Sending..." : "Send Reset Link"}
                </button>

                <div className="mt-4 text-center">
                  <Link to="/login" className="font-headline-sm text-body-sm text-primary hover:underline">
                    ← Back to Sign In
                  </Link>
                </div>
              </form>
            )}
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

// src/pages/VerifyEmail.tsx
export function VerifyEmail() {
  return (
    <div className="bg-background text-on-background font-body-md min-h-screen flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute top-[10%] left-[15%] w-32 h-32 bg-primary/10 rounded-full blur-[80px] ai-node animate-[pulse_4s_ease-in-out_infinite]" />
      <div className="absolute bottom-[10%] right-[15%] w-48 h-48 bg-secondary/10 rounded-full blur-[100px] ai-node animate-[pulse_4s_ease-in-out_infinite]" />
      
      <div className="relative z-10 w-full max-w-sm bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl border border-white/5 p-stack-lg rounded-xl shadow-2xl text-center space-y-4 animate-fade-in">
        <div className="w-16 h-16 mx-auto bg-success/20 rounded-full flex items-center justify-center shadow-lg mb-stack-sm hover:scale-105 transition-transform">
          <span className="text-success text-3xl">✅</span>
        </div>
        <h2 className="font-headline-sm text-headline-sm text-white">Email verified!</h2>
        <p className="font-body-sm text-on-surface-variant">Your account is now active.</p>
        <Link to="/login" className="w-full bg-primary-container hover:bg-primary text-on-primary-container font-headline-sm text-body-md py-3.5 rounded-lg shadow-lg active:scale-[0.98] transition-all flex items-center justify-center mt-stack-sm">
          Sign In
        </Link>
      </div>
    </div>
  );
}
