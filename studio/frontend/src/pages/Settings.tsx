import React, { useState, useEffect } from 'react';
import { useSettings, useUpdateSettings, useTestConnection } from '../hooks/useApi';
import { Button, Card, CardContent, PageHeader, ErrorState, toast } from '../components/ui';
import { Check, AlertCircle, Save, RefreshCw } from 'lucide-react';

export default function Settings() {
  const { data: serverSettings, isLoading, error: loadError, refetch } = useSettings();
  const updateSettingsMutation = useUpdateSettings();
  const testConnectionMutation = useTestConnection();

  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4-turbo');
  const [aiMode, setAiMode] = useState('Creation');
  const [visualThreshold, setVisualThreshold] = useState(0.05);
  const [retention, setRetention] = useState(10);
  const [apiKey, setApiKey] = useState('');
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Synchronize state when data loads
  useEffect(() => {
    if (serverSettings) {
      setProvider(serverSettings.provider);
      setModel(serverSettings.model);
      setAiMode(serverSettings.ai_mode);
      setVisualThreshold(serverSettings.visual_threshold);
      setRetention(serverSettings.retention);
    }
  }, [serverSettings]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = {
        provider,
        model,
        ai_mode: aiMode,
        visual_threshold: visualThreshold,
        retention,
      };
      if (apiKey) {
        payload.api_key = apiKey;
      }
      const res = await updateSettingsMutation.mutateAsync(payload);
      setApiKey(''); // Clear key field
      toast.success(res.message || 'Settings saved successfully.');
    } catch (err: any) {
      toast.error(err.message || 'Failed to save settings.');
    }
  };

  const handleTestConnection = async () => {
    const hasKey = serverSettings?.has_key;
    if (!apiKey && !hasKey && provider !== 'local') {
      setTestResult({ ok: false, message: 'Please enter an API Key to test.' });
      return;
    }

    try {
      setTestResult(null);
      // Connection test uses input key, or fallback placeholder if already set
      const res = await testConnectionMutation.mutateAsync({
        provider,
        model,
        api_key: apiKey || '•••• set'
      });
      setTestResult(res);
      if (res.ok) {
        toast.success('LLM connectivity probe succeeded.');
      } else {
        toast.error('LLM connectivity probe failed.');
      }
    } catch (err: any) {
      setTestResult({ ok: false, message: err.message || 'Test failed.' });
      toast.error(err.message || 'Connection test failed.');
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 w-full max-w-4xl mx-auto">
        <div className="h-10 w-48 bg-slate-800/50 rounded-lg animate-pulse"></div>
        <div className="h-96 bg-slate-850 rounded-xl border border-edge/30 animate-pulse"></div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-8 w-full max-w-2xl mx-auto">
        <ErrorState
          message="Failed to load configuration settings."
          details={loadError instanceof Error ? loadError.stack : String(loadError)}
          onRetry={refetch}
        />
      </div>
    );
  }

  const isSaving = updateSettingsMutation.isPending;
  const isTesting = testConnectionMutation.isPending;

  return (
    <div className="p-8 space-y-8 w-full max-w-4xl mx-auto">
      <PageHeader
        title="Settings"
        description="Configure LLM providers, credentials, and runner configurations"
      />

      <form onSubmit={handleSave} className="space-y-6">
        <Card>
          <CardContent className="space-y-6 p-8">
            {/* Provider Select */}
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-300">LLM Provider</label>
              <select 
                value={provider} 
                onChange={(e) => setProvider(e.target.value)}
                disabled={isSaving}
                className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="openrouter">OpenRouter</option>
                <option value="local">Local (Ollama)</option>
              </select>
              <p className="text-xs text-text-muted">Configure provider endpoints used by the test AI logic</p>
            </div>

            {/* API Key */}
            {provider !== 'local' && (
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-300 flex justify-between">
                  <span>API Key</span>
                  {serverSettings?.has_key && <span className="text-pass font-medium text-xs">✓ API Key Stored</span>}
                </label>
                <input 
                  type="password" 
                  value={apiKey} 
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={serverSettings?.has_key ? '••••••••••••••••••••' : 'Enter API Key'}
                  disabled={isSaving}
                  className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition"
                />
                <p className="text-xs text-text-muted">Stored securely in the system keyring — never saved in plaintext database</p>
              </div>
            )}

            {/* Model */}
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-300">Model Name</label>
              <input 
                type="text" 
                value={model} 
                onChange={(e) => setModel(e.target.value)}
                placeholder="e.g. gpt-4-turbo"
                disabled={isSaving}
                className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition"
              />
            </div>

            {/* Test Connection */}
            <div className="pt-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleTestConnection}
                loading={isTesting}
                className="gap-1.5"
              >
                {!isTesting && <RefreshCw className="w-3.5 h-3.5" />}
                <span>Test Connection</span>
              </Button>
              
              {testResult && (
                <div className={`mt-3 p-3 rounded-lg text-xs flex items-start gap-2.5 border ${
                  testResult.ok ? 'bg-pass/10 border-pass/20 text-pass' : 'bg-fail/10 border-fail/20 text-fail'
                }`}>
                  {testResult.ok ? (
                    <Check className="w-4 h-4 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  )}
                  <span className="font-semibold">{testResult.message}</span>
                </div>
              )}
            </div>

            <hr className="border-edge/40" />

            {/* Configs Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-300">AI Assistance Mode</label>
                <select
                  value={aiMode}
                  onChange={(e) => setAiMode(e.target.value)}
                  disabled={isSaving}
                  className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition"
                >
                  <option value="Off">Off (Strict Local Tests)</option>
                  <option value="Creation">Creation Mode (AI assists flow creation)</option>
                  <option value="Full">Full Mode (AI Creation + Self-Healing runs)</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-300">Visual Diff Threshold</label>
                <div className="flex items-center gap-4">
                  <input 
                    type="range" 
                    min="0.01" 
                    max="0.20" 
                    step="0.01"
                    value={visualThreshold} 
                    onChange={(e) => setVisualThreshold(parseFloat(e.target.value))}
                    disabled={isSaving}
                    className="w-full accent-primary cursor-pointer"
                  />
                  <span className="text-sm text-slate-400 font-mono w-12 text-right">
                    {Math.round(visualThreshold * 100)}%
                  </span>
                </div>
                <p className="text-xs text-text-muted">Difference percentage threshold to trigger visual error alerts</p>
              </div>
            </div>

            {/* Submit */}
            <div className="pt-4 flex justify-end">
              <Button
                type="submit"
                loading={isSaving}
                className="gap-2"
              >
                <Save className="w-4 h-4" />
                <span>Save Settings</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
