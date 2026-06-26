import React, { useState, useEffect } from 'react';
import { useSettings, useUpdateSettings, useTestConnection } from '../hooks/useApi';
import { Button, Card, CardContent, PageHeader, ErrorState, toast } from '../components/ui';
import { Check, AlertCircle, Save, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';

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
  
  // Local provider state
  const [localBaseUrl, setLocalBaseUrl] = useState('http://localhost:11434');
  const [localModel, setLocalModel] = useState('qwen2.5-coder:3b');
  const [offlineOnly, setOfflineOnly] = useState(false);
  const [localStatus, setLocalStatus] = useState<any>(null);
  const [pullProgress, setPullProgress] = useState<{ status: string; percent?: number } | null>(null);
  const [isPulling, setIsPulling] = useState(false);

  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const fetchLocalStatus = async () => {
    try {
      const res = await api.getLocalStatus();
      setLocalStatus(res);
    } catch (e) {
      setLocalStatus({ daemon_running: false });
    }
  };

  // Synchronize state when data loads
  useEffect(() => {
    if (serverSettings) {
      setProvider(serverSettings.provider);
      setModel(serverSettings.model);
      setAiMode(serverSettings.ai_mode);
      setVisualThreshold(serverSettings.visual_threshold);
      setRetention(serverSettings.retention);
      if (serverSettings.local_base_url) setLocalBaseUrl(serverSettings.local_base_url);
      if (serverSettings.local_model) setLocalModel(serverSettings.local_model);
      if (serverSettings.offline_only !== undefined) setOfflineOnly(serverSettings.offline_only);
    }
  }, [serverSettings]);

  useEffect(() => {
    if (provider === 'local') {
      fetchLocalStatus();
    }
  }, [provider]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = {
        provider,
        model: provider === 'local' ? localModel : model,
        ai_mode: aiMode,
        visual_threshold: visualThreshold,
        retention,
        local_base_url: localBaseUrl,
        local_model: localModel,
        offline_only: offlineOnly,
      };
      if (apiKey && provider !== 'local') {
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
        model: provider === 'local' ? localModel : model,
        api_key: provider === 'local' ? undefined : (apiKey || '•••• set'),
        local_base_url: provider === 'local' ? localBaseUrl : undefined
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

  const handlePullModel = async (modelToPull: string) => {
    try {
      setIsPulling(true);
      setPullProgress({ status: 'Initiating download...' });
      
      const response = await fetch('/api/settings/pull-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelToPull, local_base_url: localBaseUrl })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to start download: ${response.statusText}`);
      }
      
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No readable stream available.');
      }
      
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Save the last partial line back to buffer
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.done) {
                if (data.success) {
                  toast.success(`Model ${modelToPull} downloaded successfully.`);
                  setPullProgress({ status: 'Success!', percent: 100 });
                  fetchLocalStatus();
                } else {
                  toast.error(`Failed to download model ${modelToPull}.`);
                  setPullProgress({ status: 'Failed' });
                }
                break;
              }
              
              const status = data.status || '';
              const total = data.total || 0;
              const completed = data.completed || 0;
              let percent = undefined;
              if (total > 0) {
                percent = Math.round((completed / total) * 100);
              }
              
              setPullProgress({ status, percent });
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (err: any) {
      toast.error(err.message || 'Model download failed.');
      setPullProgress({ status: 'Error' });
    } finally {
      setIsPulling(false);
      setTimeout(() => setPullProgress(null), 5000);
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

            {/* Local AI Config Panel */}
            {provider === 'local' ? (
              <div className="bg-slate-900/40 border border-edge/30 rounded-xl p-6 space-y-6">
                <div className="flex items-center justify-between border-b border-edge/30 pb-4">
                  <h3 className="font-semibold text-white">Local AI Configuration</h3>
                  {localStatus && (
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                      localStatus.daemon_running 
                        ? 'bg-pass/10 text-pass border border-pass/20' 
                        : 'bg-fail/10 text-fail border border-fail/20'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${localStatus.daemon_running ? 'bg-pass' : 'bg-fail'}`} />
                      {localStatus.daemon_running ? `Ollama v${localStatus.daemon_version}` : 'Ollama Offline'}
                    </span>
                  )}
                </div>
                
                {localStatus && localStatus.daemon_running && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs bg-slate-950/40 p-4 rounded-lg border border-edge/20">
                    <div>
                      <span className="text-text-muted">Hardware Detected:</span>{' '}
                      <span className="font-mono text-slate-300">{localStatus.ram_gb} GB RAM</span>
                    </div>
                    <div>
                      <span className="text-text-muted">GPU/Processor:</span>{' '}
                      <span className="font-mono text-slate-300">{localStatus.gpu}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Suggested Tier:</span>{' '}
                      <span className="font-semibold text-primary capitalize">{localStatus.hardware_tier}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Recommended Model:</span>{' '}
                      <span className="font-mono text-green-400">{localStatus.recommended_model}</span>
                    </div>
                  </div>
                )}

                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-300">Ollama Base URL</label>
                    <input 
                      type="text" 
                      value={localBaseUrl} 
                      onChange={(e) => setLocalBaseUrl(e.target.value)}
                      placeholder="http://localhost:11434"
                      disabled={isSaving}
                      className="w-full bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-300">Local Model</label>
                    <div className="flex gap-3">
                      <select
                        value={localModel}
                        onChange={(e) => setLocalModel(e.target.value)}
                        disabled={isSaving || isPulling}
                        className="flex-1 bg-slate-800 border border-edge/60 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-hidden transition"
                      >
                        {localStatus?.installed_models && localStatus.installed_models.map((m: string) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        {localStatus?.recommended_model && !localStatus.installed_models?.includes(localStatus.recommended_model) && (
                          <option value={localStatus.recommended_model}>
                            {localStatus.recommended_model} (Recommended, not downloaded)
                          </option>
                        )}
                        {!localStatus?.installed_models?.includes('qwen2.5-coder:3b') && (
                          <option value="qwen2.5-coder:3b">qwen2.5-coder:3b (Recommended, not downloaded)</option>
                        )}
                        {localModel && !localStatus?.installed_models?.includes(localModel) && (
                          <option value={localModel}>{localModel}</option>
                        )}
                      </select>

                      <Button
                        type="button"
                        onClick={() => handlePullModel(localModel)}
                        disabled={isSaving || isPulling}
                        loading={isPulling}
                        variant="secondary"
                        className="shrink-0"
                      >
                        Pull Model
                      </Button>
                    </div>
                  </div>

                  {pullProgress && (
                    <div className="space-y-2 bg-slate-950/40 p-4 rounded-lg border border-edge/20 text-xs">
                      <div className="flex justify-between font-mono text-slate-300">
                        <span>Status: {pullProgress.status}</span>
                        {pullProgress.percent !== undefined && <span>{pullProgress.percent}%</span>}
                      </div>
                      {pullProgress.percent !== undefined && (
                        <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                          <div 
                            className="bg-primary h-full transition-all duration-350"
                            style={{ width: `${pullProgress.percent}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <>
                {/* API Key */}
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
              </>
            )}

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

            {/* Offline-Only Toggle */}
            {provider === 'local' && (
              <div className="flex items-center gap-3 p-4 bg-slate-900/20 border border-edge/20 rounded-lg">
                <input
                  type="checkbox"
                  id="offlineOnly"
                  checked={offlineOnly}
                  onChange={(e) => setOfflineOnly(e.target.checked)}
                  disabled={isSaving}
                  className="w-4 h-4 rounded-sm border-edge text-primary focus:ring-primary focus:ring-offset-2"
                />
                <div className="space-y-0.5">
                  <label htmlFor="offlineOnly" className="text-sm font-semibold text-slate-300 cursor-pointer">
                    Offline-Only Mode
                  </label>
                  <p className="text-xs text-text-muted">
                    Disable all network LLM calls and cloud fallbacks, forcing CodeGen and Self-Healing to remain offline.
                  </p>
                </div>
              </div>
            )}

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
