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
  DownloadOutlined,
  RedoOutlined,
} from "@ant-design/icons";
import {
  getRun,
  getRunTasks,
  cancelRun,
  retryRun,
  exportRunUrl,
  reviewTask,
} from "../api/runs";
import {
  EvaluationRun,
  TaskResult,
  TrajectoryStep,
  RUN_STATUS_LABELS,
} from "../types";

const statusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  completed: "success",
  failed: "error",
  cancelled: "warning",
};

const taskStatusLabels: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const expandedBlockStyle: React.CSSProperties = {
  margin: "4px 0 0",
  padding: 8,
  background: "#fafafa",
  border: "1px solid #f0f0f0",
  borderRadius: 4,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  maxHeight: 300,
  overflow: "auto",
  fontSize: 12,
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
      message.error("加载运行详情失败");
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
      message.error("加载任务结果失败");
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

  // 运行中自动刷新
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
      message.success("已取消运行");
      fetchRun();
    } catch {
      message.error("取消失败");
    }
  };

  const handleRetry = async () => {
    if (!id) return;
    try {
      await retryRun(Number(id));
      message.success("已重新提交失败任务");
      fetchRun();
      fetchTasks();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "重跑失败");
    }
  };

  const handleFilterChange = (value: string) => {
    setFilter(value);
    setPage(1);
  };

  const handleReview = async (taskId: number, isCorrect: boolean) => {
    if (!id) return;
    try {
      await reviewTask(Number(id), taskId, isCorrect);
      message.success(isCorrect ? "已人工判为正确" : "已人工判为错误");
      fetchTasks();
      fetchRun();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "复核提交失败");
    }
  };

  const columns = [
    {
      title: "#",
      dataIndex: "item_index",
      key: "item_index",
      width: 60,
    },
    {
      title: "题目",
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
      title: "参考答案",
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
      title: "模型响应",
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
      title: "解析结果",
      dataIndex: "parsed_answer",
      key: "parsed_answer",
      width: 100,
      ellipsis: true,
      render: (text: string) => text || "--",
    },
    {
      title: "判定",
      dataIndex: "is_correct",
      key: "is_correct",
      width: 80,
      align: "center" as const,
      render: (val: boolean | undefined, record: TaskResult) => {
        if (record.status === "pending") return <Tag>等待</Tag>;
        if (record.status === "failed") return <Tag color="error">失败</Tag>;
        if (record.status === "cancelled") return <Tag color="warning">取消</Tag>;
        if (val === true)
          return <CheckCircleFilled style={{ color: "#52c41a", fontSize: 18 }} />;
        if (val === false)
          return <CloseCircleFilled style={{ color: "#ff4d4f", fontSize: 18 }} />;
        return "--";
      },
    },
    {
      title: "得分",
      dataIndex: "score",
      key: "score",
      width: 80,
      render: (val: number | undefined) =>
        val !== undefined && val !== null ? val.toFixed(2) : "--",
    },
    {
      title: "延迟",
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
        <Typography.Text type="secondary">运行不存在</Typography.Text>
      </div>
    );
  }

  const isActive = run.status === "running" || run.status === "pending";
  const canRetry =
    !isActive && (run.failed_tasks > 0 || run.status === "cancelled");

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/runs")}
          style={{ padding: 0 }}
        >
          返回运行列表
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
            {run.name || `运行 #${run.id}`}
          </Typography.Title>
          <Space wrap>
            {isActive && (
              <Tag
                color={statusColors[run.status]}
                style={{ fontSize: 14, padding: "4px 12px" }}
              >
                {RUN_STATUS_LABELS[run.status]}
              </Tag>
            )}
            {isActive && (
              <Popconfirm title="取消这个评估运行？" onConfirm={handleCancel}>
                <Button danger icon={<StopOutlined />}>
                  取消运行
                </Button>
              </Popconfirm>
            )}
            {canRetry && (
              <Popconfirm
                title="重跑失败/取消的任务？"
                description="已完成的任务保持不变。"
                onConfirm={handleRetry}
              >
                <Button type="primary" ghost icon={<RedoOutlined />}>
                  重跑失败任务
                </Button>
              </Popconfirm>
            )}
            <Button
              icon={<DownloadOutlined />}
              href={exportRunUrl(run.id)}
              target="_blank"
            >
              导出 CSV
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                fetchRun();
                fetchTasks();
              }}
            >
              刷新
            </Button>
          </Space>
        </div>

        <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="数据集">
            {run.dataset_name || `#${run.dataset_id}`}
          </Descriptions.Item>
          <Descriptions.Item label="模型">
            {run.model_name || `#${run.model_config_id}`}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusColors[run.status] || "default"}>
              {RUN_STATUS_LABELS[run.status] || run.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="进度">
            <Progress
              percent={
                run.total_tasks > 0
                  ? Math.round((run.completed_tasks / run.total_tasks) * 100)
                  : 0
              }
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
          <Descriptions.Item label="任务">
            {run.completed_tasks} / {run.total_tasks} 完成
            {run.failed_tasks > 0 && (
              <Typography.Text type="danger" style={{ marginLeft: 8 }}>
                {run.failed_tasks} 失败
              </Typography.Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="综合得分">
            {run.aggregate_score !== undefined && run.aggregate_score !== null
              ? `${(run.aggregate_score * 100).toFixed(1)}%`
              : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="正确数">
            {run.correct_tasks !== undefined && run.correct_tasks !== null
              ? `${run.correct_tasks} / ${run.total_tasks}`
              : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="平均延迟">
            {run.avg_latency_ms !== undefined && run.avg_latency_ms !== null
              ? `${Math.round(run.avg_latency_ms)}ms`
              : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="Token 总量">
            {run.total_tokens !== undefined && run.total_tokens !== null
              ? run.total_tokens.toLocaleString()
              : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="成本">
            {run.cost_usd !== undefined && run.cost_usd !== null
              ? `$${run.cost_usd.toFixed(4)}`
              : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {run.started_at ? new Date(run.started_at).toLocaleString() : "--"}
          </Descriptions.Item>
          {run.completed_at && (
            <Descriptions.Item label="结束时间">
              {new Date(run.completed_at).toLocaleString()}
            </Descriptions.Item>
          )}
          {run.error_message && (
            <Descriptions.Item label="错误信息" span={3}>
              <Typography.Text type="danger">{run.error_message}</Typography.Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card
        title="任务结果"
        extra={
          <Space>
            <Typography.Text type="secondary">筛选：</Typography.Text>
            <Select
              value={filter}
              onChange={handleFilterChange}
              style={{ width: 140 }}
              options={[
                { label: "全部", value: "all" },
                { label: "正确", value: "correct" },
                { label: "错误", value: "incorrect" },
                { label: "失败", value: "failed" },
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
          expandable={{
            expandedRowRender: (record: TaskResult) => (
              <div style={{ display: "grid", gap: 12 }}>
                {record.status === "completed" && (
                  <Space>
                    <Typography.Text strong>人工复核：</Typography.Text>
                    <Button size="small" onClick={() => handleReview(record.task_id, true)}>
                      判为正确
                    </Button>
                    <Button size="small" danger onClick={() => handleReview(record.task_id, false)}>
                      判为错误
                    </Button>
                    {record.evaluation_details &&
                      (record.evaluation_details as { human_review?: unknown })
                        .human_review !== undefined && (
                        <Tag color="purple">已人工复核</Tag>
                      )}
                  </Space>
                )}
                <div>
                  <Typography.Text strong>题目</Typography.Text>
                  <pre style={expandedBlockStyle}>{record.prompt || "--"}</pre>
                </div>
                {record.trajectory && record.trajectory.length > 0 && (
                  <div>
                    <Typography.Text strong>执行轨迹（{record.trajectory.length} 轮）</Typography.Text>
                    <div style={{ display: "grid", gap: 8, marginTop: 4 }}>
                      {record.trajectory.map((step: TrajectoryStep) => (
                        <div
                          key={step.turn}
                          style={{
                            border: "1px solid #f0f0f0",
                            borderLeft: "3px solid #2a78d6",
                            borderRadius: 4,
                            padding: 8,
                            background: "#fafafa",
                          }}
                        >
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            第 {step.turn} 轮
                          </Typography.Text>
                          <pre style={{ ...expandedBlockStyle, border: "none", background: "transparent", margin: 0, padding: "4px 0" }}>
                            {step.model_output}
                          </pre>
                          {step.action && (
                            <div style={{ fontSize: 12 }}>
                              <Tag color="blue">
                                {step.action.tool}({JSON.stringify(step.action.args)})
                              </Tag>
                            </div>
                          )}
                          {step.observation !== undefined && (
                            <div style={{ fontSize: 12, marginTop: 4 }}>
                              <Typography.Text type="secondary">
                                Observation: {step.observation}
                              </Typography.Text>
                            </div>
                          )}
                          {step.final_answer !== undefined && (
                            <div style={{ marginTop: 4 }}>
                              <Tag color="green">Final Answer</Tag>
                              <Typography.Text>{step.final_answer}</Typography.Text>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {record.reference_answer && (
                  <div>
                    <Typography.Text strong>参考答案 / 评分标准</Typography.Text>
                    <pre style={expandedBlockStyle}>{record.reference_answer}</pre>
                  </div>
                )}
                <div>
                  <Typography.Text strong>模型响应</Typography.Text>
                  <pre style={expandedBlockStyle}>{record.raw_response || "--"}</pre>
                </div>
                {record.parsed_answer && (
                  <div>
                    <Typography.Text strong>解析结果</Typography.Text>
                    <pre style={expandedBlockStyle}>{record.parsed_answer}</pre>
                  </div>
                )}
                {record.evaluation_details &&
                  Object.keys(record.evaluation_details).length > 0 && (
                    <div>
                      <Typography.Text strong>评分细节</Typography.Text>
                      <pre style={expandedBlockStyle}>
                        {JSON.stringify(record.evaluation_details, null, 2)}
                      </pre>
                    </div>
                  )}
              </div>
            ),
          }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: tasksTotal,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条结果`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: "暂无任务结果" }}
        />
      </Card>
    </div>
  );
};

export default RunDetailPage;
