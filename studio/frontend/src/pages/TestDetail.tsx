import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTest, useUpdateTest, useTriggerRun } from '../hooks/useApi';
import { Button, Card, CardContent, PageHeader, ErrorState, toast } from '../components/ui';
import { Play, Download, Save, Trash2, ArrowUp, ArrowDown, ArrowLeft, Plus, X } from 'lucide-react';
import { StepData } from '../lib/api';

interface TestDetailProps {
  testId: number;
}

export default function TestDetail({ testId }: TestDetailProps) {
  const navigate = useNavigate();
  const { data: test, isLoading, error, refetch } = useTest(testId);
  const updateTestMutation = useUpdateTest(testId);
  const triggerRunMutation = useTriggerRun();

  const [steps, setSteps] = useState<StepData[]>([]);

  useEffect(() => {
    if (test?.steps) {
      setSteps(test.steps);
    }
  }, [test]);

  const handleSave = async () => {
    try {
      const res = await updateTestMutation.mutateAsync({ steps });
      toast.success(res.message || 'Steps saved successfully.');
    } catch (err: any) {
      toast.error(err.message || 'Failed to save steps.');
    }
  };

  const handleRun = async () => {
    try {
      const res = await triggerRunMutation.mutateAsync(testId);
      toast.success('Sandbox run triggered.');
      navigate(`/runs/${res.run_id}`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to trigger run.');
    }
  };

  const handleExport = () => {
    const a = document.createElement('a');
    a.href = `/tests/${testId}/export`;
    a.download = `test_${testId}.py`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const moveStep = (index: number, direction: 'up' | 'down') => {
    const newSteps = [...steps];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newSteps.length) return;
    
    // Swap
    const temp = newSteps[index];
    newSteps[index] = newSteps[targetIndex];
    newSteps[targetIndex] = temp;
    
    // Re-index orders
    newSteps.forEach((s, i) => s.order = i);
    setSteps(newSteps);
  };

  const deleteStep = (index: number) => {
    const newSteps = steps.filter((_, i) => i !== index);
    newSteps.forEach((s, i) => s.order = i);
    setSteps(newSteps);
  };

  const handleStepChange = (index: number, field: string, value: any) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    setSteps(newSteps);
  };

  const handleSelectorChange = (stepIndex: number, selectorIndex: number, value: string) => {
    const newSteps = [...steps];
    const newSelectors = [...newSteps[stepIndex].selectors];
    newSelectors[selectorIndex] = { ...newSelectors[selectorIndex], value };
    newSteps[stepIndex] = { ...newSteps[stepIndex], selectors: newSelectors };
    setSteps(newSteps);
  };

  const addAssertion = (stepIndex: number) => {
    const newSteps = [...steps];
    const newAssertions = [...(newSteps[stepIndex].assertions || [])];
    newAssertions.push({ kind: 'visible', value: '' });
    newSteps[stepIndex] = { ...newSteps[stepIndex], assertions: newAssertions };
    setSteps(newSteps);
  };

  const removeAssertion = (stepIndex: number, assertionIndex: number) => {
    const newSteps = [...steps];
    const newAssertions = newSteps[stepIndex].assertions.filter((_, i) => i !== assertionIndex);
    newSteps[stepIndex] = { ...newSteps[stepIndex], assertions: newAssertions };
    setSteps(newSteps);
  };

  const handleAssertionChange = (stepIndex: number, assertionIndex: number, field: 'kind' | 'value', value: string) => {
    const newSteps = [...steps];
    const newAssertions = [...newSteps[stepIndex].assertions];
    newAssertions[assertionIndex] = { ...newAssertions[assertionIndex], [field]: value };
    newSteps[stepIndex] = { ...newSteps[stepIndex], assertions: newAssertions };
    setSteps(newSteps);
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 w-full max-w-5xl mx-auto">
        <div className="h-10 w-48 bg-slate-800/50 rounded-lg animate-pulse"></div>
        <div className="space-y-4">
          {[1, 2].map(i => (
            <div key={i} className="h-40 bg-slate-800/40 rounded-xl animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !test) {
    return (
      <div className="p-8 w-full max-w-2xl mx-auto">
        <ErrorState
          message="Failed to load test steps."
          details={error instanceof Error ? error.stack : String(error)}
          onRetry={refetch}
        />
        <Button onClick={() => navigate('/tests')} variant="secondary" className="mt-4">
          Back to Suite
        </Button>
      </div>
    );
  }

  const isSaving = updateTestMutation.isPending;
  const isRunning = triggerRunMutation.isPending;

  return (
    <div className="p-8 space-y-8 w-full max-w-7xl mx-auto font-sans">
      <div className="flex flex-col md:flex-row justify-between items-start gap-4">
        <div className="space-y-1">
          <Button
            variant="ghost"
            onClick={() => navigate('/tests')}
            className="text-slate-400 hover:text-white mb-2"
            size="sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Suite</span>
          </Button>
          <h1 className="text-2xl font-bold text-white display-font">{test.name}</h1>
          <p className="text-text-muted text-xs font-mono">{test.url}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSave}
            loading={isSaving}
            className="gap-1.5"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Steps</span>
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleExport}
            className="gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Pytest Code</span>
          </Button>

          <Button
            size="sm"
            onClick={handleRun}
            loading={isRunning}
            className="gap-1.5"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Run Sandbox</span>
          </Button>
        </div>
      </div>

      {steps.length === 0 ? (
        <Card className="max-w-2xl mx-auto">
          <CardContent className="p-12 text-center text-text-muted italic text-sm">
            This test contains no steps. Launch the recorder from the Test Suite to populate it.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {steps.map((step, idx) => (
            <div key={idx} className="bg-surface border border-edge/60 rounded-xl p-6 relative flex flex-col md:flex-row gap-6">
              
              {/* Step info + core params */}
              <div className="flex-1 space-y-4">
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-bold font-mono text-slate-500 bg-slate-800 border border-edge/50 px-2 py-0.5 rounded-sm">
                    STEP {idx + 1}
                  </span>
                  <span className={`px-2 py-0.5 text-[10px] font-bold rounded-sm capitalize tracking-wide ${
                    step.action === 'navigate' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' :
                    step.action === 'click' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                    'bg-pink-500/10 text-pink-400 border border-pink-500/20'
                  }`}>
                    {step.action}
                  </span>
                </div>

                {/* Value input (navigate or fill) */}
                {(step.action === 'navigate' || step.action === 'fill') && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-400">Value</label>
                    <input
                      type="text"
                      value={step.value || ''}
                      onChange={(e) => handleStepChange(idx, 'value', e.target.value)}
                      className="w-full bg-slate-800 border border-edge/60 text-white text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-blue-600 focus:outline-hidden transition"
                    />
                  </div>
                )}

                {/* Selector ladder (editable) */}
                {step.selectors && step.selectors.length > 0 && (
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-400 block">Selector Ladder</label>
                    <div className="space-y-1.5">
                      {step.selectors.map((sel, sIdx) => (
                        <div key={sIdx} className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-text-muted bg-slate-800 border border-edge/40 px-1.5 py-0.5 rounded-sm capitalize">
                            {sel.kind}
                          </span>
                          <input
                            type="text"
                            value={sel.value}
                            onChange={(e) => handleSelectorChange(idx, sIdx, e.target.value)}
                            className="flex-1 bg-slate-800 border border-edge/60 text-white font-mono text-xs rounded-lg px-3 py-1.5 focus:ring-1 focus:ring-blue-600 focus:outline-hidden transition"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Assertions Editor */}
                <div className="space-y-2 pt-2">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-semibold text-slate-400">Assertions</label>
                    <button
                      onClick={() => addAssertion(idx)}
                      className="flex items-center gap-1 text-xs text-primary hover:text-primary/95 font-medium transition cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add Assertion</span>
                    </button>
                  </div>
                  
                  {step.assertions && step.assertions.length > 0 ? (
                    <div className="space-y-2">
                      {step.assertions.map((ass, aIdx) => (
                        <div key={aIdx} className="flex items-center gap-2 bg-slate-800/40 p-2 border border-edge/40 rounded-lg">
                          <select
                            value={ass.kind}
                            onChange={(e) => handleAssertionChange(idx, aIdx, 'kind', e.target.value)}
                            className="bg-slate-800 border border-edge/60 text-white text-xs rounded px-2 py-1 focus:outline-hidden"
                          >
                            <option value="visible">Visible</option>
                            <option value="url">URL</option>
                          </select>
                          <input
                            type="text"
                            value={ass.value}
                            placeholder={ass.kind === 'visible' ? 'Selector target' : 'Expected URL'}
                            onChange={(e) => handleAssertionChange(idx, aIdx, 'value', e.target.value)}
                            className="flex-1 bg-slate-850 border border-edge/60 text-white text-xs rounded px-2 py-1 focus:outline-hidden"
                          />
                          <button
                            onClick={() => removeAssertion(idx, aIdx)}
                            className="p-1 text-slate-500 hover:text-fail transition cursor-pointer"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-text-muted italic">No assertions set for this step.</p>
                  )}
                </div>
              </div>

              {/* Crop Screenshot Thumb */}
              {step.fingerprint && step.fingerprint.tag && (
                <div className="md:w-48 flex flex-col justify-between items-end border-l border-edge/40 md:pl-6 pt-4 md:pt-0">
                  <div className="w-full space-y-3">
                    <div className="text-right text-xs text-slate-500 space-y-1">
                      <p className="font-semibold text-slate-400 font-mono">&lt;{step.fingerprint.tag}&gt;</p>
                      {step.fingerprint.text && <p className="italic truncate font-mono text-[11px]">"{step.fingerprint.text}"</p>}
                    </div>
                    
                    <div className="border border-edge/60 rounded-lg overflow-hidden bg-slate-900/60 p-1 flex items-center justify-center h-20 w-full">
                      <img
                        src={step.fingerprint.screenshot_path || `/projects/test_${testId}/screenshots/crop_${step.order - 1}.png`}
                        alt="Element crop"
                        className="max-h-full max-w-full object-contain"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                          const parent = (e.target as HTMLElement).parentElement;
                          if (parent) parent.style.display = 'none';
                        }}
                      />
                    </div>
                  </div>
                  
                  <div className="flex gap-2 mt-4 md:mt-0">
                    <button
                      onClick={() => moveStep(idx, 'up')}
                      disabled={idx === 0}
                      className="p-1.5 bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white border border-edge/60 rounded-lg disabled:opacity-30 cursor-pointer"
                    >
                      <ArrowUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => moveStep(idx, 'down')}
                      disabled={idx === steps.length - 1}
                      className="p-1.5 bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white border border-edge/60 rounded-lg disabled:opacity-30 cursor-pointer"
                    >
                      <ArrowDown className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => deleteStep(idx)}
                      className="p-1.5 bg-slate-800 hover:bg-fail/10 border border-edge/60 hover:border-fail/20 text-slate-400 hover:text-fail rounded-lg cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
