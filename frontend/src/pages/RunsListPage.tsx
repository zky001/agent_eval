import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Space,
  Tag,
  Typography,
  Card,
  message,
  Popconfirm,
  Progress,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  EyeOutlined,
  DeleteOutlined,
  StopOutlined,
  DiffOutlined,
} from "@ant-design/icons";
import { listRuns, cancelRun, deleteRun } from "../api/runs";
import { EvaluationRun, RUN_STATUS_LABELS } from "../types";

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
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const fetchRuns = async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    try {
      const data = await listRuns();
      setRuns(data);
    } catch {
      message.error("加载评估运行失败");
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  // 有运行中的任务时静默轮询
  const hasActiveRuns = runs.some(
    (r) => r.status === "running" || r.status === "pending"
  );
  useEffect(() => {
    if (!hasActiveRuns) return;
    const timer = setInterval(() => fetchRuns(false), 4000);
    return () => clearInterval(timer);
  }, [hasActiveRuns]);

  const handleCancel = async (id: number) => {
    try {
      await cancelRun(id);
      message.success("已取消运行");
      fetchRuns();
    } catch {
      message.error("取消失败");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteRun(id);
      message.success("已删除运行");
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      fetchRuns();
    } catch {
      message.error("删除失败");
    }
  };

  const selectedRuns = runs.filter((r) => selectedIds.includes(r.id));
  const sameDataset =
    selectedRuns.length >= 2 &&
    selectedRuns.every((r) => r.dataset_id === selectedRuns[0].dataset_id);
  const canCompare = selectedRuns.length >= 2 && selectedRuns.length <= 4 && sameDataset;

  const columns = [
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: EvaluationRun) => (
        <a onClick={() => navigate(`/runs/${record.id}`)}>
          {text || `运行 #${record.id}`}
        </a>
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
      title: "进度",
      key: "progress",
      width: 180,
      render: (_: unknown, record: EvaluationRun) => (
        <Progress
          percent={
            record.total_tasks > 0
              ? Math.round((record.completed_tasks / record.total_tasks) * 100)
              : 0
          }
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
      title: "得分",
      dataIndex: "aggregate_score",
      key: "aggregate_score",
      render: (score: number | undefined) =>
        score !== undefined && score !== null
          ? `${(score * 100).toFixed(1)}%`
          : "--",
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? new Date(text).toLocaleString() : "--"),
    },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: EvaluationRun) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/runs/${record.id}`)}
          >
            查看
          </Button>
          {(record.status === "running" || record.status === "pending") && (
            <Popconfirm title="取消这个运行？" onConfirm={() => handleCancel(record.id)}>
              <Button type="link" icon={<StopOutlined />}>
                取消
              </Button>
            </Popconfirm>
          )}
          <Popconfirm
            title="删除这个运行？"
            description="此操作不可撤销。"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
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
          评估运行
        </Typography.Title>
        <Space>
          <Tooltip
            title={
              selectedRuns.length < 2
                ? "勾选 2-4 个同数据集的运行进行对比"
                : !sameDataset
                ? "只能对比同一数据集上的运行"
                : ""
            }
          >
            <Button
              icon={<DiffOutlined />}
              disabled={!canCompare}
              onClick={() =>
                navigate(`/runs/compare?ids=${selectedIds.join(",")}`)
              }
            >
              对比所选 ({selectedRuns.length})
            </Button>
          </Tooltip>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate("/runs/new")}
          >
            新建评估
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={runs}
          columns={columns}
          rowKey="id"
          loading={loading}
          rowSelection={{
            selectedRowKeys: selectedIds,
            onChange: (keys) => setSelectedIds(keys.map(Number)),
            getCheckboxProps: () => ({}),
          }}
          locale={{ emptyText: "还没有评估运行，点击右上角新建。" }}
        />
      </Card>
    </div>
  );
};

export default RunsListPage;
