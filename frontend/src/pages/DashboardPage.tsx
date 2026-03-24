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
import { Dataset, ModelConfig, EvaluationRun } from "../types";

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

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [ds, ms, rs] = await Promise.all([
          listDatasets().catch(() => []),
          listModels().catch(() => []),
          listRuns().catch(() => []),
        ]);
        setDatasets(ds);
        setModels(ms);
        setRuns(rs);
      } catch {
        message.error("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const recentRuns = runs.slice(0, 10);

  const runColumns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: EvaluationRun) => (
        <a onClick={() => navigate(`/runs/${record.id}`)}>{text || `Run #${record.id}`}</a>
      ),
    },
    {
      title: "Dataset ID",
      dataIndex: "dataset_id",
      key: "dataset_id",
    },
    {
      title: "Model ID",
      dataIndex: "model_config_id",
      key: "model_config_id",
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={statusColors[status] || "default"}>{status.toUpperCase()}</Tag>
      ),
    },
    {
      title: "Score",
      dataIndex: "aggregate_score",
      key: "aggregate_score",
      render: (score: number | undefined) =>
        score !== undefined && score !== null ? `${(score * 100).toFixed(1)}%` : "--",
    },
    {
      title: "Created",
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
      <Typography.Title level={3}>Dashboard</Typography.Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate("/datasets")}>
            <Statistic
              title="Total Datasets"
              value={datasets.length}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate("/models")}>
            <Statistic
              title="Models Configured"
              value={models.length}
              prefix={<RobotOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate("/runs/new")}>
            <Statistic
              title="Evaluation Runs"
              value={runs.length}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <Card title="Quick Actions">
            <Space wrap>
              <Button
                type="primary"
                icon={<ImportOutlined />}
                onClick={() => navigate("/datasets")}
              >
                Import Dataset
              </Button>
              <Button icon={<SettingOutlined />} onClick={() => navigate("/models")}>
                Configure Model
              </Button>
              <Button
                type="primary"
                ghost
                icon={<ThunderboltOutlined />}
                onClick={() => navigate("/runs/new")}
              >
                Start Evaluation
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="Recent Evaluation Runs">
        <Table
          dataSource={recentRuns}
          columns={runColumns}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: "No evaluation runs yet. Start one from the Quick Actions above." }}
        />
      </Card>
    </div>
  );
};

export default DashboardPage;
