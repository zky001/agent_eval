import client from "./client";
import { Dataset, DatasetItem } from "../types";

export async function listDatasets(): Promise<Dataset[]> {
  const response = await client.get<Dataset[]>("/datasets");
  return response.data;
}

export async function getDataset(id: number): Promise<Dataset> {
  const response = await client.get<Dataset>(`/datasets/${id}`);
  return response.data;
}

export async function importDataset(params: {
  source: string;
  split?: string;
  max_items?: number;
}): Promise<Dataset> {
  const response = await client.post<Dataset>("/datasets/import", params);
  return response.data;
}

export async function uploadDataset(data: {
  name: string;
  dataset_type?: string;
  description?: string;
  items: { prompt: string; reference_answer?: string; metadata?: Record<string, unknown> }[];
}): Promise<Dataset> {
  const response = await client.post<Dataset>("/datasets/upload", data);
  return response.data;
}

export async function getDatasetItems(
  datasetId: number,
  skip: number = 0,
  limit: number = 50
): Promise<DatasetItem[]> {
  const response = await client.get<DatasetItem[]>(
    `/datasets/${datasetId}/items`,
    { params: { skip, limit } }
  );
  return response.data;
}

export async function deleteDataset(id: number): Promise<void> {
  await client.delete(`/datasets/${id}`);
}
