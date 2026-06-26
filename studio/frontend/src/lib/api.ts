// Typesafe API client for ScrapeWizard Studio

export const API_BASE = '';

export interface SettingData {
  provider: string;
  model: string;
  ai_mode: string;
  has_key: boolean;
  visual_threshold: number;
  retention: number;
  local_base_url?: string;
  local_model?: string;
  offline_only?: boolean;
}

export interface StepData {
  id?: number;
  test_id: number;
  order: number;
  action: string;
  value: string;
  selectors: Array<{ kind: string; value: string }>;
  assertions: Array<{ kind: string; value: string }>;
  fingerprint: any;
}

export interface TestData {
  id: number;
  name: string;
  url: string;
  step_count?: number;
  last_run?: {
    id: number;
    status: string;
    started_at: string;
  } | null;
  steps?: StepData[];
}

export interface RunSummary {
  id: number;
  test_id: number;
  test_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  ai_calls: number;
  ai_cost_usd: number;
}

export interface StepResultData {
  id: number;
  run_id: number;
  step_name: string;
  status: string;
  duration_ms: number;
  screenshot_path: string | null;
  visual_diff_score: number | null;
  console_errors: string[];
  network_errors: string[];
  a11y_violations: any[];
  healed: boolean;
  error_message: string | null;
}

export interface RunDetailData extends RunSummary {
  step_results: StepResultData[];
}

export interface DashboardStats {
  tests: number;
  pass_rate_7d: number;
  runs_today: number;
  ai_spend: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const errData = await response.json();
      message = errData.detail || errData.message || message;
    } catch {
      // Ignore
    }
    throw new Error(message);
  }

  // Handle empty bodies (e.g. DELETE or updates)
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  getSettings: () => request<SettingData>('/settings'),
  updateSettings: (data: Partial<SettingData> & { api_key?: string }) =>
    request<{ status: string; message: string }>('/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  testConnection: (data: { provider: string; model: string; api_key?: string; local_base_url?: string }) =>
    request<{ ok: boolean; message: string }>('/settings/test-connection', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getLocalStatus: () =>
    request<{
      daemon_running: boolean;
      daemon_version: string;
      installed_models: string[];
      hardware_tier: string;
      ram_gb: number;
      gpu: string;
      recommended_model: string;
    }>('/settings/local-status'),

  listTests: () => request<TestData[]>('/tests'),
  createTest: (data: { url: string; name?: string }) =>
    request<{ id: number; name: string; url: string }>('/tests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getTest: (id: number) => request<TestData>(`/tests/${id}`),
  updateTest: (id: number, data: { name?: string; steps?: Partial<StepData>[] }) =>
    request<{ status: string; message: string }>(`/tests/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteTest: (id: number) =>
    request<{ status: string; message: string }>(`/tests/${id}`, {
      method: 'DELETE',
    }),
  recordTest: (id: number) =>
    request<{ status: string }>([/tests/, id, '/record'].join(''), {
      method: 'POST',
    }),
  getRecordStatus: (id: number) =>
    request<{ recording: boolean; step_count: number }>(`/tests/${id}/record/status`),

  triggerRun: (test_id: number) =>
    request<{ run_id: number; status: string }>(`/tests/${test_id}/run`, {
      method: 'POST',
    }),
  listRuns: (test_id?: number, status?: string) => {
    const params = new URLSearchParams();
    if (test_id) params.append('test_id', String(test_id));
    if (status) params.append('status', status);
    return request<RunSummary[]>(`/runs?${params.toString()}`);
  },
  getRun: (run_id: number) => request<RunDetailData>(`/runs/${run_id}`),

  getStats: () => request<DashboardStats>('/stats'),
};
