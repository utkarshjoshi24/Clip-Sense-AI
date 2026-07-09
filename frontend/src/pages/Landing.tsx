// src/pages/Landing.tsx — Dark minimal landing page

import { Link } from "react-router-dom";

export function Landing() {
  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-6 border-b border-border/50">
        <span className="text-text font-bold text-xl tracking-tight">
          Clip<span className="text-accent">Sense</span>
        </span>
        <div className="flex items-center gap-4">
          <Link to="/login" className="text-muted hover:text-text text-sm transition-colors">
            Sign in
          </Link>
          <Link to="/signup" className="btn-primary text-sm py-2 px-4">
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 text-center py-24">
        {/* Glow orb */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-accent/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-3xl animate-fade-in">
          <div className="inline-flex items-center gap-2 bg-accent/10 border border-accent/20 text-accent-light text-xs font-medium px-4 py-1.5 rounded-full mb-8">
            <span className="w-1.5 h-1.5 bg-accent-light rounded-full animate-pulse" />
            AI-powered highlight detection
          </div>

          <h1 className="text-5xl sm:text-7xl font-extrabold text-text leading-[1.05] tracking-tight mb-6">
            Turn hours of footage
            <br />
            <span className="text-accent">into killer clips.</span>
          </h1>

          <p className="text-muted text-lg sm:text-xl max-w-xl mx-auto mb-10 leading-relaxed">
            ClipSense analyzes your long-form video using audio energy, scene changes,
            and speech patterns to find the moments worth sharing.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/signup" className="btn-primary text-base py-3 px-8">
              Start for free
            </Link>
            <a
              href="https://github.com/utkarshjoshi24/Clip-Sense-AI"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-base py-3 px-8"
            >
              View on GitHub
            </a>
          </div>
        </div>

        {/* Feature grid */}
        <div className="relative grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl w-full mt-24 animate-slide-up">
          {[
            { icon: "🔊", title: "Audio Energy", desc: "Detects loud moments, music hits, and crowd reactions" },
            { icon: "✂️", title: "Scene Detection", desc: "Finds natural cut points so clips never start mid-sentence" },
            { icon: "💬", title: "Transcript Analysis", desc: "Scores hook words and high-engagement phrasing patterns" },
          ].map((f) => (
            <div key={f.title} className="card text-left hover:border-accent/30 transition-colors">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="text-text font-semibold mb-1">{f.title}</h3>
              <p className="text-muted text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
