import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Col,
  Row,
  Statistic,
  Tag,
  Table,
  Button,
  Space,
  Spin,
  message,
  Typography,
} from "antd";
import {
  DatabaseOutlined,
  RobotOutlined,
  PlayCircleOutlined,
  ImportOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { listDatasets } from "../api/datasets";
import { listModels } from "../api/models";
import { listRuns } from "../api/runs";
import { getLeaderboard } from "../api/leaderboard";
import ScoreChart from "../components/ScoreChart";
import {
  Dataset,
  ModelConfig,
  EvaluationRun,
  LeaderboardEntry,
  RUN_STATUS_LABELS,
} from "../types";

const statusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  completed: "success",
  failed: "error",
  cancelled: "warning",
};

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [ds, ms, rs, lb] = await Promise.all([
          listDatasets().catch(() => []),
          listModels().catch(() => []),
          listRuns().catch(() => []),
          getLeaderboard().catch(() => []),
        ]);
        setDatasets(ds);
        setModels(ms);
        setRuns(rs);
        setLeaderboard(lb);
      } catch {
        message.error("加载总览数据失败");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const recentRuns = runs.slice(0, 10);

  const runColumns = [
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: EvaluationRun) => (
        <a onClick={() => navigate(`/runs/${record.id}`)}>{text || `运行 #${record.id}`}</a>
      ),
    },
    {
      title: "数据集",
      dataIndex: "dataset_name",
      key: "dataset_name",
      render: (name: string | undefined, record: EvaluationRun) =>
        name || `#${record.dataset_id}`,
    },
    {
      title: "模型",
      dataIndex: "model_name",
      key: "model_name",
      render: (name: string | undefined, record: EvaluationRun) =>
        name || `#${record.model_config_id}`,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={statusColors[status] || "default"}>
          {RUN_STATUS_LABELS[status] || status}
        </Tag>
      ),
    },
    {
      title: "得分",
      dataIndex: "aggregate_score",
      key: "aggregate_score",
      render: (score: number | undefined) =>
        score !== undefined && score !== null ? `${(score * 100).toFixed(1)}%` : "--",
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? new Date(text).toLocaleString() : "--"),
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Typography.Title level={3}>总览</Typography.Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate("/datasets")}>
            <Statistic
              title="数据集"
              value={datasets.length}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate("/models")}>
            <Statistic
              title="已配置模型"
              value={models.length}
              prefix={<RobotOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate("/runs")}>
            <Statistic
              title="评估运行"
              value={runs.length}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {leaderboard.length > 0 && (
        <Card
          title="模型得分对比"
          extra={<a onClick={() => navigate("/leaderboard")}>完整排行榜</a>}
          style={{ marginBottom: 24 }}
        >
          <ScoreChart
            entries={leaderboard}
            colorDomain={models.map((m) => m.name)}
            showValueLabels
          />
        </Card>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <Card title="快捷操作">
            <Space wrap>
              <Button
                type="primary"
                icon={<ImportOutlined />}
                onClick={() => navigate("/datasets")}
              >
                导入数据集
              </Button>
              <Button icon={<SettingOutlined />} onClick={() => navigate("/models")}>
                配置模型
              </Button>
              <Button
                type="primary"
                ghost
                icon={<ThunderboltOutlined />}
                onClick={() => navigate("/runs/new")}
              >
                启动评估
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="最近评估运行">
        <Table
          dataSource={recentRuns}
          columns={runColumns}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: "还没有评估运行，点击上方快捷操作开始。" }}
        />
      </Card>
    </div>
  );
};

export default DashboardPage;
