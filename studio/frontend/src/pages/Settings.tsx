import React, { useEffect, useState } from 'react';
import { api, SettingData } from '../lib/api';
import { Check, AlertCircle, Save, RefreshCw } from 'lucide-react';

export default function Settings() {
  const [settings, setSettings] = useState<SettingData>({
    provider: 'openai',
    model: 'gpt-4-turbo',
    ai_mode: 'Creation',
    has_key: false,
    visual_threshold: 0.05,
    retention: 10
  });

  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [banner, setBanner] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  useEffect(() => {
    async function loadSettings() {
      try {
        setLoading(true);
        const data = await api.getSettings();
        setSettings(data);
      } catch (err: any) {
        setBanner({ type: 'error', message: err.message || 'Failed to load settings.' });
      } finally {
        setLoading(false);
      }
    }
    loadSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const payload: any = { ...settings };
      if (apiKey) {
        payload.api_key = apiKey;
      }
      const res = await api.updateSettings(payload);
      setApiKey(''); // Clear key field
      
      // Reload settings to get updated `has_key`
      const freshData = await api.getSettings();
      setSettings(freshData);
      
      setBanner({ type: 'success', message: res.message });
      setTimeout(() => setBanner(null), 3000);
    } catch (err: any) {
      setBanner({ type: 'error', message: err.message || 'Failed to save settings.' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!apiKey && !settings.has_key && settings.provider !== 'local') {
      setTestResult({ ok: false, message: 'Please enter an API Key to test.' });
      return;
    }

    try {
      setTestLoading(true);
      setTestResult(null);
      
      // Connection test uses the input key, or placeholder if already set
      const res = await api.testConnection({
        provider: settings.provider,
        model: settings.model,
        api_key: apiKey || '•••• set'
      });
      setTestResult(res);
    } catch (err: any) {
      setTestResult({ ok: false, message: err.message || 'Test failed.' });
    } finally {
      setTestLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 space-y-6 w-full animate-pulse">
        <div className="h-10 w-48 bg-slate-700/50 rounded-lg"></div>
        <div className="h-96 bg-slate-800/30 rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white display-font">Settings</h1>
        <p className="text-slate-400 mt-1">Configure LLM providers, credentials, and runner configurations</p>
      </div>

      {banner && (
        <div className={`p-4 rounded-lg flex items-center gap-3 border ${
          banner.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        }`}>
          {banner.type === 'success' ? <Check className="w-5 h-5 shrink-0" /> : <AlertCircle className="w-5 h-5 shrink-0" />}
          <span className="text-sm font-medium">{banner.message}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6 bg-slate-850 p-8 rounded-xl border border-slate-750">
        
        {/* Provider Select */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-300">LLM Provider</label>
          <select 
            value={settings.provider} 
            onChange={(e) => setSettings({ ...settings, provider: e.target.value })}
            className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-none transition"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="openrouter">OpenRouter</option>
            <option value="local">Local (Ollama)</option>
          </select>
          <p className="text-xs text-slate-500">Configure provider endpoints used by the scraper AI logic</p>
        </div>

        {/* API Key */}
        {settings.provider !== 'local' && (
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300 flex justify-between">
              <span>API Key</span>
              {settings.has_key && <span className="text-emerald-400 font-medium text-xs">✓ API Key Stored</span>}
            </label>
            <input 
              type="password" 
              value={apiKey} 
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={settings.has_key ? '••••••••••••••••••••' : 'Enter API Key'}
              className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-none transition"
            />
            <p className="text-xs text-slate-500">Stored securely in the system keyring — never saved in plain text database</p>
          </div>
        )}

        {/* Model */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-300">Model Name</label>
          <input 
            type="text" 
            value={settings.model} 
            onChange={(e) => setSettings({ ...settings, model: e.target.value })}
            placeholder="e.g. gpt-4-turbo"
            className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-none transition"
          />
        </div>

        {/* Test Connection Buttons */}
        <div className="pt-2">
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={testLoading}
            className="flex items-center gap-2 px-4 py-2 border border-slate-750 hover:bg-slate-800 text-slate-300 rounded-lg text-sm font-medium transition disabled:opacity-50"
          >
            {testLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span>Test Connection</span>
          </button>
          
          {testResult && (
            <div className={`mt-3 p-3 rounded-lg text-sm flex items-start gap-2.5 border ${
              testResult.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}>
              {testResult.ok ? <Check className="w-4 h-4 shrink-0 mt-0.5" /> : <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />}
              <span className="font-medium">{testResult.message}</span>
            </div>
          )}
        </div>

        <hr className="border-slate-750" />

        {/* Configs Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300">AI Assistance Mode</label>
            <select
              value={settings.ai_mode}
              onChange={(e) => setSettings({ ...settings, ai_mode: e.target.value })}
              className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-600 focus:outline-none transition"
            >
              <option value="Off">Off (Strict Local Scrapers)</option>
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
                value={settings.visual_threshold} 
                onChange={(e) => setSettings({ ...settings, visual_threshold: parseFloat(e.target.value) })}
                className="w-full accent-blue-500"
              />
              <span className="text-sm text-slate-400 font-mono w-12 text-right">
                {Math.round(settings.visual_threshold * 100)}%
              </span>
            </div>
            <p className="text-xs text-slate-500">Difference percentage threshold to trigger visual error alerts</p>
          </div>
        </div>

        {/* Submit */}
        <div className="pt-4 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-blue-500/10 transition duration-150 disabled:opacity-50"
          >
            <Save className="w-5 h-5" />
            <span>Save Settings</span>
          </button>
        </div>
      </form>
    </div>
  );
}
