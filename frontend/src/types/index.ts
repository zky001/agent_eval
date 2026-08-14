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
  input_price_per_million?: number;
  output_price_per_million?: number;
  created_at: string;
  updated_at?: string;
}

export interface EvaluationRun {
  id: number;
  name?: string;
  dataset_id: number;
  model_config_id: number;
  judge_model_config_id?: number;
  dataset_name?: string;
  model_name?: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  aggregate_score?: number;
  correct_tasks?: number;
  avg_latency_ms?: number;
  total_tokens?: number;
  cost_usd?: number;
  params_override?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  error_message?: string;
}

export interface TrajectoryStep {
  turn: number;
  model_output: string;
  action?: { tool: string; args: Record<string, unknown> };
  observation?: string;
  final_answer?: string;
  note?: string;
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
  token_count?: number;
  evaluation_details?: Record<string, unknown>;
  trajectory?: TrajectoryStep[] | null;
  status: string;
}

export interface LeaderboardEntry {
  model_name: string;
  model_id: number;
  dataset_name: string;
  score: number;
  completed_runs: number;
  avg_latency: number;
  avg_cost_usd?: number | null;
}

export interface ScoreHistoryPoint {
  run_id: number;
  model_id: number;
  model_name: string;
  score: number;
  completed_at?: string | null;
}

export interface CompareItemResult {
  status: string;
  raw_response?: string;
  parsed_answer?: string;
  is_correct?: boolean;
  score?: number;
  latency_ms?: number;
}

export interface CompareItem {
  item_index: number;
  prompt: string;
  reference_answer?: string;
  results: Record<string, CompareItemResult>;
}

export interface CompareData {
  runs: EvaluationRun[];
  items: CompareItem[];
}

/** 评估类型的中文名，全站统一使用 */
export const DATASET_TYPE_LABELS: Record<string, string> = {
  gsm8k: "数学推理 (GSM8K)",
  mmlu: "综合知识 (MMLU)",
  humaneval: "代码生成 (HumanEval)",
  tool_use: "工具调用",
  multi_step: "多步规划",
  react: "ReAct 推理",
  instruction_following: "指令遵循",
  agent_loop: "多轮工具代理",
  api_interaction: "API 交互",
  error_recovery: "错误恢复",
  llm_judge: "LLM 裁判评分",
  custom: "自定义",
};

export const RUN_STATUS_LABELS: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};
