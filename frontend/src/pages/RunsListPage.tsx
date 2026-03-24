import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Space,
  Tag,
  Typography,
  Card,
  Spin,
  message,
  Popconfirm,
  Progress,
} from "antd";
import {
  PlusOutlined,
  EyeOutlined,
  DeleteOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { listRuns, cancelRun, deleteRun } from "../api/runs";
import { EvaluationRun } from "../types";

const statusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  completed: "success",
  failed: "error",
  cancelled: "warning",
};

const RunsListPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const data = await listRuns();
      setRuns(data);
    } catch {
      message.error("Failed to load evaluation runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleCancel = async (id: number) => {
    try {
      await cancelRun(id);
      message.success("Run cancelled");
      fetchRuns();
    } catch {
      message.error("Failed to cancel run");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteRun(id);
      message.success("Run deleted");
      fetchRuns();
    } catch {
      message.error("Failed to delete run");
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: EvaluationRun) => (
        <a onClick={() => navigate(`/runs/${record.id}`)}>
          {text || `Run #${record.id}`}
        </a>
      ),
    },
    {
      title: "Dataset",
      dataIndex: "dataset_id",
      key: "dataset_id",
    },
    {
      title: "Model",
      dataIndex: "model_config_id",
      key: "model_config_id",
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={statusColors[status] || "default"}>
          {status.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: "Progress",
      key: "progress",
      width: 180,
      render: (_: unknown, record: EvaluationRun) => (
        <Progress
          percent={record.total_tasks > 0 ? Math.round((record.completed_tasks / record.total_tasks) * 100) : 0}
          size="small"
          status={
            record.status === "failed"
              ? "exception"
              : record.status === "completed"
              ? "success"
              : "active"
          }
        />
      ),
    },
    {
      title: "Score",
      dataIndex: "aggregate_score",
      key: "aggregate_score",
      render: (score: number | undefined) =>
        score !== undefined && score !== null
          ? `${(score * 100).toFixed(1)}%`
          : "--",
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) =>
        text ? new Date(text).toLocaleString() : "--",
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: EvaluationRun) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/runs/${record.id}`)}
          >
            View
          </Button>
          {(record.status === "running" || record.status === "pending") && (
            <Popconfirm
              title="Cancel this run?"
              onConfirm={() => handleCancel(record.id)}
            >
              <Button type="link" icon={<StopOutlined />}>
                Cancel
              </Button>
            </Popconfirm>
          )}
          <Popconfirm
            title="Delete this run?"
            description="This action cannot be undone."
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          Evaluation Runs
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate("/runs/new")}
        >
          New Run
        </Button>
      </div>

      <Card>
        <Table
          dataSource={runs}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{
            emptyText:
              "No evaluation runs yet. Create one to get started.",
          }}
        />
      </Card>
    </div>
  );
};

export default RunsListPage;
