import client from "./client";
import { ModelConfig } from "../types";

export async function listModels(): Promise<ModelConfig[]> {
  const response = await client.get<ModelConfig[]>("/models");
  return response.data;
}

export async function createModel(data: {
  name: string;
  provider: string;
  model_id: string;
  api_key?: string;
  api_base_url?: string;
  default_params?: Record<string, unknown>;
}): Promise<ModelConfig> {
  const response = await client.post<ModelConfig>("/models", data);
  return response.data;
}

export async function getModel(id: string): Promise<ModelConfig> {
  const response = await client.get<ModelConfig>(`/models/${id}`);
  return response.data;
}

export async function updateModel(
  id: string,
  data: Partial<{
    name: string;
    provider: string;
    model_id: string;
    api_key: string;
    api_base_url: string;
    default_params: Record<string, unknown>;
  }>
): Promise<ModelConfig> {
  const response = await client.put<ModelConfig>(`/models/${id}`, data);
  return response.data;
}

export async function deleteModel(id: string): Promise<void> {
  await client.delete(`/models/${id}`);
}

export async function testModel(id: string): Promise<{ success: boolean; response?: string; error?: string; latency_ms?: number }> {
  const response = await client.post<{ success: boolean; response?: string; error?: string; latency_ms?: number }>(
    `/models/${id}/test`
  );
  return response.data;
}
