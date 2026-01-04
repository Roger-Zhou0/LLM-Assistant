import { useState } from "react";
import { useNavigate, Link, Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import TurnstileWidget from "../components/TurnstileWidget";

const API_BASE = import.meta.env.VITE_API_BASE_URL;

export default function Login() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [turnstileToken, setTurnstileToken] = useState("");
  const turnstileEnabled = Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY);

  if (user) return <Navigate to="/chat" />;

  const handleLogin = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          turnstile_token: turnstileToken || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");

      localStorage.setItem("token", data.access_token);

      // Decode token and set user
      const decoded = JSON.parse(atob(data.access_token.split(".")[1]));
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
          <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Welcome back</p>
          <h1 className="text-2xl font-semibold">LLM Assistant</h1>
          <p className="text-sm text-slate-400">Sign in to continue your sessions.</p>
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
            onClick={handleLogin}
            disabled={turnstileEnabled && !turnstileToken}
            className="w-full rounded-2xl bg-sky-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-500/30 transition hover:bg-sky-400 disabled:opacity-50"
          >
            Log In
          </button>
          <p className="text-sm text-slate-400">
            Don't have an account?{" "}
            <Link to="/signup" className="text-sky-300 hover:text-sky-200">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
