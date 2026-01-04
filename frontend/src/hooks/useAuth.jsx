import { useEffect, useState, createContext, useContext } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL;
const AuthContext = createContext();

function getTokenExpiry(token) {
  try {
    // Manually decode the JWT payload instead of using jwt-decode
    const decoded = JSON.parse(atob(token.split(".")[1]));
    if (!decoded.exp) return null;
    const expiryMs = decoded.exp * 1000;
    const timeLeftMs = expiryMs - Date.now();
    return timeLeftMs > 0 ? timeLeftMs : 0;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expiryMs, setExpiryMs] = useState(null);

  useEffect(() => {
    async function bootstrapAuth() {
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          const newToken = data.access_token;
          localStorage.setItem("token", newToken);

          // Manual decode:
          const decoded = JSON.parse(atob(newToken.split(".")[1]));
          setUser({ email: decoded.sub });
          setExpiryMs(decoded.exp * 1000 - Date.now());
          setLoading(false);
          return;
        }
      } catch {
        // ignore and fall back to existing token
      }

      const existingToken = localStorage.getItem("token");
      if (existingToken) {
        try {
          const meRes = await fetch(`${API_BASE}/auth/me`, {
            headers: { Authorization: `Bearer ${existingToken}` },
          });
          if (meRes.ok) {
            const data = await meRes.json();
            setUser(data);

            const timeLeft = getTokenExpiry(existingToken);
            setExpiryMs(timeLeft);
          } else {
            localStorage.removeItem("token");
            setUser(null);
          }
        } catch {
          localStorage.removeItem("token");
          setUser(null);
        }
      }
      setLoading(false);
    }

    bootstrapAuth();
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      const timeLeft = getTokenExpiry(token);
      setExpiryMs(timeLeft);

      if (timeLeft !== null && timeLeft < 60_000) {
        try {
          const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
          });
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            const newToken = data.access_token;
            localStorage.setItem("token", newToken);

            const decoded = JSON.parse(atob(newToken.split(".")[1]));
            setUser({ email: decoded.sub });
            setExpiryMs(decoded.exp * 1000 - Date.now());
          } else {
            logout();
          }
        } catch {
          logout();
        }
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [user]);

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, logout, loading, expiryMs }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
