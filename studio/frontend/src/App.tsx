import React, { useState, useEffect } from 'react';
import { api, SettingData } from './lib/api';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Tests from './pages/Tests';
import NewTest from './pages/NewTest';
import TestDetail from './pages/TestDetail';
import RunDetail from './pages/RunDetail';
import RunHistory from './pages/RunHistory';

import { LayoutDashboard, ShieldCheck, ListTodo, Settings as SettingsIcon, Brain, Sparkles } from 'lucide-react';

export default function App() {
  // Simple, bulletproof hash routing for local FastAPI static mounts
  const [route, setRoute] = useState<string>(() => {
    return window.location.hash.slice(1) || '/';
  });

  const [aiSettings, setAiSettings] = useState<SettingData | null>(null);

  useEffect(() => {
    const handleHashChange = () => {
      setRoute(window.location.hash.slice(1) || '/');
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (newRoute: string) => {
    window.location.hash = newRoute;
    setRoute(newRoute);
  };

  const loadAiStats = async () => {
    try {
      const data = await api.getSettings();
      setAiSettings(data);
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    loadAiStats();
    // Refresh stats periodically
    const interval = setInterval(loadAiStats, 10000);
    return () => clearInterval(interval);
  }, [route]);

  // Route matching
  const renderContent = () => {
    if (route === '/' || route === '/dashboard') {
      return <Dashboard onNavigate={navigate} />;
    }
    if (route === '/settings') {
      return <Settings />;
    }
    if (route === '/tests') {
      return <Tests onNavigate={navigate} />;
    }
    if (route === '/tests/new') {
      return <NewTest onNavigate={navigate} />;
    }
    if (route.startsWith('/tests/')) {
      const id = parseInt(route.split('/')[2], 10);
      return <TestDetail testId={id} onNavigate={navigate} />;
    }
    if (route.startsWith('/runs/')) {
      const id = parseInt(route.split('/')[2], 10);
      return <RunDetail runId={id} onNavigate={navigate} />;
    }
    if (route === '/runs') {
      return <RunHistory onNavigate={navigate} />;
    }
    return (
      <div className="p-8 text-center text-slate-400">
        <h2 className="text-xl font-bold text-white">404 Not Found</h2>
        <p className="mt-2">The requested route does not exist.</p>
        <button onClick={() => navigate('/')} className="mt-4 px-4 py-2 bg-blue-600 rounded-lg">Go Home</button>
      </div>
    );
  };

  const isActive = (paths: string[]) => {
    return paths.some(p => route === p || (p !== '/' && route.startsWith(p)));
  };

  return (
    <div className="flex min-h-screen bg-[#101622] text-slate-100 font-sans w-screen overflow-x-hidden">
      
      {/* Sidebar Layout */}
      <aside className="w-64 bg-[#192233] border-r border-[#324467] flex flex-col justify-between shrink-0">
        <div>
          {/* Sidebar Header */}
          <div className="px-6 py-5 border-b border-[#324467] flex items-center gap-3">
            <div className="p-1.5 bg-blue-600 rounded-lg text-white">
              <Brain className="w-6 h-6" />
            </div>
            <div>
              <span className="font-bold text-lg text-white tracking-wide block leading-none display-font">ScrapeWizard</span>
              <span className="text-[10px] text-slate-500 font-mono">STUDIO v1.2.0</span>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-4 space-y-1.5">
            <button
              onClick={() => navigate('/')}
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition ${
                isActive(['/', '/dashboard']) 
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/10' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <LayoutDashboard className="w-5 h-5" />
              <span>Dashboard</span>
            </button>

            <button
              onClick={() => navigate('/tests')}
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition ${
                isActive(['/tests']) 
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/10' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <ListTodo className="w-5 h-5" />
              <span>Test Suite</span>
            </button>

            <button
              onClick={() => navigate('/runs')}
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition ${
                isActive(['/runs']) 
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/10' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <ShieldCheck className="w-5 h-5" />
              <span>Executions</span>
            </button>

            <button
              onClick={() => navigate('/settings')}
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition ${
                isActive(['/settings']) 
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/10' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <SettingsIcon className="w-5 h-5" />
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Footer info */}
        <div className="p-4 border-t border-[#324467] text-xs text-slate-500 text-center">
          <p>© 2026 ScrapeWizard</p>
          <p className="mt-1 font-mono text-[10px]">Localhost environment</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen">
        
        {/* Top Header Panel */}
        <header className="h-16 border-b border-[#324467] bg-[#192233] px-8 flex justify-end items-center shrink-0">
          {aiSettings && (
            <div className="flex items-center gap-2 px-3 py-1 bg-slate-850/80 border border-slate-750 rounded-full text-xs text-slate-300">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>AI Mode: <strong className="text-white">{aiSettings.ai_mode}</strong></span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">Provider: <strong className="text-white capitalize">{aiSettings.provider}</strong></span>
            </div>
          )}
        </header>

        {/* Dynamic view */}
        <main className="flex-1 overflow-y-auto flex bg-[#101622]">
          {renderContent()}
        </main>
      </div>

    </div>
  );
}
