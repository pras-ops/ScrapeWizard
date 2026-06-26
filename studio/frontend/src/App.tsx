import { createHashRouter, RouterProvider, Outlet, useNavigate, useLocation, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { api } from './lib/api';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Tests from './pages/Tests';
import NewTest from './pages/NewTest';
import TestDetail from './pages/TestDetail';
import RunDetail from './pages/RunDetail';
import RunHistory from './pages/RunHistory';
import { ToastContainer } from './components/ui/Toast';

import { LayoutDashboard, ShieldCheck, ListTodo, Settings as SettingsIcon, Brain, Sparkles } from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5000,
    },
  },
});

function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const path = location.pathname;

  const { data: aiSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: api.getSettings,
    refetchInterval: 30000,
  });

  const isActive = (paths: string[]) => {
    return paths.some(p => path === p || (p !== '/' && path.startsWith(p)));
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
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition cursor-pointer ${
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
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition cursor-pointer ${
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
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition cursor-pointer ${
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
              className={`w-full px-4 py-2.5 rounded-lg flex items-center gap-3 text-sm font-medium transition cursor-pointer ${
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
          <Outlet />
        </main>
      </div>

    </div>
  );
}

function TestDetailWrapper() {
  const { id } = useParams<{ id: string }>();
  return <TestDetail testId={id ? parseInt(id, 10) : 0} />;
}

function RunDetailWrapper() {
  const { id } = useParams<{ id: string }>();
  return <RunDetail runId={id ? parseInt(id, 10) : 0} />;
}

const router = createHashRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/dashboard', element: <Dashboard /> },
      { path: '/settings', element: <Settings /> },
      { path: '/tests', element: <Tests /> },
      { path: '/tests/new', element: <NewTest /> },
      { path: '/tests/:id', element: <TestDetailWrapper /> },
      { path: '/runs/:id', element: <RunDetailWrapper /> },
      { path: '/runs', element: <RunHistory /> },
      {
        path: '*',
        element: (
          <div className="p-8 text-center text-slate-400 w-full">
            <h2 className="text-xl font-bold text-white">404 Not Found</h2>
            <p className="mt-2">The requested route does not exist.</p>
          </div>
        )
      }
    ]
  }
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ToastContainer />
    </QueryClientProvider>
  );
}
