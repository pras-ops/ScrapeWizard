import { useNavigate } from 'react-router-dom';
import { useRuns } from '../hooks/useApi';
import { Card, StatusPill, PageHeader, ErrorState, EmptyState } from '../components/ui';
import { Clock, Zap, Activity } from 'lucide-react';

export default function RunHistory() {
  const navigate = useNavigate();
  const { data: runs, isLoading, error, refetch } = useRuns();

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 w-full max-w-6xl mx-auto">
        <div className="h-10 w-48 bg-slate-800/50 rounded-lg animate-pulse"></div>
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-slate-800/40 rounded-xl animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 w-full max-w-2xl mx-auto">
        <ErrorState
          message="Failed to load execution run history."
          details={error instanceof Error ? error.stack : String(error)}
          onRetry={refetch}
        />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full max-w-7xl mx-auto">
      <PageHeader
        title="Execution History"
        description="Audit log of all automated sandbox test flow executions"
      />

      {!runs || runs.length === 0 ? (
        <div className="max-w-2xl mx-auto">
          <EmptyState
            icon={<Activity className="h-8 w-8" />}
            title="No Executions Found"
            description="No test runs have been recorded or executed yet. Go to the Test Suite to launch your first flow."
            action={{
              label: "Go to Test Suite",
              onClick: () => navigate('/tests'),
            }}
          />
        </div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-edge/40 bg-slate-800/40 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-4">Test Flow</th>
                  <th className="px-6 py-4">Run ID</th>
                  <th className="px-6 py-4">Started At</th>
                  <th className="px-6 py-4">Duration</th>
                  <th className="px-6 py-4">AI Spent</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-edge/40 text-xs text-slate-300">
                {runs.map(run => (
                  <tr 
                    key={run.id}
                    onClick={() => navigate(`/runs/${run.id}`)}
                    className="hover:bg-slate-850/40 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 font-semibold text-white text-sm hover:text-primary transition-colors">
                      {run.test_name}
                    </td>
                    <td className="px-6 py-4 font-mono text-text-muted">{run.id}</td>
                    <td className="px-6 py-4 text-text-muted">{new Date(run.started_at).toLocaleString()}</td>
                    <td className="px-6 py-4">
                      <span className="flex items-center gap-1 font-mono">
                        <Clock className="w-3.5 h-3.5 text-text-muted" />
                        <span>{run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono">
                      <span className="flex items-center gap-1">
                        <Zap className="w-3.5 h-3.5 text-amber-500" />
                        <span>${run.ai_cost_usd.toFixed(4)}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <StatusPill status={run.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
