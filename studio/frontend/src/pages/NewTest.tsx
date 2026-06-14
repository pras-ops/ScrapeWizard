import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateTest, useRecordTest, useRecordStatus } from '../hooks/useApi';
import { Button, Card, CardContent, PageHeader, ErrorState } from '../components/ui';
import { Play, Chrome, AlertTriangle, ArrowLeft } from 'lucide-react';

export default function NewTest() {
  const navigate = useNavigate();
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [recording, setRecording] = useState(false);
  const [createdTestId, setCreatedTestId] = useState<number | null>(null);

  const createTestMutation = useCreateTest();
  const recordTestMutation = useRecordTest();

  // Poll status using React Query hook, active when recording is true
  const { data: recordStatus } = useRecordStatus(createdTestId ?? 0, recording);

  // Monitor recording status from API
  useEffect(() => {
    if (recording && recordStatus && !recordStatus.recording) {
      setRecording(false);
      navigate(`/tests/${createdTestId}`);
    }
  }, [recordStatus, recording, createdTestId, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      return;
    }

    try {
      // 1. Create the test
      const test = await createTestMutation.mutateAsync({ url, name });
      setCreatedTestId(test.id);

      // 2. Trigger the recording session
      await recordTestMutation.mutateAsync(test.id);
      setRecording(true);
    } catch (err) {
      // Handled by mutation errors
    }
  };

  const isPending = createTestMutation.isPending || recordTestMutation.isPending;
  const error = createTestMutation.error || recordTestMutation.error;

  if (recording) {
    const stepCount = recordStatus?.step_count ?? 0;

    return (
      <div className="p-8 max-w-2xl mx-auto space-y-8 py-16 text-center">
        <div className="w-20 h-20 bg-blue-500/10 border-2 border-blue-500 rounded-full flex items-center justify-center mx-auto text-blue-400 animate-pulse">
          <Chrome className="w-10 h-10 animate-spin" style={{ animationDuration: '3s' }} />
        </div>
        
        <div className="space-y-3">
          <h2 className="text-2xl font-bold text-white display-font">Browser Recording Active</h2>
          <p className="text-slate-400 text-sm max-w-md mx-auto">
            A headed browser has been opened. Perform actions (click elements, enter text, navigate) in the target window.
          </p>
        </div>

        <Card className="max-w-md mx-auto">
          <CardContent className="flex items-center justify-around divide-x divide-edge/40 p-6">
            <div className="text-center px-4 w-1/2">
              <span className="text-3xl font-extrabold text-blue-400 font-mono">{stepCount}</span>
              <p className="text-[10px] text-text-muted mt-1 uppercase tracking-wider font-semibold">Steps Captured</p>
            </div>
            <div className="text-center px-4 w-1/2 flex flex-col items-center justify-center">
              <span className="flex h-3 w-3 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <p className="text-[10px] text-text-muted mt-2 uppercase tracking-wider font-semibold">Listening...</p>
            </div>
          </CardContent>
        </Card>

        <div className="p-4 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs rounded-lg flex gap-2.5 items-start text-left max-w-md mx-auto">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block mb-0.5">How to Save:</span>
            Simply close the browser window when you are done. ScrapeWizard will automatically finalize the flow definition and generate the step configurations.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full max-w-2xl mx-auto">
      <Button
        variant="ghost"
        onClick={() => navigate('/tests')}
        className="gap-2 text-slate-400 hover:text-white"
        size="sm"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Suite</span>
      </Button>

      <PageHeader
        title="Record Test Flow"
        description="Start recording browser interactions to build an automated, self-healing test definition"
      />

      {error && (
        <ErrorState
          message="Failed to initialize recording session."
          details={error instanceof Error ? error.message : String(error)}
        />
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardContent className="space-y-6 p-8">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-300">Target Website URL</label>
              <input 
                type="url" 
                required
                value={url} 
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                disabled={isPending}
                className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition-all"
              />
              <p className="text-xs text-text-muted">Starting entry point for the headed record process</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-300">Test Name (Optional)</label>
              <input 
                type="text" 
                value={name} 
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Verify checkout process"
                disabled={isPending}
                className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition-all"
              />
            </div>

            <div className="pt-4 flex justify-end">
              <Button
                type="submit"
                loading={isPending}
                className="gap-2"
              >
                <Play className="w-4 h-4 fill-white" />
                <span>{isPending ? 'Starting...' : 'Launch Recorder'}</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
