import React, { useEffect, useState } from "react";
import {
  Table,
  Select,
  Typography,
  Card,
  message,
  Space,
  Tag,
} from "antd";
import { TrophyOutlined } from "@ant-design/icons";
import { getLeaderboard } from "../api/leaderboard";
import { listDatasets } from "../api/datasets";
import { listModels } from "../api/models";
import ScoreChart from "../components/ScoreChart";
import { Dataset, LeaderboardEntry, ModelConfig } from "../types";

const medalColors: Record<number, string> = {
  1: "#ffd700",
  2: "#c0c0c0",
  3: "#cd7f32",
};

const LeaderboardPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<number | undefined>(
    undefined
  );

  useEffect(() => {
    listDatasets().then(setDatasets).catch(() => undefined);
    listModels().then(setModels).catch(() => undefined);
  }, []);

  const fetchLeaderboard = async (datasetId?: number) => {
    setLoading(true);
    try {
      const data = await getLeaderboard(datasetId);
      setEntries(data);
    } catch {
      message.error("加载排行榜失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaderboard();
  }, []);

  const handleDatasetChange = (value: number | undefined) => {
    setSelectedDataset(value);
    fetchLeaderboard(value);
  };

  const maxScore =
    entries.length > 0 ? Math.max(...entries.map((e) => e.score)) : 1;

  const columns = [
    {
      title: "排名",
      key: "rank",
      width: 80,
      render: (_: unknown, __: LeaderboardEntry, index: number) => {
        const rank = index + 1;
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
      title: "模型",
      dataIndex: "model_name",
      key: "model_name",
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: "数据集",
      dataIndex: "dataset_name",
      key: "dataset_name",
      render: (text: string) => <Tag>{text}</Tag>,
    },
    {
      title: "得分",
      dataIndex: "score",
      key: "score",
      width: 280,
      sorter: (a: LeaderboardEntry, b: LeaderboardEntry) => a.score - b.score,
      defaultSortOrder: "descend" as const,
      render: (score: number) => {
        const barWidth = maxScore > 0 ? (score / maxScore) * 100 : 0;
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
                    score >= 80 ? "#52c41a" : score >= 50 ? "#faad14" : "#ff4d4f",
                  borderRadius: 4,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <Typography.Text strong>{score.toFixed(1)}%</Typography.Text>
          </div>
        );
      },
    },
    {
      title: "完成运行数",
      dataIndex: "completed_runs",
      key: "completed_runs",
      width: 120,
      align: "center" as const,
    },
    {
      title: "平均延迟",
      dataIndex: "avg_latency",
      key: "avg_latency",
      width: 110,
      render: (val: number) =>
        val !== undefined && val !== null ? `${(val / 1000).toFixed(2)}s` : "--",
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
          排行榜
        </Typography.Title>
        <Space>
          <Typography.Text type="secondary">按数据集筛选：</Typography.Text>
          <Select
            placeholder="全部数据集"
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

      {entries.length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <ScoreChart
            entries={entries}
            colorDomain={models.map((m) => m.name)}
          />
        </Card>
      )}

      <Card>
        <Table
          dataSource={entries}
          columns={columns}
          rowKey={(record) => `${record.model_id}-${record.dataset_name}`}
          loading={loading}
          pagination={false}
          locale={{
            emptyText: "暂无排行数据，完成一些评估运行后这里会展示结果。",
          }}
        />
      </Card>
    </div>
  );
};

export default LeaderboardPage;
