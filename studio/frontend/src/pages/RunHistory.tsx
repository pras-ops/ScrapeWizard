import React, { useEffect, useState } from 'react';
import { api, RunSummary } from '../lib/api';
import { ArrowLeft, Clock, Zap, CheckCircle2, ShieldAlert, RefreshCw } from 'lucide-react';

interface RunHistoryProps {
  onNavigate: (route: string) => void;
}

export default function RunHistory({ onNavigate }: RunHistoryProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const data = await api.listRuns();
      setRuns(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load execution run history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  if (loading && runs.length === 0) {
    return (
      <div className="p-8 space-y-6 w-full animate-pulse">
        <div className="h-10 w-48 bg-slate-700/50 rounded-lg"></div>
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-slate-800/40 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold text-rose-400">Failed to load run history</h2>
        <p className="text-slate-400">{error}</p>
        <button onClick={loadRuns} className="px-4 py-2 bg-slate-800 rounded-lg">Retry</button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white display-font">Execution History</h1>
        <p className="text-slate-400 mt-1">Audit log of all automated sandbox scraper executions</p>
      </div>

      {runs.length === 0 ? (
        <div className="border border-slate-750 bg-slate-850 rounded-xl p-16 text-center max-w-2xl mx-auto space-y-4">
          <p className="text-slate-400">No test runs executed yet.</p>
        </div>
      ) : (
        <div className="bg-slate-850 border border-slate-750 rounded-xl overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-750 bg-slate-800/40 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <th className="px-6 py-4">Test Flow</th>
                <th className="px-6 py-4">Run ID</th>
                <th className="px-6 py-4">Started At</th>
                <th className="px-6 py-4">Duration</th>
                <th className="px-6 py-4">AI Spent</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-750 text-sm text-slate-300">
              {runs.map(run => (
                <tr 
                  key={run.id}
                  onClick={() => onNavigate(`/runs/${run.id}`)}
                  className="hover:bg-slate-800/40 cursor-pointer transition"
                >
                  <td className="px-6 py-4 font-semibold text-white">{run.test_name}</td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-500">{run.id}</td>
                  <td className="px-6 py-4 text-xs">{new Date(run.started_at).toLocaleString()}</td>
                  <td className="px-6 py-4 text-xs flex items-center gap-1 mt-1">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    <span>{run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}</span>
                  </td>
                  <td className="px-6 py-4 text-xs font-mono">
                    <span className="flex items-center gap-1">
                      <Zap className="w-3.5 h-3.5 text-amber-500" />
                      <span>${run.ai_cost_usd.toFixed(4)}</span>
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 text-xs font-semibold rounded-full capitalize ${
                      run.status === 'passed' ? 'bg-emerald-500/10 text-emerald-400' :
                      run.status === 'failed' ? 'bg-rose-500/10 text-rose-400' :
                      run.status === 'running' || run.status === 'queued' ? 'bg-blue-500/10 text-blue-400 animate-pulse' :
                      'bg-slate-500/10 text-slate-400'
                    }`}>
                      {run.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
