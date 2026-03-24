import client from "./client";
import { EvaluationRun, TaskResult } from "../types";

export async function listRuns(): Promise<EvaluationRun[]> {
  const response = await client.get<EvaluationRun[]>("/runs");
  return response.data;
}

export async function createRun(data: {
  dataset_id: number;
  model_config_id: number;
  name?: string;
  params_override?: Record<string, unknown>;
}): Promise<EvaluationRun> {
  const response = await client.post<EvaluationRun>("/runs", data);
  return response.data;
}

export async function createBatchRuns(data: {
  dataset_ids: number[];
  model_config_ids: number[];
  params_override?: Record<string, unknown>;
}): Promise<EvaluationRun[]> {
  const response = await client.post<EvaluationRun[]>("/runs/batch", data);
  return response.data;
}

export async function getRun(id: number): Promise<EvaluationRun> {
  const response = await client.get<EvaluationRun>(`/runs/${id}`);
  return response.data;
}

export async function getRunTasks(
  runId: number,
  skip: number = 0,
  limit: number = 50,
  status?: string,
  is_correct?: boolean
): Promise<{ tasks: TaskResult[]; total: number }> {
  const params: Record<string, unknown> = { skip, limit };
  if (status && status !== "all") {
    params.status = status;
  }
  if (is_correct !== undefined) {
    params.is_correct = is_correct;
  }
  const response = await client.get<{ tasks: TaskResult[]; total: number }>(
    `/runs/${runId}/tasks`,
    { params }
  );
  return response.data;
}

export async function cancelRun(id: number): Promise<void> {
  await client.post(`/runs/${id}/cancel`);
}

export async function deleteRun(id: number): Promise<void> {
  await client.delete(`/runs/${id}`);
}
