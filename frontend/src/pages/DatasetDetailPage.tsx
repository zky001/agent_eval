import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card,
  Table,
  Typography,
  Descriptions,
  Spin,
  message,
  Button,
  Tooltip,
  Tag,
} from "antd";
import { ArrowLeftOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { getDataset, getDatasetItems } from "../api/datasets";
import { Dataset, DatasetItem, DATASET_TYPE_LABELS } from "../types";

const DatasetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [items, setItems] = useState<DatasetItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!id) return;
    const fetchDataset = async () => {
      setLoading(true);
      try {
        const ds = await getDataset(Number(id));
        setDataset(ds);
        setTotal(ds.total_items);
      } catch {
        message.error("加载数据集失败");
      } finally {
        setLoading(false);
      }
    };
    fetchDataset();
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const fetchItems = async () => {
      setItemsLoading(true);
      try {
        const skip = (page - 1) * pageSize;
        const result = await getDatasetItems(Number(id), skip, pageSize);
        setItems(result);
      } catch {
        message.error("加载题目失败");
      } finally {
        setItemsLoading(false);
      }
    };
    fetchItems();
  }, [id, page, pageSize]);

  const toggleExpand = (itemId: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
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
      render: (text: string, record: DatasetItem) => {
        const isExpanded = expandedRows.has(record.id);
        if (!text) return "--";
        if (text.length <= 100) return <span style={{ whiteSpace: "pre-wrap" }}>{text}</span>;
        return (
          <div>
            <span style={{ whiteSpace: "pre-wrap" }}>
              {isExpanded ? text : text.substring(0, 100) + "..."}
            </span>
            <Button
              type="link"
              size="small"
              onClick={() => toggleExpand(record.id)}
              style={{ padding: "0 4px" }}
            >
              {isExpanded ? "收起" : "展开"}
            </Button>
          </div>
        );
      },
    },
    {
      title: "参考答案",
      dataIndex: "reference_answer",
      key: "reference_answer",
      width: 300,
      render: (text: string) => {
        if (!text) return "--";
        if (text.length <= 80) return text;
        return (
          <Tooltip title={<div style={{ whiteSpace: "pre-wrap" }}>{text}</div>}>
            <span>{text.substring(0, 80)}...</span>
          </Tooltip>
        );
      },
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!dataset) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Typography.Text type="secondary">数据集不存在</Typography.Text>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between" }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/datasets")}
          style={{ padding: 0 }}
        >
          返回数据集列表
        </Button>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={() => navigate("/runs/new")}
        >
          用此数据集评估
        </Button>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions
          title={
            <Typography.Title level={4} style={{ margin: 0 }}>
              {dataset.name}
            </Typography.Title>
          }
          bordered
          column={{ xs: 1, sm: 2, md: 3 }}
        >
          <Descriptions.Item label="类型">
            <Tag>{DATASET_TYPE_LABELS[dataset.dataset_type] || dataset.dataset_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="题目数">{dataset.total_items}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {dataset.created_at ? new Date(dataset.created_at).toLocaleString() : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={3}>
            {dataset.description || "无描述"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="题目列表">
        <Table
          dataSource={items}
          columns={columns}
          rowKey="id"
          loading={itemsLoading}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 题`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: "该数据集没有题目" }}
        />
      </Card>
    </div>
  );
};

export default DatasetDetailPage;
