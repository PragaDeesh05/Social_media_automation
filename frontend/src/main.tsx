import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';
import { api } from './services/api';

const RootApp: React.FC = () => {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const ensureAuth = async () => {
      const existingToken = localStorage.getItem('incubrix_auth_token');
      if (!existingToken) {
        try {
          await api.login('lead@incubrix.com', 'IncuBrix2026!');
        } catch (err) {
          console.warn('Auto-login could not connect to backend immediately. Will retry on demand.', err);
        }
      }
      setReady(true);
    };

    ensureAuth();
  }, []);

  if (!ready) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#1E293B] text-white">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-semibold tracking-wide text-slate-300">Initializing IncuBrix Growth Engine...</p>
        </div>
      </div>
    );
  }

  return (
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
};

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(<RootApp />);
