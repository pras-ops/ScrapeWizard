import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Tests from './pages/Tests';
import NewTest from './pages/NewTest';
import TestDetail from './pages/TestDetail';
import RunDetail from './pages/RunDetail';
import RunHistory from './pages/RunHistory';
import Settings from './pages/Settings';

// Mock the api module to return mock promises instead of actual fetches
vi.mock('./lib/api', () => ({
  API_BASE: '',
  api: {
    getStats: vi.fn(() => Promise.resolve({ tests: 0, pass_rate_7d: 0, runs_today: 0, ai_spend: 0 })),
    listRuns: vi.fn(() => Promise.resolve([])),
    listTests: vi.fn(() => Promise.resolve([])),
    getSettings: vi.fn(() => Promise.resolve({ provider: 'openai', model: 'gpt-4', has_key: false, visual_threshold: 0.05, retention: 10 })),
    getLocalStatus: vi.fn(() => Promise.resolve({ daemon_running: false, recommended_model: 'qwen2.5-coder:3b', installed_models: [] })),
    getTest: vi.fn(() => Promise.resolve({ id: 1, name: 'Mock Test', url: 'https://example.com', steps: [] })),
    getRun: vi.fn(() => Promise.resolve({ id: 1, test_id: 1, test_name: 'Mock Test', status: 'passed', started_at: '2026-06-26T21:41:13', finished_at: null, duration_ms: 100, ai_calls: 0, ai_cost_usd: 0, step_results: [] })),
  }
}));

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: Infinity,
      gcTime: Infinity,
    },
  },
});

const renderWithProviders = (ui: React.ReactElement, prefillData: Record<string, any> = {}) => {
  const queryClient = createTestQueryClient();
  
  // Prefill cache to enable synchronous rendering in tests
  Object.entries(prefillData).forEach(([keyStr, data]) => {
    try {
      const key = JSON.parse(keyStr);
      queryClient.setQueryData(key, data);
    } catch {
      queryClient.setQueryData([keyStr], data);
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('Frontend Component Smoke Tests', () => {
  it('renders Dashboard without crashing', () => {
    const { getAllByText } = renderWithProviders(<Dashboard />, {
      '["stats"]': { tests: 0, pass_rate_7d: 0, runs_today: 0, ai_spend: 0 },
      '["runs",{}]': []
    });
    expect(getAllByText(/Dashboard/i)[0]).toBeInTheDocument();
  });

  it('renders Tests page without crashing', () => {
    const { getAllByText } = renderWithProviders(<Tests />, {
      '["tests"]': []
    });
    expect(getAllByText(/Test Suite/i)[0]).toBeInTheDocument();
  });

  it('renders NewTest page without crashing', () => {
    const { getAllByText } = renderWithProviders(<NewTest />);
    expect(getAllByText(/Target Website/i)[0]).toBeInTheDocument();
  });

  it('renders TestDetail page without crashing', () => {
    const { getAllByText } = renderWithProviders(<TestDetail testId={1} />, {
      '["tests",1]': { id: 1, name: 'Mock Test', url: 'https://example.com', steps: [] }
    });
    expect(getAllByText(/Run Sandbox/i)[0]).toBeInTheDocument();
  });

  it('renders RunDetail page without crashing', () => {
    const { getAllByText } = renderWithProviders(<RunDetail runId={1} />, {
      '["runs",1]': { id: 1, test_id: 1, test_name: 'Mock Test', status: 'passed', started_at: '2026-06-26T21:41:13', finished_at: null, duration_ms: 100, ai_calls: 0, ai_cost_usd: 0, step_results: [] }
    });
    expect(getAllByText(/Back to Test Manager/i)[0]).toBeInTheDocument();
  });

  it('renders RunHistory page without crashing', () => {
    const { getAllByText } = renderWithProviders(<RunHistory />, {
      '["runs",{}]': []
    });
    expect(getAllByText(/Execution History/i)[0]).toBeInTheDocument();
  });

  it('renders Settings page without crashing', () => {
    const { getAllByText } = renderWithProviders(<Settings />, {
      '["settings"]': { provider: 'openai', model: 'gpt-4', has_key: false, visual_threshold: 0.05, retention: 10 }
    });
    expect(getAllByText(/LLM Provider/i)[0]).toBeInTheDocument();
  });
});
