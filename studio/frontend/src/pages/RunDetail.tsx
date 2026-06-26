import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRun } from '../hooks/useApi';
import { Button, Card, CardHeader, CardTitle, CardContent, StatusPill, ErrorState } from '../components/ui';
import { ArrowLeft, Clock, Zap, ShieldAlert, CheckCircle2, RefreshCw, Layers } from 'lucide-react';
import { API_BASE } from '../lib/api';

interface RunDetailProps {
  runId: number;
}

export default function RunDetail({ runId }: RunDetailProps) {
  const navigate = useNavigate();
  const [selectedStepIdx, setSelectedStepIdx] = useState<number | null>(null);

  // Poll every 1.5s if the run is active (running/queued)
  const { data: run, isLoading, error, refetch } = useRun(
    runId,
    runId > 0 ? (r) => (r.state.data?.status === 'running' || r.state.data?.status === 'queued' ? 1500 : false) : false
  );

  // Default to first failing step or step 0
  useEffect(() => {
    if (run && selectedStepIdx === null && run.step_results.length > 0) {
      const firstFail = run.step_results.findIndex(
        r => r.status === 'failed' || r.status === 'error'
      );
      setSelectedStepIdx(firstFail !== -1 ? firstFail : 0);
    }
  }, [run, selectedStepIdx]);

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 w-full max-w-6xl mx-auto">
        <div className="h-10 w-48 bg-slate-800/50 rounded-lg animate-pulse"></div>
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-1 h-96 bg-slate-800/40 rounded-xl animate-pulse"></div>
          <div className="col-span-2 h-96 bg-slate-850/40 rounded-xl animate-pulse"></div>
        </div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="p-8 w-full max-w-2xl mx-auto">
        <ErrorState
          message="Failed to load execution details."
          details={error instanceof Error ? error.stack : String(error)}
          onRetry={refetch}
        />
        <Button onClick={() => navigate('/tests')} variant="secondary" className="mt-4">
          Back to Suite
        </Button>
      </div>
    );
  }
  const selectedStep = selectedStepIdx !== null ? run.step_results[selectedStepIdx] : undefined;

  return (
    <div className="p-8 space-y-6 w-full max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start gap-4">
        <div className="space-y-1">
          <Button
            variant="ghost"
            onClick={() => navigate(`/tests/${run.test_id}`)}
            className="text-slate-400 hover:text-white mb-2"
            size="sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Test Manager</span>
          </Button>
          <h1 className="text-2xl font-bold text-white display-font">Run Execution: {run.test_name}</h1>
          <p className="text-[11px] text-text-muted">
            Run ID: {run.id} · Started at {new Date(run.started_at).toLocaleString()}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 bg-slate-850 p-4 border border-edge/60 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-mono">
            <Clock className="w-4 h-4 text-run" />
            <span>Duration: {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs font-mono">
            <Zap className="w-4 h-4 text-amber-400" />
            <span>Spend: ${run.ai_cost_usd.toFixed(4)}</span>
          </div>
          <StatusPill status={run.status} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Timeline */}
        <div className="md:col-span-1 h-fit">
          <Card>
            <CardHeader>
              <CardTitle className="text-xs uppercase tracking-wider text-text-muted">Timeline Steps</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 max-h-[600px] overflow-y-auto">
              {run.step_results.length === 0 ? (
                <p className="text-xs text-text-muted italic py-4 text-center">No steps executed yet.</p>
              ) : (
                run.step_results.map((res, i) => (
                  <div
                    key={i}
                    onClick={() => setSelectedStepIdx(i)}
                    className={`w-full p-3.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                      selectedStepIdx === i 
                        ? 'bg-primary/10 border-primary text-white shadow-xs' 
                        : 'bg-slate-800/40 border-edge/40 text-slate-300 hover:border-edge'
                    }`}
                  >
                    <div className="flex items-center gap-3 truncate">
                      {res.status === 'passed' ? <CheckCircle2 className="w-4.5 h-4.5 text-pass shrink-0" /> :
                       res.status === 'failed' || res.status === 'error' ? <ShieldAlert className="w-4.5 h-4.5 text-fail shrink-0" /> :
                       <RefreshCw className="w-4.5 h-4.5 text-run animate-spin shrink-0" />}
                      <span className="font-semibold text-xs truncate">{res.step_name}</span>
                    </div>
                    <span className="text-[10px] text-text-muted shrink-0 font-mono">{res.duration_ms}ms</span>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Evidence Panel */}
        <div className="md:col-span-2">
          <Card className="h-full min-h-[400px]">
            {selectedStep ? (
              <CardContent className="space-y-6 p-6">
                <div className="flex justify-between items-center border-b border-edge/40 pb-4">
                  <div>
                    <h3 className="text-base font-bold text-white display-font">{selectedStep.step_name}</h3>
                    <p className="text-[11px] text-text-muted font-mono mt-0.5">Duration: {selectedStep.duration_ms} ms</p>
                  </div>
                  <div className="flex gap-2">
                    {selectedStep.healed && <StatusPill status="passed" healed={true} />}
                    <StatusPill status={selectedStep.status} />
                  </div>
                </div>

                {selectedStep.error_message && (
                  <div className="p-4 bg-fail/5 border border-fail/20 text-fail text-xs rounded-lg flex items-start gap-2.5">
                    <ShieldAlert className="w-4.5 h-4.5 shrink-0 mt-0.5" />
                    <pre className="font-mono text-xs whitespace-pre-wrap">{selectedStep.error_message}</pre>
                  </div>
                )}

                <div className="space-y-6">
                  {/* Page Screenshot & Visual Diffs */}
                  {selectedStep.screenshot_path && (
                    <div className="space-y-3">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                        <Layers className="w-4 h-4 text-run" />
                        <span>Visual Evidence & Checks</span>
                      </h4>
                      
                      {selectedStep.visual_diff_score !== null && (
                        <div className="p-3 bg-slate-800/60 border border-edge/60 rounded-lg flex justify-between items-center text-xs">
                          <span className="text-slate-400">Visual Deviation Score:</span>
                          <span className={`font-semibold font-mono ${
                            selectedStep.visual_diff_score > 0.05 ? 'text-warn' : 'text-slate-300'
                          }`}>
                            {(selectedStep.visual_diff_score * 100).toFixed(1)}% difference
                          </span>
                        </div>
                      )}

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="border border-edge/60 rounded-xl overflow-hidden bg-slate-900/60 flex flex-col">
                          <div className="px-4 py-2 border-b border-edge/40 bg-slate-800/40 text-[10px] uppercase font-semibold text-text-muted tracking-wider">
                            Execution Screenshot
                          </div>
                          <img 
                            src={`${API_BASE}${selectedStep.screenshot_path}`} 
                            alt="Execution Screenshot" 
                            className="w-full max-h-96 object-contain p-2"
                          />
                        </div>
                        
                        {selectedStep.visual_diff_score !== null && selectedStep.visual_diff_score > 0.05 && (
                          <div className="border border-edge/60 rounded-xl overflow-hidden bg-slate-900/60 flex flex-col">
                            <div className="px-4 py-2 border-b border-edge/40 bg-slate-800/40 text-[10px] uppercase font-semibold text-warn tracking-wider">
                              Visual Regression Diff Image
                            </div>
                            <img 
                              src={`${API_BASE}/artifacts/run_${runId}/diffs/diff_${selectedStep.step_name}.png`} 
                              alt="Visual diff" 
                              className="w-full max-h-96 object-contain p-2"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Console & Network Errors */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold text-text-muted uppercase tracking-wider">
                        Console Logs ({selectedStep.console_errors.length})
                      </h4>
                      {selectedStep.console_errors.length > 0 ? (
                        <div className="bg-slate-900 border border-edge/65 rounded-lg p-3 max-h-48 overflow-y-auto space-y-1.5 font-mono text-[11px] text-rose-300">
                          {selectedStep.console_errors.map((err, i) => (
                            <div key={i} className="border-b border-edge/20 pb-1.5 last:border-0 last:pb-0">{err}</div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-text-muted italic">No console errors logged.</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <h4 className="text-xs font-bold text-text-muted uppercase tracking-wider">
                        Network Failures ({selectedStep.network_errors.length})
                      </h4>
                      {selectedStep.network_errors.length > 0 ? (
                        <div className="bg-slate-900 border border-edge/65 rounded-lg p-3 max-h-48 overflow-y-auto space-y-1.5 font-mono text-[11px] text-rose-300">
                          {selectedStep.network_errors.map((err, i) => (
                            <div key={i} className="border-b border-edge/20 pb-1.5 last:border-0 last:pb-0">{err}</div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-text-muted italic">No network errors logged.</p>
                      )}
                    </div>
                  </div>

                  {/* Accessibility Violations */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-text-muted uppercase tracking-wider">
                      Axe-Core accessibility Audits ({selectedStep.a11y_violations.length})
                    </h4>
                    {selectedStep.a11y_violations.length > 0 ? (
                      <div className="space-y-3">
                        {selectedStep.a11y_violations.map((violation, i) => (
                          <div key={i} className="bg-slate-800/40 p-4 border border-edge/60 rounded-xl space-y-2 text-xs">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-white text-sm">{violation.id}</span>
                              <span className={`px-2 py-0.5 rounded font-semibold text-[10px] capitalize ${
                                violation.impact === 'critical' || violation.impact === 'serious' 
                                  ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' 
                                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              }`}>
                                {violation.impact}
                              </span>
                            </div>
                            <p className="text-slate-400">{violation.description}</p>
                            {violation.help_url && (
                              <a 
                                href={violation.help_url} 
                                target="_blank" 
                                rel="noreferrer" 
                                className="text-primary hover:underline inline-block mt-1"
                              >
                                Axe Help Reference Docs →
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-text-muted italic">Zero accessibility violations detected.</p>
                    )}
                  </div>
                </div>
              </CardContent>
            ) : (
              <div className="flex items-center justify-center h-full p-12 text-text-muted italic text-xs">
                Select a timeline step to review audit logs.
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
