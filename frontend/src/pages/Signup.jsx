import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import TurnstileWidget from "../components/TurnstileWidget";

// Use the environment variable instead of hard-coded localhost
const API_BASE = import.meta.env.VITE_API_BASE_URL;

export default function Signup() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [turnstileToken, setTurnstileToken] = useState("");
  const turnstileEnabled = Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY);

  if (user) return <Navigate to="/chat" />;

  const handleSignup = async () => {
    setError(null);
    try {
      // 1) Signup request
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          turnstile_token: turnstileToken || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Signup failed");

      // 2) Auto-login
      const loginRes = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const loginData = await loginRes.json();
      if (!loginRes.ok) throw new Error("Auto-login failed");

      localStorage.setItem("token", loginData.access_token);

      // 3) Decode token and set user
      const decoded = JSON.parse(atob(loginData.access_token.split(".")[1]));
      setUser({ email: decoded.sub });

      navigate("/chat");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen px-6 py-12">
      <div className="mx-auto w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-8 text-slate-100 shadow-2xl shadow-black/30 backdrop-blur">
        <div className="mb-6 space-y-2">
          <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Create access</p>
          <h1 className="text-2xl font-semibold">LLM Assistant</h1>
          <p className="text-sm text-slate-400">Start a new workspace in seconds.</p>
        </div>

        <div className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
          />
          {error && <p className="text-rose-300 text-xs">{error}</p>}
          <TurnstileWidget onVerify={setTurnstileToken} />
          <button
            onClick={handleSignup}
            disabled={turnstileEnabled && !turnstileToken}
            className="w-full rounded-2xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            Sign Up
          </button>
        </div>
      </div>
    </div>
  );
}
