import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, SettingData, TestData, RunSummary, RunDetailData, DashboardStats, StepData } from "../lib/api";

// 1. Settings Queries & Mutations
export function useSettings() {
  return useQuery<SettingData>({
    queryKey: ["settings"],
    queryFn: api.getSettings,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<SettingData> & { api_key?: string }) => api.updateSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: (data: { provider: string; model: string; api_key?: string; local_base_url?: string }) =>
      api.testConnection(data),
  });
}

// 2. Tests Queries & Mutations
export function useTests() {
  return useQuery<TestData[]>({
    queryKey: ["tests"],
    queryFn: api.listTests,
  });
}

export function useTest(id: number) {
  return useQuery<TestData>({
    queryKey: ["tests", id],
    queryFn: () => api.getTest(id),
    enabled: !!id && id > 0,
  });
}

export function useCreateTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { url: string; name?: string }) => api.createTest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useUpdateTest(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name?: string; steps?: Partial<StepData>[] }) =>
      api.updateTest(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests", id] });
      queryClient.invalidateQueries({ queryKey: ["tests"] });
    },
  });
}

export function useDeleteTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteTest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useRecordTest() {
  return useMutation({
    mutationFn: (id: number) => api.recordTest(id),
  });
}

export function useRecordStatus(id: number, enabled: boolean = false) {
  return useQuery({
    queryKey: ["tests", id, "record-status"],
    queryFn: () => api.getRecordStatus(id),
    enabled: enabled && !!id,
    refetchInterval: enabled ? 1000 : false,
  });
}

// 3. Runs Queries & Mutations
export function useTriggerRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testId: number) => api.triggerRun(testId),
    onSuccess: (_, testId) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["tests", testId] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useRuns(testId?: number, status?: string) {
  return useQuery<RunSummary[]>({
    queryKey: ["runs", { testId, status }],
    queryFn: () => api.listRuns(testId, status),
  });
}

export function useRun(
  runId: number,
  refetchInterval: number | false | ((query: any) => number | false | undefined) = false
) {
  return useQuery<RunDetailData>({
    queryKey: ["runs", runId],
    queryFn: () => api.getRun(runId),
    enabled: !!runId && runId > 0,
    refetchInterval,
  });
}

// 4. Dashboard Stats
export function useStats() {
  return useQuery<DashboardStats>({
    queryKey: ["stats"],
    queryFn: api.getStats,
  });
}
