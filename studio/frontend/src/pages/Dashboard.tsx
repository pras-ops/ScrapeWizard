import React, { useEffect, useState } from 'react';
import { api, DashboardStats, RunSummary } from '../lib/api';
import { Play, Plus, Activity, CheckCircle, Clock, Zap, ArrowRight } from 'lucide-react';

interface DashboardProps {
  onNavigate: (route: string) => void;
}

export default function Dashboard({ onNavigate }: DashboardProps) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true);
        const [statsData, runsData] = await Promise.all([
          api.getStats(),
          api.listRuns()
        ]);
        setStats(statsData);
        setRuns(runsData.slice(0, 5));
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load dashboard.');
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  if (loading) {
    return (
      <div className="p-8 space-y-6 w-full animate-pulse">
        <div className="h-10 w-48 bg-slate-700/50 rounded-lg"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-28 bg-slate-800/40 rounded-xl border border-slate-700/30"></div>
          ))}
        </div>
        <div className="h-64 bg-slate-800/20 rounded-xl border border-slate-700/20"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-xl mx-auto text-center space-y-4">
        <h2 className="text-2xl font-bold text-red-400">Failed to Load Dashboard</h2>
        <p className="text-slate-400">{error}</p>
        <button 
          onClick={() => window.location.reload()} 
          className="px-4 py-2 bg-primary hover:bg-primary/90 rounded-lg font-medium transition"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white display-font">Studio Dashboard</h1>
          <p className="text-slate-400 mt-1">Overview of test health and extraction metrics</p>
        </div>
        <button
          onClick={() => onNavigate('/tests/new')}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg shadow-lg hover:shadow-blue-500/10 transition duration-150"
        >
          <Plus className="w-5 h-5" />
          <span>New Test</span>
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="p-6 bg-slate-850 rounded-xl border border-slate-750 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-sm font-medium">Total Tests</span>
            <Activity className="w-5 h-5 text-blue-400" />
          </div>
          <div className="mt-4">
            <span className="text-3xl font-bold text-white">{stats?.tests || 0}</span>
            <p className="text-xs text-slate-500 mt-1">Recorded scrapers</p>
          </div>
        </div>

        <div className="p-6 bg-slate-850 rounded-xl border border-slate-750 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-sm font-medium">Success Rate (7d)</span>
            <CheckCircle className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="mt-4">
            <span className="text-3xl font-bold text-white">
              {stats?.pass_rate_7d === 0 && stats?.tests === 0 ? '—' : `${stats?.pass_rate_7d}%`}
            </span>
            <p className="text-xs text-slate-500 mt-1">From recent runs</p>
          </div>
        </div>

        <div className="p-6 bg-slate-850 rounded-xl border border-slate-750 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-sm font-medium">Runs Today</span>
            <Clock className="w-5 h-5 text-purple-400" />
          </div>
          <div className="mt-4">
            <span className="text-3xl font-bold text-white">{stats?.runs_today || 0}</span>
            <p className="text-xs text-slate-500 mt-1">Executions enqueued</p>
          </div>
        </div>

        <div className="p-6 bg-slate-850 rounded-xl border border-slate-750 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-sm font-medium">AI Cost Spend</span>
            <Zap className="w-5 h-5 text-amber-400" />
          </div>
          <div className="mt-4">
            <span className="text-3xl font-bold text-white">${stats?.ai_spend.toFixed(4) || '0.0000'}</span>
            <p className="text-xs text-slate-500 mt-1">Accumulated spend</p>
          </div>
        </div>
      </div>

      {/* Recent Runs */}
      <div className="bg-slate-850 rounded-xl border border-slate-750 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-750 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-white display-font">Recent Executions</h2>
          <button 
            onClick={() => onNavigate('/runs')}
            className="text-sm text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 hover:gap-1.5 transition-all"
          >
            <span>View All</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        
        {runs.length === 0 ? (
          <div className="p-12 text-center space-y-4">
            <p className="text-slate-400">No test runs executed yet.</p>
            <button
              onClick={() => onNavigate('/tests')}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-750 text-white border border-slate-700/50 rounded-lg font-medium transition"
            >
              Go to Test Suite
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-750">
            {runs.map(run => (
              <div 
                key={run.id} 
                onClick={() => onNavigate(`/runs/${run.id}`)}
                className="px-6 py-4 flex items-center justify-between hover:bg-slate-800/40 cursor-pointer transition"
              >
                <div className="space-y-1">
                  <p className="font-semibold text-white text-sm">{run.test_name}</p>
                  <p className="text-xs text-slate-500">Run ID: {run.id} · {new Date(run.started_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right text-xs text-slate-400">
                    <p>{run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}</p>
                    <p className="text-slate-600 mt-0.5">${run.ai_cost_usd.toFixed(4)}</p>
                  </div>
                  <span className={`px-2.5 py-1 text-xs font-semibold rounded-full capitalize ${
                    run.status === 'passed' ? 'bg-emerald-500/10 text-emerald-400' :
                    run.status === 'failed' ? 'bg-rose-500/10 text-rose-400' :
                    run.status === 'running' ? 'bg-blue-500/10 text-blue-400 animate-pulse' :
                    'bg-slate-500/10 text-slate-400'
                  }`}>
                    {run.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
