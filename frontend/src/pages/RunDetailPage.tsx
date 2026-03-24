import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card,
  Table,
  Tag,
  Typography,
  Descriptions,
  Spin,
  message,
  Button,
  Progress,
  Space,
  Select,
  Tooltip,
  Popconfirm,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  StopOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { getRun, getRunTasks, cancelRun } from "../api/runs";
import { EvaluationRun, TaskResult } from "../types";

const statusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  completed: "success",
  failed: "error",
  cancelled: "warning",
};

const RunDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [tasks, setTasks] = useState<TaskResult[]>([]);
  const [tasksTotal, setTasksTotal] = useState(0);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filter, setFilter] = useState<string>("all");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRun = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getRun(Number(id));
      setRun(data);
      return data;
    } catch {
      message.error("Failed to load run details");
      return null;
    }
  }, [id]);

  const fetchTasks = useCallback(async () => {
    if (!id) return;
    setTasksLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const result = await getRunTasks(Number(id), skip, pageSize, filter);
      setTasks(result.tasks);
      setTasksTotal(result.total);
    } catch {
      message.error("Failed to load task results");
    } finally {
      setTasksLoading(false);
    }
  }, [id, page, pageSize, filter]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchRun();
      setLoading(false);
    };
    init();
  }, [fetchRun]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Auto-refresh while running or pending
  useEffect(() => {
    if (run && (run.status === "running" || run.status === "pending")) {
      intervalRef.current = setInterval(async () => {
        const updatedRun = await fetchRun();
        if (updatedRun) {
          fetchTasks();
          if (
            updatedRun.status !== "running" &&
            updatedRun.status !== "pending"
          ) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
          }
        }
      }, 3000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [run?.status, fetchRun, fetchTasks]);

  const handleCancel = async () => {
    if (!id) return;
    try {
      await cancelRun(Number(id));
      message.success("Run cancelled");
      fetchRun();
    } catch {
      message.error("Failed to cancel run");
    }
  };

  const handleFilterChange = (value: string) => {
    setFilter(value);
    setPage(1);
  };

  const columns = [
    {
      title: "#",
      dataIndex: "item_index",
      key: "item_index",
      width: 60,
    },
    {
      title: "Prompt",
      dataIndex: "prompt",
      key: "prompt",
      ellipsis: true,
      width: 200,
      render: (text: string) => {
        if (!text) return "--";
        return (
          <Tooltip title={text}>
            <span>{text.length > 80 ? text.substring(0, 80) + "..." : text}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "Reference",
      dataIndex: "reference_answer",
      key: "reference_answer",
      width: 150,
      render: (text: string) => {
        if (!text) return "--";
        return (
          <Tooltip title={text}>
            <span>{text.length > 60 ? text.substring(0, 60) + "..." : text}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "Model Response",
      dataIndex: "raw_response",
      key: "raw_response",
      width: 200,
      render: (text: string) => {
        if (!text) return "--";
        return (
          <Tooltip title={text}>
            <span>{text.length > 80 ? text.substring(0, 80) + "..." : text}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "Parsed",
      dataIndex: "parsed_answer",
      key: "parsed_answer",
      width: 100,
      render: (text: string) => text || "--",
    },
    {
      title: "Correct",
      dataIndex: "is_correct",
      key: "is_correct",
      width: 80,
      align: "center" as const,
      render: (val: boolean | undefined, record: TaskResult) => {
        if (record.status === "pending") return <Tag>PENDING</Tag>;
        if (record.status === "failed")
          return <Tag color="error">FAILED</Tag>;
        if (val === true)
          return (
            <CheckCircleFilled style={{ color: "#52c41a", fontSize: 18 }} />
          );
        if (val === false)
          return (
            <CloseCircleFilled style={{ color: "#ff4d4f", fontSize: 18 }} />
          );
        return "--";
      },
    },
    {
      title: "Score",
      dataIndex: "score",
      key: "score",
      width: 80,
      render: (val: number | undefined) =>
        val !== undefined && val !== null ? val.toFixed(2) : "--",
    },
    {
      title: "Latency",
      dataIndex: "latency_ms",
      key: "latency_ms",
      width: 90,
      render: (val: number | undefined) =>
        val !== undefined && val !== null ? `${val}ms` : "--",
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!run) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Typography.Text type="secondary">Run not found</Typography.Text>
      </div>
    );
  }

  const isActive = run.status === "running" || run.status === "pending";

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/runs")}
          style={{ padding: 0 }}
        >
          Back to Runs
        </Button>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 16,
          }}
        >
          <Typography.Title level={4} style={{ margin: 0 }}>
            {run.name || `Run #${run.id}`}
          </Typography.Title>
          <Space>
            {isActive && (
              <Tag color={statusColors[run.status]} style={{ fontSize: 14, padding: "4px 12px" }}>
                {run.status.toUpperCase()}
              </Tag>
            )}
            {isActive && (
              <Popconfirm
                title="Cancel this evaluation run?"
                onConfirm={handleCancel}
              >
                <Button danger icon={<StopOutlined />}>
                  Cancel Run
                </Button>
              </Popconfirm>
            )}
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                fetchRun();
                fetchTasks();
              }}
            >
              Refresh
            </Button>
          </Space>
        </div>

        <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="Dataset">
            {run.dataset_id}
          </Descriptions.Item>
          <Descriptions.Item label="Model">
            {run.model_config_id}
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            <Tag color={statusColors[run.status] || "default"}>
              {run.status.toUpperCase()}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Progress">
            <Progress
              percent={run.total_tasks > 0 ? Math.round((run.completed_tasks / run.total_tasks) * 100) : 0}
              status={
                run.status === "failed"
                  ? "exception"
                  : run.status === "completed"
                  ? "success"
                  : "active"
              }
              style={{ width: 200 }}
            />
          </Descriptions.Item>
          <Descriptions.Item label="Tasks">
            {run.completed_tasks} / {run.total_tasks} completed
          </Descriptions.Item>
          <Descriptions.Item label="Failed">
            {run.failed_tasks}
          </Descriptions.Item>
          <Descriptions.Item label="Score">
            {run.aggregate_score !== undefined && run.aggregate_score !== null
              ? `${(run.aggregate_score * 100).toFixed(1)}%`
              : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="Started">
            {run.started_at
              ? new Date(run.started_at).toLocaleString()
              : "--"}
          </Descriptions.Item>
          {run.completed_at && (
            <Descriptions.Item label="Completed">
              {new Date(run.completed_at).toLocaleString()}
            </Descriptions.Item>
          )}
          {run.error_message && (
            <Descriptions.Item label="Error" span={3}>
              <Typography.Text type="danger">{run.error_message}</Typography.Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card
        title="Task Results"
        extra={
          <Space>
            <Typography.Text type="secondary">Filter:</Typography.Text>
            <Select
              value={filter}
              onChange={handleFilterChange}
              style={{ width: 140 }}
              options={[
                { label: "All", value: "all" },
                { label: "Correct", value: "correct" },
                { label: "Incorrect", value: "incorrect" },
                { label: "Failed", value: "failed" },
              ]}
            />
          </Space>
        }
      >
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="task_id"
          loading={tasksLoading}
          scroll={{ x: 1000 }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: tasksTotal,
            showSizeChanger: true,
            showTotal: (t) => `Total ${t} results`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: "No task results yet" }}
        />
      </Card>
    </div>
  );
};

export default RunDetailPage;
