import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";

// Use the environment variable instead of hard-coded localhost
const API_BASE = import.meta.env.VITE_API_BASE_URL;

export default function MemoryView() {
  // We still grab user, logout, and loading from `useAuth`
  const { user, logout, loading } = useAuth();

  // But instead of “const { token } = useAuth()”, we read the JWT directly:
  const token = localStorage.getItem("token");

  const [memory, setMemory] = useState([]);
  const [offset, setOffset] = useState(0);
  const limit = 10;

  const [newEntry, setNewEntry] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // 1) Fetch memory whenever `offset`, `token`, or `user` changes
  const fetchMemory = async () => {
    if (!token) return; // If no token, bail out (not logged in)
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE}/api/memory?offset=${offset}&limit=${limit}`,
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to load memory");
      }
      const data = await res.json();
      setMemory(data.memory || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (user && token) {
      fetchMemory();
    }
  }, [offset, token, user]);

  // 2) “Remember” a new string manually
  const handleRemember = async (e) => {
    e.preventDefault();
    if (!newEntry.trim() || !token) return;

    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/remember`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ query: newEntry.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to remember");
      }
      // Clear input, reset to first page, then reload
      setNewEntry("");
      setOffset(0);
      await fetchMemory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // 3) Delete a single memory entry
  const handleDelete = async (index) => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const globalIndex = offset + index;
      const res = await fetch(
        `${API_BASE}/api/memory/${globalIndex}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete");
      }
      await fetchMemory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // 4) Clear all memory
  const handleClearAll = async () => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/memory`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to clear");
      }
      setOffset(0);
      await fetchMemory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // 5) Pagination controls
  const prevPage = () => {
    if (offset === 0) return;
    setOffset((prev) => Math.max(prev - limit, 0));
  };
  const nextPage = () => {
    if (memory.length < limit) return;
    setOffset((prev) => prev + limit);
  };

  // 6) Render
  if (loading) {
    return <div className="text-white p-10">Loading...</div>;
  }
  if (!user) {
    return (
      <div className="text-white p-10">
        You must be logged in to view your memory.
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6 bg-gray-900 text-white">
      {/* Header with Logout */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">🧠 Your Memory</h1>
        <button
          onClick={logout}
          className="text-red-400 hover:underline text-sm"
        >
          Logout
        </button>
      </div>

      {/* Error Banner */}
      {error && <p className="text-red-400">{error}</p>}

      {/* Form to “Remember” a new entry */}
      <form onSubmit={handleRemember} className="flex gap-2">
        <input
          type="text"
          value={newEntry}
          onChange={(e) => setNewEntry(e.target.value)}
          placeholder="Enter something to remember..."
          className="flex-grow rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:outline-none"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !newEntry.trim()}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded disabled:opacity-40"
        >
          {busy ? "…" : "Remember"}
        </button>
      </form>

      {/* Clear All Button */}
      <button
        onClick={handleClearAll}
        disabled={busy}
        className="text-sm text-red-500 hover:underline disabled:opacity-40"
      >
        Clear All Memory
      </button>

      {/* Memory List or Loading/Empty State */}
      {busy ? (
        <p>Loading…</p>
      ) : memory.length === 0 ? (
        <p className="text-gray-400">No memory stored yet.</p>
      ) : (
        <div className="space-y-4">
          {memory.map((chunk, idx) => (
            <div key={idx} className="relative bg-gray-800 p-4 rounded-md">
              <button
                onClick={() => handleDelete(idx)}
                disabled={busy}
                className="absolute top-2 right-2 text-red-400 hover:text-red-600 text-sm"
              >
                ✖
              </button>
              <p className="whitespace-pre-wrap text-sm text-gray-200">{chunk}</p>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      <div className="mt-6 flex justify-between">
        <button
          onClick={prevPage}
          disabled={busy || offset === 0}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded disabled:opacity-40"
        >
          ← Previous
        </button>

        <button
          onClick={nextPage}
          disabled={busy || memory.length < limit}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded disabled:opacity-40"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
