import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Play, Chrome, Activity, AlertTriangle, ArrowLeft } from 'lucide-react';

interface NewTestProps {
  onNavigate: (route: string) => void;
}

export default function NewTest({ onNavigate }: NewTestProps) {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState({ recording: false, step_count: 0 });
  const [error, setError] = useState<string | null>(null);
  const [createdTestId, setCreatedTestId] = useState<number | null>(null);

  // Poll status while recording is active
  useEffect(() => {
    let interval: any;
    if (recording && createdTestId !== null) {
      interval = setInterval(async () => {
        try {
          const res = await api.getRecordStatus(createdTestId);
          setStatus(res);
          if (!res.recording) {
            setRecording(false);
            clearInterval(interval);
            onNavigate(`/tests/${createdTestId}`);
          }
        } catch (err) {
          // Ignore polling errors
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [recording, createdTestId, onNavigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setError('URL must start with http:// or https://');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // 1. Create the test
      const test = await api.createTest({ url, name });
      setCreatedTestId(test.id);

      // 2. Trigger the recording session
      await api.recordTest(test.id);
      setRecording(true);
      setStatus({ recording: true, step_count: 0 });
    } catch (err: any) {
      setError(err.message || 'Failed to initialize recording session.');
      setLoading(false);
    }
  };

  if (recording) {
    return (
      <div className="p-8 max-w-2xl mx-auto space-y-8 py-16 text-center">
        <div className="w-20 h-20 bg-blue-500/10 border-2 border-blue-500 rounded-full flex items-center justify-center mx-auto text-blue-400 animate-pulse">
          <Chrome className="w-10 h-10 animate-spin" style={{ animationDuration: '3s' }} />
        </div>
        
        <div className="space-y-3">
          <h2 className="text-2xl font-bold text-white display-font">Browser Recording Active</h2>
          <p className="text-slate-400 text-sm max-w-md mx-auto">
            A headed browser has been opened. Perform actions (click elements, enter text) in the target window.
          </p>
        </div>

        <div className="bg-slate-850 p-6 rounded-xl border border-slate-750 max-w-md mx-auto flex items-center justify-around divide-x divide-slate-750">
          <div className="text-center px-4">
            <span className="text-3xl font-extrabold text-blue-400 font-mono">{status.step_count}</span>
            <p className="text-xs text-slate-500 mt-1 uppercase tracking-wider font-semibold">Steps Captured</p>
          </div>
          <div className="text-center px-4 w-1/2 flex flex-col items-center justify-center">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <p className="text-xs text-slate-500 mt-2 uppercase tracking-wider font-semibold">Listening...</p>
          </div>
        </div>

        <div className="p-4 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs rounded-lg flex gap-2.5 items-start text-left max-w-md mx-auto">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block mb-0.5">How to Save:</span>
            Simply close the browser window. ScrapeWizard will automatically finalize the flow.json and generate the steps code.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full max-w-2xl">
      <button
        onClick={() => onNavigate('/tests')}
        className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Suite</span>
      </button>

      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white display-font">Record Scraper Flow</h1>
        <p className="text-slate-400 mt-1">Start recording browser interactions to build an automated scraper plugin</p>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-slate-850 p-8 rounded-xl border border-slate-750 space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-300">Target Website URL</label>
          <input 
            type="text" 
            required
            value={url} 
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            disabled={loading}
            className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-600 focus:outline-none transition"
          />
          <p className="text-xs text-slate-500">Starting entry point for the headed record process</p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-300">Test Name (Optional)</label>
          <input 
            type="text" 
            value={name} 
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Scrape products list"
            disabled={loading}
            className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-600 focus:outline-none transition"
          />
        </div>

        <div className="pt-4 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-blue-500/10 transition duration-150 disabled:opacity-50"
          >
            <Play className="w-5 h-5 fill-white" />
            <span>{loading ? 'Starting...' : 'Launch Recorder'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
