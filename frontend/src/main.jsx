import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter as Router } from 'react-router-dom';
import AppShell from './pages/AppShell';
import './index.css';
import { AuthProvider } from "./hooks/useAuth";

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </Router>
  </StrictMode>
);
