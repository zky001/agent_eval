export interface Dataset {
  id: number;
  name: string;
  dataset_type: string;
  description?: string;
  total_items: number;
  created_at: string;
}

export interface DatasetItem {
  id: number;
  dataset_id: number;
  item_index: number;
  prompt: string;
  reference_answer?: string;
  metadata?: Record<string, unknown>;
}

export interface ModelConfig {
  id: number;
  name: string;
  provider: string;
  model_id: string;
  api_key?: string;
  api_base_url?: string;
  default_params?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export interface EvaluationRun {
  id: number;
  name?: string;
  dataset_id: number;
  model_config_id: number;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  aggregate_score?: number;
  params_override?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  error_message?: string;
}

export interface TaskResult {
  task_id: number;
  item_index: number;
  prompt: string;
  reference_answer?: string;
  raw_response?: string;
  parsed_answer?: string;
  is_correct?: boolean;
  score?: number;
  latency_ms?: number;
  status: string;
}

export interface LeaderboardEntry {
  model_name: string;
  model_id: number;
  dataset_name: string;
  score: number;
  completed_runs: number;
  avg_latency: number;
}
