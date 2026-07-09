// src/pages/Signup.tsx

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";

export function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authApi.signup(email, password);
      setDone(true);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-sm card text-center space-y-4 animate-fade-in">
          <div className="text-4xl">📬</div>
          <h2 className="text-xl font-bold text-text">Check your inbox</h2>
          <p className="text-muted text-sm">
            We sent a verification link to <strong className="text-text">{email}</strong>. Click it to activate your account.
          </p>
          <Link to="/login" className="btn-primary block w-full text-center">
            Go to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm animate-fade-in">
        <Link to="/" className="block text-center text-text font-bold text-2xl mb-8">
          Clip<span className="text-accent">Sense</span>
        </Link>

        <div className="card">
          <h1 className="text-xl font-bold text-text mb-1">Create your account</h1>
          <p className="text-muted text-sm mb-6">Free plan: 3 videos/month · 15 min max</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-muted mb-1.5">Email</label>
              <input
                type="email" required
                className="input-field"
                placeholder="you@example.com"
                value={email} onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1.5">Password</label>
              <input
                type="password" required minLength={8}
                className="input-field"
                placeholder="Min. 8 chars, 1 uppercase, 1 number"
                value={password} onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <p className="text-error text-sm bg-error/10 border border-error/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? "Creating account..." : "Create account"}
            </button>
          </form>
        </div>

        <p className="text-center text-muted text-sm mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-accent hover:text-accent-light transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
