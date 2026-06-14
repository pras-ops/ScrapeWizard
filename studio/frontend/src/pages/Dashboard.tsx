import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useStats, useRuns } from '../hooks/useApi';
import { Button, Card, CardHeader, CardTitle, CardContent, StatusPill, PageHeader, LoadingSkeleton, ErrorState, EmptyState } from '../components/ui';
import { Play, Plus, Activity, CheckCircle, Clock, Zap, ArrowRight, Kanban } from 'lucide-react';

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: stats, isLoading: statsLoading, error: statsError, refetch: refetchStats } = useStats();
  const { data: runs, isLoading: runsLoading, error: runsError, refetch: refetchRuns } = useRuns();

  const isLoading = statsLoading || runsLoading;
  const error = statsError || runsError;

  const handleRetry = () => {
    refetchStats();
    refetchRuns();
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 w-full">
        <div className="h-10 w-48 bg-slate-800/50 rounded-lg animate-pulse"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-28 bg-slate-800/40 rounded-xl border border-edge/30 animate-pulse"></div>
          ))}
        </div>
        <div className="h-64 bg-slate-850 rounded-xl border border-edge/30 animate-pulse"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 w-full max-w-2xl mx-auto">
        <ErrorState
          message="Failed to load dashboard data."
          details={error instanceof Error ? error.stack : String(error)}
          onRetry={handleRetry}
        />
      </div>
    );
  }

  const recentRuns = runs ? runs.slice(0, 5) : [];

  return (
    <div className="p-8 space-y-8 w-full max-w-7xl mx-auto">
      <PageHeader
        title="Studio Dashboard"
        description="Overview of test health and extraction metrics"
        actions={
          <Button onClick={() => navigate('/tests/new')} className="gap-2">
            <Plus className="w-4 h-4" />
            <span>New Test</span>
          </Button>
        }
      />

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardContent className="flex flex-col justify-between h-full min-h-24">
            <div className="flex justify-between items-center text-slate-400">
              <span className="text-xs font-semibold uppercase tracking-wider">Total Tests</span>
              <Activity className="w-5 h-5 text-run" />
            </div>
            <div className="mt-4">
              <span className="text-3xl font-bold text-white">{stats?.tests ?? 0}</span>
              <p className="text-[10px] text-text-muted mt-1">Recorded flows</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col justify-between h-full min-h-24">
            <div className="flex justify-between items-center text-slate-400">
              <span className="text-xs font-semibold uppercase tracking-wider">Success Rate (7d)</span>
              <CheckCircle className="w-5 h-5 text-pass" />
            </div>
            <div className="mt-4">
              <span className="text-3xl font-bold text-white">
                {stats?.pass_rate_7d === 0 && stats?.tests === 0 ? '—' : `${stats?.pass_rate_7d ?? 0}%`}
              </span>
              <p className="text-[10px] text-text-muted mt-1">From recent runs</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col justify-between h-full min-h-24">
            <div className="flex justify-between items-center text-slate-400">
              <span className="text-xs font-semibold uppercase tracking-wider">Runs Today</span>
              <Clock className="w-5 h-5 text-purple-400" />
            </div>
            <div className="mt-4">
              <span className="text-3xl font-bold text-white">{stats?.runs_today ?? 0}</span>
              <p className="text-[10px] text-text-muted mt-1">Executions completed</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col justify-between h-full min-h-24">
            <div className="flex justify-between items-center text-slate-400">
              <span className="text-xs font-semibold uppercase tracking-wider">AI Cost Spend</span>
              <Zap className="w-5 h-5 text-amber-400" />
            </div>
            <div className="mt-4">
              <span className="text-3xl font-bold text-white">${stats?.ai_spend.toFixed(4) ?? '0.0000'}</span>
              <p className="text-[10px] text-text-muted mt-1">Accumulated spend</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Runs */}
      <Card>
        <CardHeader className="flex justify-between items-center flex-row">
          <CardTitle>Recent Executions</CardTitle>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate('/runs')}
            className="text-xs gap-1"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </CardHeader>
        
        {recentRuns.length === 0 ? (
          <div className="p-12">
            <EmptyState
              icon={<Kanban className="h-8 w-8" />}
              title="No Executions"
              description="No tests have been executed yet. Go to the Test Suite to trigger a run."
              action={{
                label: "Go to Test Suite",
                onClick: () => navigate('/tests'),
              }}
            />
          </div>
        ) : (
          <div className="divide-y divide-edge/40">
            {recentRuns.map(run => (
              <div 
                key={run.id} 
                onClick={() => navigate(`/runs/${run.id}`)}
                className="px-6 py-4 flex items-center justify-between hover:bg-slate-850/40 cursor-pointer transition-colors"
              >
                <div className="space-y-1">
                  <p className="font-semibold text-white text-sm hover:text-primary transition-colors">{run.test_name}</p>
                  <p className="text-[11px] text-text-muted">Run ID: {run.id} · {new Date(run.started_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right text-xs text-slate-400">
                    <p className="font-mono">{run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}</p>
                    <p className="text-[10px] text-slate-600 font-mono mt-0.5">${run.ai_cost_usd.toFixed(4)}</p>
                  </div>
                  <StatusPill status={run.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
