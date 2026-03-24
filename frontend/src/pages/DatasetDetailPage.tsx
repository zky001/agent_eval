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
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { getDataset, getDatasetItems } from "../api/datasets";
import { Dataset, DatasetItem } from "../types";

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
        message.error("Failed to load dataset");
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
        message.error("Failed to load dataset items");
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
      title: "Prompt",
      dataIndex: "prompt",
      key: "prompt",
      render: (text: string, record: DatasetItem) => {
        const isExpanded = expandedRows.has(record.id);
        if (!text) return "--";
        if (text.length <= 100) return text;
        return (
          <div>
            <span>{isExpanded ? text : text.substring(0, 100) + "..."}</span>
            <Button
              type="link"
              size="small"
              onClick={() => toggleExpand(record.id)}
              style={{ padding: "0 4px" }}
            >
              {isExpanded ? "Show less" : "Show more"}
            </Button>
          </div>
        );
      },
    },
    {
      title: "Reference Answer",
      dataIndex: "reference_answer",
      key: "reference_answer",
      width: 300,
      render: (text: string) => {
        if (!text) return "--";
        if (text.length <= 80) return text;
        return (
          <Tooltip title={text}>
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
        <Typography.Text type="secondary">Dataset not found</Typography.Text>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/datasets")}
          style={{ padding: 0 }}
        >
          Back to Datasets
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
          <Descriptions.Item label="Type">{dataset.dataset_type || "--"}</Descriptions.Item>
          <Descriptions.Item label="Total Items">{dataset.total_items}</Descriptions.Item>
          <Descriptions.Item label="Created">
            {dataset.created_at ? new Date(dataset.created_at).toLocaleString() : "--"}
          </Descriptions.Item>
          <Descriptions.Item label="Description" span={3}>
            {dataset.description || "No description"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Dataset Items">
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
            showTotal: (t) => `Total ${t} items`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: "No items in this dataset" }}
        />
      </Card>
    </div>
  );
};

export default DatasetDetailPage;
