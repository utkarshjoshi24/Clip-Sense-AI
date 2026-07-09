import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";

// Lazy load the 3D scene so it doesn't block initial render
// and is code-split from the main bundle.
const Hero3DScene = lazy(() => import("../components/Hero3DScene"));

export function Landing() {
  // Check if user prefers reduced motion
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <div className="bg-background text-on-background font-body-md selection:bg-primary/30 selection:text-primary min-h-screen flex flex-col">
      {/* Top Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 flex justify-between items-center px-container-margin py-stack-sm bg-surface/70 backdrop-blur-xl border-b border-white/10 shadow-md">
        <div className="flex items-center gap-stack-md">
          <span className="text-body-lg font-headline-md font-bold text-on-surface tracking-tight">
            ClipSense
          </span>
          <div className="hidden md:flex gap-gutter ml-stack-lg">
            <Link to="/dashboard" className="text-primary font-bold border-b-2 border-primary pb-1 font-body-md transition-all duration-200">
              Dashboard
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-stack-md">
          <Link to="/login" className="text-on-surface-variant hover:text-white transition-colors">
            Sign In
          </Link>
          <Link to="/signup" className="bg-primary text-on-primary font-bold px-stack-md py-stack-sm rounded-lg hover:bg-primary/90 transition-all active:scale-95 font-body-md">
            Get Started
          </Link>
        </div>
      </nav>

      <main className="pt-24 flex-1">
        {/* Hero Section */}
        <section className="relative px-container-margin py-24 flex flex-col items-center text-center overflow-hidden">
          <div className="relative z-10 max-w-4xl">
            <span className="font-label-caps text-label-caps text-primary tracking-widest uppercase mb-stack-md block">
              Video Intelligence Platform
            </span>
            <h1 className="font-headline-lg text-headline-lg text-white mb-stack-lg leading-tight">
              Distill raw footage into <span className="text-primary" style={{ textShadow: "0 0 20px rgba(192, 193, 255, 0.3)" }}>viral highlights.</span>
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant mb-stack-lg max-w-2xl mx-auto">
              ClipSense uses advanced neural processing to find the most engaging moments in your videos automatically. Stop scrubbing, start shipping.
            </p>
            <div className="flex flex-col sm:flex-row gap-stack-md justify-center">
              <Link to="/signup" className="px-8 py-4 bg-primary text-on-primary font-bold rounded-xl text-body-lg shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-all active:scale-95">
                Start Creating for Free
              </Link>
              <a href="https://github.com/utkarshjoshi24/Clip-Sense-AI" target="_blank" rel="noreferrer" className="px-8 py-4 bg-surface-variant/50 text-white border border-white/10 font-semibold rounded-xl text-body-lg hover:bg-surface-variant transition-all active:scale-95 backdrop-blur-md">
                View on GitHub
              </a>
            </div>
          </div>

          {/* Hero Visualization: Timeline Condensing */}
          <div className="mt-20 w-full max-w-5xl relative z-10">
            <div className="bg-[rgba(30,30,32,0.7)] backdrop-blur-3xl border border-white/10 p-stack-md rounded-2xl shadow-2xl relative overflow-hidden">
              <div className="flex items-center justify-between mb-stack-md">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-error/50"></div>
                  <div className="w-3 h-3 rounded-full bg-warning/50"></div>
                  <div className="w-3 h-3 rounded-full bg-success/50"></div>
                </div>
                <span className="text-mono-sm font-mono-sm text-on-surface-variant">SCENE_ANALYSIS_V4.LOG</span>
              </div>
              
              {/* 3D Scene Container */}
              <div className="w-full h-[500px] bg-black/40 rounded-xl border border-white/5 relative flex items-center justify-center">
                {prefersReducedMotion ? (
                  <div className="text-on-surface-variant font-mono-sm">
                    [3D Visualization Disabled - Reduced Motion Preference]
                  </div>
                ) : (
                  <Suspense fallback={<div className="text-on-surface-variant animate-pulse font-mono-sm">Loading Neural Visualization...</div>}>
                    <Hero3DScene />
                  </Suspense>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Features Bento Grid */}
        <section className="px-container-margin py-24 bg-surface-dim">
          <div className="max-w-7xl mx-auto">
            <div className="mb-stack-lg">
              <h2 className="font-headline-md text-headline-md mb-stack-sm text-white">Precision Intelligence.</h2>
              <p className="font-body-md text-on-surface-variant max-w-xl">Every frame analyzed by neural engines optimized for narrative impact and retention.</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
              {/* Feature 1 */}
              <div className="md:col-span-2 bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl border border-white/10 p-stack-lg rounded-2xl flex flex-col md:flex-row gap-stack-lg items-center group">
                <div className="flex-1">
                  <div className="w-12 h-12 bg-primary/10 text-primary rounded-xl flex items-center justify-center mb-stack-md text-2xl">
                    🔊
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-white mb-stack-sm">Audio Energy Detection</h3>
                  <p className="font-body-md text-on-surface-variant">Identify emotional peaks and punchlines by analyzing waveform density and vocal inflection patterns in real-time.</p>
                </div>
              </div>
              
              {/* Feature 2 */}
              <div className="bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl border border-white/10 p-stack-lg rounded-2xl hover:bg-surface-variant/30 transition-all">
                <div className="w-12 h-12 bg-secondary/10 text-secondary rounded-xl flex items-center justify-center mb-stack-md text-2xl">
                  ✂️
                </div>
                <h3 className="font-headline-sm text-headline-sm text-white mb-stack-sm">Scene-Aware Cutting</h3>
                <p className="font-body-md text-on-surface-variant">Automatically detect context shifts and visual transitions to ensure every clip starts and ends with perfect timing.</p>
              </div>

              {/* Feature 3 */}
              <div className="bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl border-t-4 border-t-primary/50 border border-white/10 p-stack-lg rounded-2xl flex flex-col justify-between">
                <div>
                  <div className="w-12 h-12 bg-primary/10 text-primary rounded-xl flex items-center justify-center mb-stack-md text-2xl">
                    💬
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-white mb-stack-sm">Transcript Scoring</h3>
                  <p className="font-body-md text-on-surface-variant">Keywords and semantic relevance map directly to virality potential scores. Search by intent, not just time.</p>
                </div>
                <div className="mt-stack-lg pt-stack-md border-t border-white/5 flex items-center justify-between">
                  <span className="text-label-caps font-label-caps text-primary">NLP ENGINE V2</span>
                  <span className="text-mono-sm text-on-surface-variant">99.2% Accuracy</span>
                </div>
              </div>
              
              {/* Feature 4 */}
              <div className="md:col-span-2 bg-gradient-to-br from-surface-variant/40 to-transparent border border-white/10 p-stack-lg rounded-2xl flex items-center gap-stack-lg">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-stack-sm">
                    <span className="px-2 py-1 bg-tertiary-container/20 text-tertiary text-[10px] font-bold rounded uppercase tracking-widest">Workflow Pro</span>
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-white mb-stack-sm">Individual Clip Export</h3>
                  <p className="font-body-md text-on-surface-variant">Your highlights are physically cut and exported as standalone .mp4 files, ready to be uploaded directly to TikTok, Shorts, and Reels.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="px-container-margin py-32 relative overflow-hidden">
          <div className="relative z-10 bg-[rgba(30,30,32,0.7)] backdrop-blur-2xl max-w-5xl mx-auto rounded-3xl p-12 text-center border border-white/20">
            <h2 className="font-headline-lg text-headline-lg mb-stack-md text-white">Ready to reclaim 80% of your editing time?</h2>
            <p className="font-body-lg text-on-surface-variant mb-stack-lg max-w-xl mx-auto">Join thousands of creators who use ClipSense to power their social media growth.</p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link to="/signup" className="bg-primary text-on-primary font-bold px-12 py-5 rounded-2xl text-body-lg hover:scale-105 transition-transform active:scale-95 shadow-2xl shadow-primary/20">
                Start Creating for Free
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="w-full py-stack-lg px-container-margin flex flex-col md:flex-row justify-between items-center gap-stack-md bg-surface-dim border-t border-white/5 mt-auto">
        <div className="flex flex-col gap-2">
          <span className="text-label-caps font-black text-on-surface-variant">CLIPSENSE</span>
          <p className="text-body-sm font-body-sm text-on-surface-variant/60 max-w-xs">© 2024 ClipSense AI. Professional Video Intelligence.</p>
        </div>
        <div className="flex gap-stack-lg">
          <a className="text-on-surface-variant hover:text-primary transition-all text-body-sm font-body-sm" href="#">Privacy Policy</a>
          <a className="text-on-surface-variant hover:text-primary transition-all text-body-sm font-body-sm" href="#">Terms of Service</a>
          <a className="text-on-surface-variant hover:text-primary transition-all text-body-sm font-body-sm" href="#">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
