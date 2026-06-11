import React, { useEffect, useState, useRef } from 'react';
import { api, RunDetailData, StepResultData, API_BASE } from '../lib/api';
import { ArrowLeft, Clock, Zap, AlertTriangle, ShieldAlert, CheckCircle2, RefreshCw, Layers } from 'lucide-react';

interface RunDetailProps {
  runId: number;
  onNavigate: (route: string) => void;
}

export default function RunDetail({ runId, onNavigate }: RunDetailProps) {
  const [run, setRun] = useState<RunDetailData | null>(null);
  const [selectedStepIdx, setSelectedStepIdx] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const loadRun = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      const data = await api.getRun(runId);
      setRun(data);
      if (selectedStepIdx === null && data.step_results.length > 0) {
        // Deep-link to first failing step, or default to step 0
        const firstFail = data.step_results.findIndex(r => r.status === 'failed' || r.status === 'error');
        setSelectedStepIdx(firstFail !== -1 ? firstFail : 0);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load run details.');
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    loadRun();

    const loc = window.location;
    const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_BASE ? API_BASE.replace(/^http(s)?:\/\//, '').replace(/\/$/, '') : loc.host;
    const wsUrl = `${wsProto}//${wsHost}/runs/${runId}/live`;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'run_status') {
        setRun(prev => prev ? { ...prev, status: msg.status } : null);
        if (msg.status !== 'running' && msg.status !== 'queued') {
          // Final reload to ensure all details are fetched
          loadRun(false);
        }
      } else if (msg.type === 'step_result') {
        setRun(prev => {
          if (!prev) return null;
          const newResults = [...prev.step_results];
          newResults[msg.step_index] = msg.result;
          return { ...prev, step_results: newResults };
        });
      }
    };

    socket.onclose = () => {
      // Socket closed
    };

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [runId]);

  if (loading) {
    return (
      <div className="p-8 space-y-6 w-full animate-pulse">
        <div className="h-10 w-48 bg-slate-700/50 rounded-lg"></div>
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-1 h-96 bg-slate-800/40 rounded-xl"></div>
          <div className="col-span-2 h-96 bg-slate-850/40 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold text-rose-400">Failed to load run</h2>
        <p className="text-slate-400">{error}</p>
        <button onClick={() => onNavigate('/tests')} className="px-4 py-2 bg-slate-800 rounded-lg">Back</button>
      </div>
    );
  }

  const selectedStep: StepResultData | undefined = selectedStepIdx !== null ? run?.step_results[selectedStepIdx] : undefined;

  return (
    <div className="p-8 space-y-6 w-full max-w-6xl">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <button
            onClick={() => onNavigate(`/tests/${run?.test_id}`)}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Step Manager</span>
          </button>
          <h1 className="text-3xl font-bold text-white display-font">Run Execution: {run?.test_name}</h1>
          <p className="text-xs text-slate-500">Run ID: {run?.id} · Started at {run && new Date(run.started_at).toLocaleString()}</p>
        </div>

        <div className="flex items-center gap-6 bg-slate-850 p-4 border border-slate-750 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 text-xs">
            <Clock className="w-4 h-4" />
            <span>Duration: {run?.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs">
            <Zap className="w-4 h-4 text-amber-400" />
            <span>Spend: ${run?.ai_cost_usd.toFixed(4)}</span>
          </div>
          <span className={`px-3 py-1 text-xs font-semibold rounded-full capitalize ${
            run?.status === 'passed' ? 'bg-emerald-500/10 text-emerald-400' :
            run?.status === 'failed' ? 'bg-rose-500/10 text-rose-400' :
            run?.status === 'running' || run?.status === 'queued' ? 'bg-blue-500/10 text-blue-400 animate-pulse' :
            'bg-slate-500/10 text-slate-400'
          }`}>
            {run?.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Column: Timeline */}
        <div className="md:col-span-1 bg-slate-850 border border-slate-750 rounded-xl p-6 h-fit space-y-4">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Timeline Steps</h2>
          
          <div className="space-y-2">
            {run?.step_results.map((res, i) => (
              <div
                key={i}
                onClick={() => setSelectedStepIdx(i)}
                className={`w-full p-4 rounded-xl border flex items-center justify-between cursor-pointer transition ${
                  selectedStepIdx === i 
                    ? 'bg-blue-500/10 border-blue-500 text-white' 
                    : 'bg-slate-800/40 border-slate-700/50 text-slate-300 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center gap-3 truncate">
                  {res.status === 'passed' ? <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" /> :
                   res.status === 'failed' || res.status === 'error' ? <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" /> :
                   <RefreshCw className="w-5 h-5 text-blue-400 animate-spin shrink-0" />}
                  <span className="font-semibold text-sm truncate">{res.step_name}</span>
                </div>
                <span className="text-xs text-slate-500 shrink-0">{res.duration_ms}ms</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Evidence Panel */}
        <div className="md:col-span-2 bg-slate-850 border border-slate-750 rounded-xl p-6 space-y-6">
          {selectedStep ? (
            <div className="space-y-6">
              
              {/* Evidence details */}
              <div className="flex justify-between items-center border-b border-slate-750 pb-4">
                <div>
                  <h3 className="text-lg font-bold text-white display-font">{selectedStep.step_name}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Execution Step Duration: {selectedStep.duration_ms} ms</p>
                </div>
                <span className={`px-2.5 py-0.5 text-xs font-semibold rounded capitalize ${
                  selectedStep.status === 'passed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                }`}>
                  {selectedStep.status}
                </span>
              </div>

              {selectedStep.error_message && (
                <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm rounded-lg flex items-start gap-2">
                  <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
                  <div className="font-mono text-xs">{selectedStep.error_message}</div>
                </div>
              )}

              {/* Tab options for evidence */}
              <div className="space-y-4">
                {/* 1. Page Screenshot and Visual Diffs */}
                {selectedStep.screenshot_path && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-blue-400" />
                      <span>Visual Evidence & Checks</span>
                    </h4>
                    
                    {selectedStep.visual_diff_score !== null && (
                      <div className="p-3 bg-slate-800/60 border border-slate-750 rounded-lg flex justify-between items-center text-xs">
                        <span className="text-slate-400">Visual Deviation Score:</span>
                        <span className={`font-semibold font-mono ${
                          selectedStep.visual_diff_score > 0.05 ? 'text-amber-400' : 'text-slate-300'
                        }`}>
                          {(selectedStep.visual_diff_score * 100).toFixed(1)}% difference
                        </span>
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="border border-slate-750 rounded-xl overflow-hidden bg-slate-900 flex flex-col">
                        <div className="px-4 py-2 border-b border-slate-750 bg-slate-800 text-xs font-medium text-slate-400">
                          Execution Screenshot
                        </div>
                        <img 
                          src={`${API_BASE}${selectedStep.screenshot_path}`} 
                          alt="Execution Screenshot" 
                          className="w-full max-h-96 object-contain p-2"
                        />
                      </div>
                      
                      {selectedStep.visual_diff_score !== null && selectedStep.visual_diff_score > 0.05 && (
                        <div className="border border-slate-750 rounded-xl overflow-hidden bg-slate-900 flex flex-col">
                          <div className="px-4 py-2 border-b border-slate-750 bg-slate-800 text-xs font-medium text-amber-400">
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

                {/* 2. Console and Network Errors */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Console Logs ({selectedStep.console_errors.length})</h4>
                    {selectedStep.console_errors.length > 0 ? (
                      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 max-h-48 overflow-y-auto space-y-1.5 font-mono text-xs text-rose-300">
                        {selectedStep.console_errors.map((err, i) => (
                          <div key={i} className="border-b border-slate-800/60 pb-1.5 last:border-0 last:pb-0">{err}</div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-600 italic">No console errors logged.</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Network Failures ({selectedStep.network_errors.length})</h4>
                    {selectedStep.network_errors.length > 0 ? (
                      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 max-h-48 overflow-y-auto space-y-1.5 font-mono text-xs text-rose-300">
                        {selectedStep.network_errors.map((err, i) => (
                          <div key={i} className="border-b border-slate-800/60 pb-1.5 last:border-0 last:pb-0">{err}</div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-650 italic">No network errors logged.</p>
                    )}
                  </div>
                </div>

                {/* 3. Accessibility Violations */}
                <div className="space-y-2 pt-4">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Axe-Core accessibility Audits ({selectedStep.a11y_violations.length})</h4>
                  {selectedStep.a11y_violations.length > 0 ? (
                    <div className="space-y-3">
                      {selectedStep.a11y_violations.map((violation, i) => (
                        <div key={i} className="bg-slate-800/40 p-4 border border-slate-750 rounded-xl space-y-2 text-xs">
                          <div className="flex justify-between items-center">
                            <span className="font-bold text-white text-sm">{violation.id}</span>
                            <span className={`px-2 py-0.5 rounded font-semibold text-[10px] capitalize ${
                              violation.impact === 'critical' || violation.impact === 'serious' 
                                ? 'bg-rose-500/10 text-rose-400' 
                                : 'bg-amber-500/10 text-amber-400'
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
                              className="text-blue-400 hover:underline inline-block mt-1"
                            >
                              Axe Help Reference Docs →
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-650 italic">Zero accessibility violations detected.</p>
                  )}
                </div>
              </div>

            </div>
          ) : (
            <div className="text-center p-12 text-slate-500 italic">Select a timeline step to review audit logs.</div>
          )}
        </div>

      </div>
    </div>
  );
}
