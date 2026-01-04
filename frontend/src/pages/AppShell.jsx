import { Routes, Route, Navigate } from "react-router-dom";
import ChatInterface from "./ChatInterface";
import Login from "./Login";
import Signup from "./Signup";
import PrivateRoute from "./PrivateRoute";
import { useAuth } from "../hooks/useAuth.jsx";
import React from "react";


export default function AppShell() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="text-slate-200 p-10">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(1200px_circle_at_20%_-10%,rgba(56,189,248,0.18),transparent_55%),radial-gradient(900px_circle_at_90%_10%,rgba(251,191,36,0.14),transparent_45%),linear-gradient(180deg,#0b1220,rgba(8,13,24,0.98))] text-slate-100">
      <main className="min-h-screen">
        <Routes>
          <Route path="/" element={user ? <Navigate to="/chat" /> : <Navigate to="/login" />} />
          <Route path="/chat" element={<PrivateRoute><ChatInterface /></PrivateRoute>} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
        </Routes>
      </main>
      {user && (
        <div className="fixed bottom-6 right-6 text-xs text-slate-300">
          {user.email}
        </div>
      )}
    </div>
  );
}
