import React, { useEffect, useState } from 'react';
import { api, TestData, StepData } from '../lib/api';
import { Play, Download, Save, Trash2, ArrowUp, ArrowDown, ArrowLeft, Plus, X } from 'lucide-react';

interface TestDetailProps {
  testId: number;
  onNavigate: (route: string) => void;
}

export default function TestDetail({ testId, onNavigate }: TestDetailProps) {
  const [test, setTest] = useState<TestData | null>(null);
  const [steps, setSteps] = useState<StepData[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    async function loadTest() {
      try {
        setLoading(true);
        const data = await api.getTest(testId);
        setTest(data);
        setSteps(data.steps || []);
      } catch (err: any) {
        setError(err.message || 'Failed to load test details.');
      } finally {
        setLoading(false);
      }
    }
    loadTest();
  }, [testId]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const res = await api.updateTest(testId, { steps });
      setBanner(res.message);
      setTimeout(() => setBanner(null), 3000);
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    try {
      const res = await api.triggerRun(testId);
      onNavigate(`/runs/${res.run_id}`);
    } catch (err: any) {
      alert(`Run trigger failed: ${err.message}`);
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

  if (loading) {
    return (
      <div className="p-8 space-y-6 w-full animate-pulse">
        <div className="h-10 w-48 bg-slate-700/50 rounded-lg"></div>
        <div className="space-y-4">
          {[1, 2].map(i => (
            <div key={i} className="h-40 bg-slate-800/40 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold text-rose-400">Failed to load test steps</h2>
        <p className="text-slate-400">{error}</p>
        <button onClick={() => onNavigate('/tests')} className="px-4 py-2 bg-slate-800 rounded-lg">Back</button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full max-w-5xl">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <button
            onClick={() => onNavigate('/tests')}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Suite</span>
          </button>
          <h1 className="text-3xl font-bold text-white display-font">{test?.name}</h1>
          <p className="text-slate-400 text-sm">{test?.url}</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg text-sm font-semibold border border-slate-750 transition"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Steps'}</span>
          </button>

          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg text-sm font-semibold border border-slate-750 transition"
          >
            <Download className="w-4 h-4" />
            <span>Pytest Code</span>
          </button>

          <button
            onClick={handleRun}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-lg shadow-lg hover:shadow-blue-500/10 transition"
          >
            <Play className="w-4 h-4 fill-white" />
            <span>Run Sandbox</span>
          </button>
        </div>
      </div>

      {banner && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-lg text-sm font-medium">
          {banner}
        </div>
      )}

      {steps.length === 0 ? (
        <div className="p-12 text-center bg-slate-850 border border-slate-750 rounded-xl">
          <p className="text-slate-400">This test contains no steps. Record steps to populate the flow.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {steps.map((step, idx) => (
            <div key={idx} className="bg-slate-850 border border-slate-750 rounded-xl p-6 relative flex flex-col md:flex-row gap-6">
              
              {/* Step info + core params */}
              <div className="flex-1 space-y-4">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-bold font-mono text-slate-500 bg-slate-800 border border-slate-750 px-2 py-0.5 rounded">
                    STEP {idx + 1}
                  </span>
                  <span className={`px-2 py-0.5 text-xs font-semibold rounded capitalize ${
                    step.action === 'navigate' ? 'bg-indigo-500/10 text-indigo-400' :
                    step.action === 'click' ? 'bg-blue-500/10 text-blue-400' :
                    'bg-pink-500/10 text-pink-400'
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
                      className="w-full bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-1.5 focus:ring-1 focus:ring-blue-600 focus:outline-none transition"
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
                          <span className="text-xs font-mono text-slate-600 bg-slate-800 border border-slate-750 px-1.5 py-0.5 rounded capitalize">
                            {sel.kind}
                          </span>
                          <input
                            type="text"
                            value={sel.value}
                            onChange={(e) => handleSelectorChange(idx, sIdx, e.target.value)}
                            className="flex-1 bg-slate-800 border border-slate-700 text-white font-mono text-xs rounded px-3 py-1 focus:ring-1 focus:ring-blue-600 focus:outline-none transition"
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
                      className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 font-medium transition"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add Assertion</span>
                    </button>
                  </div>
                  
                  {step.assertions && step.assertions.length > 0 ? (
                    <div className="space-y-2">
                      {step.assertions.map((ass, aIdx) => (
                        <div key={aIdx} className="flex items-center gap-2 bg-slate-800/40 p-2 border border-slate-750/50 rounded-lg">
                          <select
                            value={ass.kind}
                            onChange={(e) => handleAssertionChange(idx, aIdx, 'kind', e.target.value)}
                            className="bg-slate-800 border border-slate-700 text-white text-xs rounded px-2 py-1"
                          >
                            <option value="visible">Visible</option>
                            <option value="url">URL</option>
                          </select>
                          <input
                            type="text"
                            value={ass.value}
                            placeholder={ass.kind === 'visible' ? 'Selector target' : 'Expected URL'}
                            onChange={(e) => handleAssertionChange(idx, aIdx, 'value', e.target.value)}
                            className="flex-1 bg-slate-850 border border-slate-700 text-white text-xs rounded px-2 py-1"
                          />
                          <button
                            onClick={() => removeAssertion(idx, aIdx)}
                            className="p-1 text-slate-500 hover:text-red-400 transition"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-650 italic">No assertions set for this step.</p>
                  )}
                </div>
              </div>

              {/* Crop Screenshot Thumb */}
              {step.fingerprint && step.fingerprint.tag && (
                <div className="md:w-48 flex flex-col justify-between items-end border-l border-slate-750 md:pl-6 pt-4 md:pt-0">
                  <div className="w-full text-right text-xs text-slate-500 space-y-1">
                    <p className="font-semibold text-slate-400">&lt;{step.fingerprint.tag}&gt;</p>
                    {step.fingerprint.text && <p className="italic truncate font-mono">"{step.fingerprint.text}"</p>}
                  </div>
                  
                  <div className="flex gap-2 mt-4 md:mt-0">
                    <button
                      onClick={() => moveStep(idx, 'up')}
                      disabled={idx === 0}
                      className="p-1.5 bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white border border-slate-750 rounded disabled:opacity-30 disabled:hover:bg-slate-800"
                    >
                      <ArrowUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => moveStep(idx, 'down')}
                      disabled={idx === steps.length - 1}
                      className="p-1.5 bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white border border-slate-750 rounded disabled:opacity-30 disabled:hover:bg-slate-800"
                    >
                      <ArrowDown className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => deleteStep(idx)}
                      className="p-1.5 bg-slate-800 hover:bg-rose-500/10 border border-slate-750 hover:border-rose-500/20 text-slate-400 hover:text-rose-400 rounded"
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
