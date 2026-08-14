import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Card,
  Table,
  Tag,
  Typography,
  Spin,
  message,
  Button,
  Space,
  Statistic,
  Row,
  Col,
  Tooltip,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
} from "@ant-design/icons";
import { compareRuns } from "../api/runs";
import { CompareData, CompareItem } from "../types";

const RunComparePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<CompareData | null>(null);

  const ids = useMemo(
    () =>
      (searchParams.get("ids") || "")
        .split(",")
        .map((x) => Number(x.trim()))
        .filter((x) => Number.isFinite(x) && x > 0),
    [searchParams]
  );

  useEffect(() => {
    const fetch = async () => {
      if (ids.length < 2) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const result = await compareRuns(ids);
        setData(result);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        message.error(error.response?.data?.detail || "加载对比数据失败");
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [ids]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (ids.length < 2 || !data) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Typography.Text type="secondary">
          请从「评估运行」列表勾选 2-4 个同数据集的运行后点击「对比所选」。
        </Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button onClick={() => navigate("/runs")}>返回运行列表</Button>
        </div>
      </div>
    );
  }

  const runLabel = (runId: number) => {
    const run = data.runs.find((r) => r.id === runId);
    return run?.model_name || run?.name || `运行 #${runId}`;
  };

  const renderResultCell = (item: CompareItem, runId: number) => {
    const res = item.results[String(runId)];
    if (!res) return <Typography.Text type="secondary">--</Typography.Text>;
    const icon =
      res.is_correct === true ? (
        <CheckCircleFilled style={{ color: "#52c41a" }} />
      ) : res.is_correct === false ? (
        <CloseCircleFilled style={{ color: "#ff4d4f" }} />
      ) : (
        <Tag>{res.status}</Tag>
      );
    const text = res.parsed_answer || res.raw_response || "";
    return (
      <Space align="start">
        {icon}
        <Tooltip
          title={
            <div style={{ whiteSpace: "pre-wrap", maxHeight: 320, overflow: "auto" }}>
              {res.raw_response || "(无响应)"}
            </div>
          }
          overlayStyle={{ maxWidth: 480 }}
        >
          <span>
            {text.length > 60 ? text.substring(0, 60) + "..." : text || "--"}
            {res.score !== undefined && res.score !== null && (
              <Typography.Text type="secondary"> ({(res.score * 100).toFixed(0)}%)</Typography.Text>
            )}
          </span>
        </Tooltip>
      </Space>
    );
  };

  const columns = [
    {
      title: "#",
      dataIndex: "item_index",
      key: "item_index",
      width: 50,
      fixed: "left" as const,
    },
    {
      title: "题目",
      dataIndex: "prompt",
      key: "prompt",
      width: 260,
      render: (text: string) => (
        <Tooltip
          title={<div style={{ whiteSpace: "pre-wrap", maxHeight: 320, overflow: "auto" }}>{text}</div>}
          overlayStyle={{ maxWidth: 480 }}
        >
          <span>{text.length > 80 ? text.substring(0, 80) + "..." : text}</span>
        </Tooltip>
      ),
    },
    ...data.runs.map((run) => ({
      title: runLabel(run.id),
      key: `run-${run.id}`,
      render: (_: unknown, item: CompareItem) => renderResultCell(item, run.id),
    })),
  ];

  // 仅在部分运行答对时高亮该行（分歧行最值得看）
  const divergentRows = new Set(
    data.items
      .filter((item) => {
        const verdicts = data.runs
          .map((r) => item.results[String(r.id)]?.is_correct)
          .filter((v) => v !== undefined && v !== null);
        return verdicts.length >= 2 && new Set(verdicts).size > 1;
      })
      .map((i) => i.item_index)
  );

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

      <Typography.Title level={3}>
        运行对比：{data.runs[0]?.dataset_name || "同一数据集"}
      </Typography.Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {data.runs.map((run) => (
          <Col xs={24} sm={12} md={6} key={run.id}>
            <Card hoverable onClick={() => navigate(`/runs/${run.id}`)}>
              <Statistic
                title={
                  <span>
                    {run.model_name || `运行 #${run.id}`}
                    <Typography.Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                      #{run.id}
                    </Typography.Text>
                  </span>
                }
                value={
                  run.aggregate_score !== undefined && run.aggregate_score !== null
                    ? (run.aggregate_score * 100).toFixed(1)
                    : "--"
                }
                suffix="%"
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card
        title="逐题对比"
        extra={
          <Typography.Text type="secondary">
            高亮行 = 模型间结果不一致（{divergentRows.size} 行）
          </Typography.Text>
        }
      >
        <Table
          dataSource={data.items}
          columns={columns}
          rowKey="item_index"
          scroll={{ x: 900 }}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 题` }}
          rowClassName={(item) =>
            divergentRows.has(item.item_index) ? "compare-divergent-row" : ""
          }
        />
        <style>{`.compare-divergent-row td { background: #fffbe6 !important; }`}</style>
      </Card>
    </div>
  );
};

export default RunComparePage;
