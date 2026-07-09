// src/pages/ForgotPassword.tsx

import { useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../api/auth";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

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
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm animate-fade-in">
        <Link to="/" className="block text-center text-text font-bold text-2xl mb-8">
          Clip<span className="text-accent">Sense</span>
        </Link>
        <div className="card">
          {sent ? (
            <div className="text-center space-y-3">
              <div className="text-3xl">📧</div>
              <h2 className="text-lg font-bold text-text">Check your email</h2>
              <p className="text-muted text-sm">If that address is registered, you'll receive a reset link shortly.</p>
              <Link to="/login" className="btn-primary block w-full text-center mt-4">Back to sign in</Link>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-bold text-text mb-1">Reset password</h1>
              <p className="text-muted text-sm mb-6">Enter your email and we'll send a reset link.</p>
              <form onSubmit={handleSubmit} className="space-y-4">
                <input type="email" required className="input-field" placeholder="you@example.com"
                  value={email} onChange={(e) => setEmail(e.target.value)} />
                <button type="submit" disabled={loading} className="btn-primary w-full">
                  {loading ? "Sending..." : "Send reset link"}
                </button>
              </form>
              <Link to="/login" className="block text-center text-muted text-sm mt-4 hover:text-text transition-colors">
                ← Back to sign in
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// src/pages/VerifyEmail.tsx
export function VerifyEmail() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="card max-w-sm w-full text-center space-y-4 animate-fade-in">
        <div className="text-4xl">✅</div>
        <h2 className="text-xl font-bold text-text">Email verified!</h2>
        <p className="text-muted text-sm">Your account is now active.</p>
        <Link to="/login" className="btn-primary block w-full text-center">
          Sign in
        </Link>
      </div>
    </div>
  );
}
