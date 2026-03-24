import React, { useEffect, useState } from "react";
import {
  Table,
  Select,
  Typography,
  Card,
  Spin,
  message,
  Space,
  Tag,
} from "antd";
import { TrophyOutlined } from "@ant-design/icons";
import { getLeaderboard } from "../api/leaderboard";
import { listDatasets } from "../api/datasets";
import { Dataset, LeaderboardEntry } from "../types";

const medalColors: Record<number, string> = {
  1: "#ffd700",
  2: "#c0c0c0",
  3: "#cd7f32",
};

const LeaderboardPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string | undefined>(
    undefined
  );

  const fetchDatasets = async () => {
    try {
      const data = await listDatasets();
      setDatasets(data);
    } catch {
      // silent fail for dataset list
    }
  };

  const fetchLeaderboard = async (datasetId?: number | string) => {
    setLoading(true);
    try {
      const data = await getLeaderboard(datasetId);
      setEntries(data);
    } catch {
      message.error("Failed to load leaderboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
    fetchLeaderboard();
  }, []);

  const handleDatasetChange = (value: string | undefined) => {
    setSelectedDataset(value);
    fetchLeaderboard(value);
  };

  const maxScore =
    entries.length > 0 ? Math.max(...entries.map((e) => e.score)) : 1;

  const columns = [
    {
      title: "Rank",
      dataIndex: "rank",
      key: "rank",
      width: 80,
      render: (rank: number) => {
        const color = medalColors[rank];
        if (color) {
          return (
            <Space>
              <TrophyOutlined style={{ color, fontSize: 18 }} />
              <strong>{rank}</strong>
            </Space>
          );
        }
        return <span style={{ paddingLeft: 26 }}>{rank}</span>;
      },
    },
    {
      title: "Model",
      dataIndex: "model_name",
      key: "model_name",
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: "Dataset",
      dataIndex: "dataset_name",
      key: "dataset_name",
      render: (text: string) => <Tag>{text}</Tag>,
    },
    {
      title: "Score",
      dataIndex: "score",
      key: "score",
      width: 280,
      sorter: (a: LeaderboardEntry, b: LeaderboardEntry) =>
        a.score - b.score,
      defaultSortOrder: "descend" as const,
      render: (score: number) => {
        const pct = score;
        const barWidth =
          maxScore > 0 ? (score / maxScore) * 100 : 0;
        return (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 160,
                height: 20,
                backgroundColor: "#f0f0f0",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${barWidth}%`,
                  height: "100%",
                  backgroundColor:
                    pct >= 80
                      ? "#52c41a"
                      : pct >= 50
                      ? "#faad14"
                      : "#ff4d4f",
                  borderRadius: 4,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <Typography.Text strong>{pct.toFixed(1)}%</Typography.Text>
          </div>
        );
      },
    },
    {
      title: "Completed Runs",
      dataIndex: "completed_runs",
      key: "completed_runs",
      width: 140,
      align: "center" as const,
    },
    {
      title: "Avg Latency",
      dataIndex: "avg_latency",
      key: "avg_latency",
      width: 120,
      render: (val: number) =>
        val !== undefined && val !== null ? `${val.toFixed(2)}s` : "--",
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          Leaderboard
        </Typography.Title>
        <Space>
          <Typography.Text type="secondary">Filter by Dataset:</Typography.Text>
          <Select
            placeholder="All Datasets"
            allowClear
            value={selectedDataset}
            onChange={handleDatasetChange}
            style={{ width: 240 }}
            options={datasets.map((ds) => ({
              label: ds.name,
              value: ds.id,
            }))}
          />
        </Space>
      </div>

      <Card>
        <Table
          dataSource={entries}
          columns={columns}
          rowKey={(record) =>
            `${record.model_id}-${record.dataset_name}`
          }
          loading={loading}
          pagination={false}
          locale={{
            emptyText:
              "No leaderboard data yet. Complete some evaluation runs to see results.",
          }}
        />
      </Card>
    </div>
  );
};

export default LeaderboardPage;
