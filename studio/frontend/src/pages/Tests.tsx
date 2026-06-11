import React, { useEffect, useState } from 'react';
import { api, TestData } from '../lib/api';
import { Play, Trash2, Eye, Plus, ArrowRight, ShieldAlert, CheckCircle, RefreshCw } from 'lucide-react';

interface TestsProps {
  onNavigate: (route: string) => void;
}

export default function Tests({ onNavigate }: TestsProps) {
  const [tests, setTests] = useState<TestData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTests = async () => {
    try {
      setLoading(true);
      const data = await api.listTests();
      setTests(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load test suite.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTests();
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this test? All step and execution records will be lost.')) {
      return;
    }
    try {
      await api.deleteTest(id);
      setTests(tests.filter(t => t.id !== id));
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleRun = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const res = await api.triggerRun(id);
      onNavigate(`/runs/${res.run_id}`);
    } catch (err: any) {
      alert(`Execution run failed: ${err.message}`);
    }
  };

  if (loading && tests.length === 0) {
    return (
      <div className="p-8 space-y-6 w-full animate-pulse">
        <div className="flex justify-between items-center">
          <div className="h-10 w-48 bg-slate-700/50 rounded-lg"></div>
          <div className="h-10 w-32 bg-slate-700/50 rounded-lg"></div>
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-20 bg-slate-800/40 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white display-font">Test Suite</h1>
          <p className="text-slate-400 mt-1">Manage, record and trigger local automated scraper flows</p>
        </div>
        <button
          onClick={() => onNavigate('/tests/new')}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-blue-500/10 transition duration-150"
        >
          <Plus className="w-5 h-5" />
          <span>New Test</span>
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-lg">
          {error}
        </div>
      )}

      {tests.length === 0 ? (
        <div className="border border-slate-750 bg-slate-850 rounded-xl p-16 text-center max-w-2xl mx-auto space-y-6">
          <div className="w-16 h-16 bg-slate-800 border border-slate-700/50 rounded-full flex items-center justify-center mx-auto text-slate-500">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-bold text-white display-font">No Tests Recorded</h3>
            <p className="text-slate-400 max-w-md mx-auto text-sm">
              ScrapeWizard is a record-first automation framework. Record browser actions to generate standalone Python scrapers and verification suites.
            </p>
          </div>
          <button
            onClick={() => onNavigate('/tests/new')}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition"
          >
            Record Your First Test
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {tests.map(test => (
            <div
              key={test.id}
              onClick={() => onNavigate(`/tests/${test.id}`)}
              className="px-6 py-5 bg-slate-850 border border-slate-750 hover:border-slate-700 rounded-xl flex items-center justify-between cursor-pointer transition"
            >
              <div className="space-y-1.5 max-w-xl">
                <h3 className="font-bold text-white text-base display-font">{test.name}</h3>
                <p className="text-xs text-slate-500 truncate">{test.url}</p>
                <div className="flex items-center gap-3 pt-1 text-xs">
                  <span className="px-2 py-0.5 bg-slate-800 text-slate-400 border border-slate-750 rounded-md font-medium">
                    {test.step_count} Steps
                  </span>
                  
                  {test.last_run ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-600">•</span>
                      <span className="text-slate-500">Last run:</span>
                      <span className={`flex items-center gap-1 font-semibold capitalize ${
                        test.last_run.status === 'passed' ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {test.last_run.status === 'passed' ? <CheckCircle className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
                        {test.last_run.status}
                      </span>
                    </div>
                  ) : (
                    <span className="text-slate-600">No runs executed</span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3">
                <button
                  onClick={(e) => { e.stopPropagation(); onNavigate(`/tests/${test.id}`); }}
                  title="View details"
                  className="p-2 bg-slate-800 hover:bg-slate-750 border border-slate-750 text-slate-300 rounded-lg hover:text-white transition"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => handleRun(e, test.id)}
                  disabled={!test.step_count}
                  title="Execute Run"
                  className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg disabled:opacity-50 disabled:hover:bg-blue-600 transition"
                >
                  <Play className="w-4 h-4 fill-white" />
                </button>
                <button
                  onClick={(e) => handleDelete(e, test.id)}
                  title="Delete test"
                  className="p-2 bg-slate-800 hover:bg-rose-500/10 border border-slate-750 hover:border-rose-500/20 text-slate-400 hover:text-rose-400 rounded-lg transition"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
