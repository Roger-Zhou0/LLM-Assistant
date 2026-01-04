import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "../hooks/useAuth";

// Use the environment variable instead of hard-coded localhost
const API_BASE = import.meta.env.VITE_API_BASE_URL;
const SESSION_KEY = "chat_session_id";
const MODEL_KEY_PREFIX = "chat_model_selection:";
const generateSessionId = () => {
  if (crypto?.randomUUID) return crypto.randomUUID();
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export default function ChatInterface() {
  const { user, logout, loading, expiryMs } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const newId = generateSessionId();
    localStorage.setItem(SESSION_KEY, newId);
    return newId;
  });
  const [models, setModels] = useState([]);
  const [defaultModel, setDefaultModel] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  const bottomRef = useRef(null);

  // 1) On mount, fetch chat history
  useEffect(() => {
    if (!user) return;
    const token = localStorage.getItem("token");
    const url = new URL(`${API_BASE}/api/history`);
    url.searchParams.set("session_id", sessionId);
    fetch(url.toString(), {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load history");
        return res.json();
      })
      .then((data) => {
        setMessages(data.messages || []);
        if (data.session?.provider && data.session?.model) {
          const selection = { provider: data.session.provider, model: data.session.model };
          setSelectedModel(selection);
          localStorage.setItem(
            `${MODEL_KEY_PREFIX}${sessionId}`,
            JSON.stringify(selection)
          );
        }
      })
      .catch(() => setMessages([]));
  }, [user, sessionId]);

  useEffect(() => {
    if (!user) return;
    const token = localStorage.getItem("token");
    fetch(`${API_BASE}/api/models`, {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load models");
        return res.json();
      })
      .then((data) => {
        setModels(data.models || []);
        setDefaultModel(data.default || null);

        const saved = localStorage.getItem(`${MODEL_KEY_PREFIX}${sessionId}`);
        if (saved) {
          setSelectedModel(JSON.parse(saved));
        } else if (data.default) {
          setSelectedModel(data.default);
        }
      })
      .catch(() => {
        setModels([]);
      });
  }, [user, sessionId]);

  // 2) Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 3) Send a message (with Auto-Remember if enabled)
  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    const token = localStorage.getItem("token");
    if (!token) return;

    // Append the user message to the UI immediately
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setSending(true);

    try {
      // 3a) Call /api/chat for the response
      const payload = { message: trimmed, session_id: sessionId };
      if (selectedModel?.provider && selectedModel?.model) {
        payload.provider = selectedModel.provider;
        payload.model = selectedModel.model;
      }

      const chatRes = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!chatRes.ok) {
        const err = await chatRes.json();
        throw new Error(err.detail || "Chat request failed");
      }
      const chatData = await chatRes.json();
      const botReply = chatData.reply || "No response";
      if (chatData.session?.provider && chatData.session?.model) {
        const selection = {
          provider: chatData.session.provider,
          model: chatData.session.model,
        };
        setSelectedModel(selection);
        localStorage.setItem(
          `${MODEL_KEY_PREFIX}${sessionId}`,
          JSON.stringify(selection)
        );
      }

      // 3c) Append assistant's response
      setMessages((prev) => [...prev, { role: "assistant", content: botReply }]);
    } catch (err) {
      console.error("Send message error:", err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: " + err.message },
      ]);
    } finally {
      setSending(false);
    }
  };

  // 4) Handle Enter key in textarea
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startNewSession = () => {
    const newId = generateSessionId();
    localStorage.setItem(SESSION_KEY, newId);
    setSessionId(newId);
    setMessages([]);
    const saved = localStorage.getItem(`${MODEL_KEY_PREFIX}${newId}`);
    if (saved) {
      setSelectedModel(JSON.parse(saved));
    } else if (defaultModel) {
      setSelectedModel(defaultModel);
    } else {
      setSelectedModel(null);
    }
  };

  const handleModelChange = (e) => {
    const [provider, model] = e.target.value.split("::");
    const selection = { provider, model };
    setSelectedModel(selection);
    localStorage.setItem(`${MODEL_KEY_PREFIX}${sessionId}`, JSON.stringify(selection));
  };

  if (loading) {
    return <div className="text-white p-10">Loading...</div>;
  }
  if (!user) {
    return (
      <div className="text-slate-200 p-10">
        You must be logged in to view the chat.
      </div>
    );
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-5xl rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/20 backdrop-blur">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🧠</span>
            <div>
              <h1 className="text-xl font-semibold tracking-wide text-slate-50">LLM Assistant</h1>
              <p className="text-xs text-slate-400">Fast, focused, and private</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
              <span className="text-slate-400">Model</span>
              <select
                value={
                  selectedModel
                    ? `${selectedModel.provider}::${selectedModel.model}`
                    : ""
                }
                onChange={handleModelChange}
                className="bg-transparent text-slate-100 outline-none"
                disabled={!models.length}
              >
                {!models.length && <option value="">No models</option>}
                {models.map((spec) => (
                  <option
                    key={`${spec.provider}-${spec.model}`}
                    value={`${spec.provider}::${spec.model}`}
                  >
                    {spec.display_name}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={startNewSession}
              className="rounded-full border border-white/10 px-3 py-1 text-slate-200 hover:bg-white/10"
            >
              New chat
            </button>

            <div className="rounded-full border border-white/10 px-3 py-1 text-slate-300">
              {user.email}
            </div>

            <div className="rounded-full border border-white/10 px-3 py-1 text-amber-200">
              {Math.max(Math.floor(expiryMs / 1000), 0)}s
            </div>

            <button
              onClick={logout}
              className="rounded-full border border-white/10 px-3 py-1 text-rose-200 hover:bg-white/10"
            >
              Logout
            </button>
          </div>
        </header>

        <main className="flex h-[62vh] flex-col gap-4 overflow-y-auto py-6">
          {messages.length === 0 && (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 p-6 text-sm text-slate-400">
              Start a conversation. Your model choice applies to this session and can be switched at any time.
            </div>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`
                  max-w-[75%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm
                  ${msg.role === "user"
                    ? "bg-gradient-to-br from-sky-500 via-blue-600 to-indigo-600 text-white shadow-lg shadow-sky-500/20"
                    : "bg-white/10 text-slate-100 shadow-lg shadow-black/10"}
                `}
              >
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </main>

        <footer className="flex flex-col gap-3 border-t border-white/10 pt-4 md:flex-row">
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything…"
            className="flex-1 resize-none rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
            disabled={sending}
          />
          <button
            onClick={sendMessage}
            disabled={sending || !input.trim()}
            className="rounded-2xl bg-sky-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-500/30 transition hover:bg-sky-400 disabled:opacity-50"
          >
            {sending ? "…" : "Send"}
          </button>
        </footer>
      </div>
    </div>
  );
}
