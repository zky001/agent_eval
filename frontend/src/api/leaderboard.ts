import client from "./client";
import { LeaderboardEntry } from "../types";

export async function getLeaderboard(datasetId?: number | string): Promise<LeaderboardEntry[]> {
  const params: Record<string, unknown> = {};
  if (datasetId !== undefined) {
    params.dataset_id = datasetId;
  }
  const response = await client.get<LeaderboardEntry[]>("/leaderboard", { params });
  return response.data;
}

export async function compareModels(modelIds: number[], datasetId?: number): Promise<LeaderboardEntry[]> {
  const params: Record<string, unknown> = {
    model_ids: modelIds.join(","),
  };
  if (datasetId !== undefined) {
    params.dataset_id = datasetId;
  }
  const response = await client.get<LeaderboardEntry[]>("/leaderboard/compare", { params });
  return response.data;
}
