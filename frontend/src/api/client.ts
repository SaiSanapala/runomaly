export type Run = {
  run_id: string;
  pipeline_id: string;
  status: "RUNNING" | "SUCCESS" | "FAILED";
  started_at: string;
  finished_at?: string;
  duration_seconds?: number;
  git_commit?: string;
  input_filename?: string;
  input_snapshot_path?: string;
  error_type?: string;
  error_message?: string;
  environment_metadata: Record<string, unknown>;
  pipeline_parameters: Record<string, unknown>;
};

export type Step = {
  step_id: number;
  step_name: string;
  status: string;
  started_at: string;
  finished_at?: string;
  duration_seconds?: number;
  error_message?: string;
};

export type Diagnosis = {
  diagnosis_id?: number;
  category: string;
  severity: string;
  confidence: string;
  title: string;
  description: string;
  supporting_evidence: Record<string, unknown>;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  runs: (status = "") => request<Run[]>(`/api/runs${status ? `?status=${status}` : ""}`),
  run: (runId: string) => request<Run>(`/api/runs/${runId}`),
  steps: (runId: string) => request<Step[]>(`/api/runs/${runId}/steps`),
  logs: (runId: string) => request<Array<{ created_at: string; level: string; message: string }>>(`/api/runs/${runId}/logs`),
  comparison: (runId: string) => request<any>(`/api/runs/${runId}/comparison`),
  diagnoses: (runId: string) => request<Diagnosis[]>(`/api/runs/${runId}/diagnoses`),
  impact: (runId: string) => request<any>(`/api/runs/${runId}/impact`),
  replay: (runId: string) => request<any>(`/api/runs/${runId}/replay`, { method: "POST" }),
  trigger: (testFile: string) => {
    const form = new FormData();
    form.append("test_file", testFile);
    return request<Run>("/api/pipelines/daily_order_analytics/run", { method: "POST", body: form });
  }
};

