import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Radio,
  message,
  Popconfirm,
  Typography,
  Card,
  Tag,
} from "antd";
import { PlusOutlined, UploadOutlined, DeleteOutlined, EyeOutlined } from "@ant-design/icons";
import { listDatasets, importDataset, uploadDataset, deleteDataset } from "../api/datasets";
import { Dataset, DATASET_TYPE_LABELS } from "../types";

// gsm8k / mmlu / humaneval 支持从 HuggingFace 拉取真实数据
const HF_SOURCES = new Set(["gsm8k", "mmlu", "humaneval"]);

const SOURCE_OPTIONS = [
  "tool_use",
  "multi_step",
  "react",
  "instruction_following",
  "api_interaction",
  "error_recovery",
  "gsm8k",
  "mmlu",
  "humaneval",
  "llm_judge",
];

const DatasetsPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [importForm] = Form.useForm();
  const [uploadForm] = Form.useForm();
  const selectedSource: string | undefined = Form.useWatch("source", importForm);
  const selectedOrigin: string = Form.useWatch("origin", importForm) ?? "sample";

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const data = await listDatasets();
      setDatasets(data);
    } catch {
      message.error("加载数据集失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleImport = async (values: {
    source: string;
    origin?: "sample" | "huggingface";
    max_items?: number;
  }) => {
    setSubmitting(true);
    try {
      await importDataset(values);
      message.success("数据集导入成功");
      setImportModalOpen(false);
      importForm.resetFields();
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "数据集导入失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpload = async (values: {
    name: string;
    dataset_type?: string;
    system_prompt?: string;
    json_items: string;
  }) => {
    setSubmitting(true);
    try {
      let items: unknown;
      try {
        items = JSON.parse(values.json_items);
      } catch {
        message.error("题目列表不是合法的 JSON");
        return;
      }
      if (!Array.isArray(items) || items.length === 0) {
        message.error("题目列表必须是非空的 JSON 数组");
        return;
      }
      await uploadDataset({
        name: values.name,
        dataset_type: values.dataset_type || "custom",
        system_prompt: values.system_prompt || undefined,
        items: items as { prompt: string; reference_answer?: string }[],
      });
      message.success("数据集上传成功");
      setUploadModalOpen(false);
      uploadForm.resetFields();
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "数据集上传失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDataset(id);
      message.success("数据集已删除");
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "删除失败");
    }
  };

  const columns = [
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: Dataset) => (
        <a onClick={() => navigate(`/datasets/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: "类型",
      dataIndex: "dataset_type",
      key: "dataset_type",
      render: (type: string) => (
        <Tag>{DATASET_TYPE_LABELS[type] || type}</Tag>
      ),
    },
    {
      title: "题目数",
      dataIndex: "total_items",
      key: "total_items",
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? new Date(text).toLocaleDateString() : "--"),
    },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: Dataset) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/datasets/${record.id}`)}
          >
            查看
          </Button>
          <Popconfirm
            title="删除这个数据集？"
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
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          数据集
        </Typography.Title>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setImportModalOpen(true)}
          >
            导入数据集
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>
            上传自定义
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={datasets}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: "还没有数据集，先导入或上传一个。" }}
        />
      </Card>

      <Modal
        title="导入数据集"
        open={importModalOpen}
        onCancel={() => {
          setImportModalOpen(false);
          importForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={importForm}
          layout="vertical"
          onFinish={handleImport}
          initialValues={{ origin: "sample" }}
        >
          <Form.Item
            name="source"
            label="评估类型"
            rules={[{ required: true, message: "请选择评估类型" }]}
          >
            <Select
              placeholder="选择评估类型"
              options={SOURCE_OPTIONS.map((s) => ({
                value: s,
                label: DATASET_TYPE_LABELS[s] || s,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="origin"
            label="数据来源"
            help={
              selectedSource && !HF_SOURCES.has(selectedSource)
                ? "该类型仅提供内置示例数据"
                : "HuggingFace 导入真实基准数据（需要网络）"
            }
          >
            <Radio.Group>
              <Radio.Button value="sample">内置示例</Radio.Button>
              <Radio.Button
                value="huggingface"
                disabled={!selectedSource || !HF_SOURCES.has(selectedSource)}
              >
                HuggingFace 真实数据
              </Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item
            name="max_items"
            label="最大题目数"
            help={selectedOrigin === "huggingface" ? "默认 50，最多 500" : "留空导入全部示例"}
          >
            <InputNumber min={1} max={500} style={{ width: "100%" }} placeholder="留空使用默认值" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                导入
              </Button>
              <Button
                onClick={() => {
                  setImportModalOpen(false);
                  importForm.resetFields();
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="上传自定义数据集"
        open={uploadModalOpen}
        onCancel={() => {
          setUploadModalOpen(false);
          uploadForm.resetFields();
        }}
        footer={null}
        width={640}
      >
        <Form form={uploadForm} layout="vertical" onFinish={handleUpload}>
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input placeholder="例如：客服问答-v1" />
          </Form.Item>
          <Form.Item name="dataset_type" label="评估类型" initialValue="custom">
            <Select
              options={[
                { value: "custom", label: "自定义（精确/包含匹配）" },
                { value: "llm_judge", label: "LLM 裁判评分（参考答案填评分标准）" },
                ...SOURCE_OPTIONS.filter((s) => s !== "llm_judge").map((s) => ({
                  value: s,
                  label: DATASET_TYPE_LABELS[s] || s,
                })),
              ]}
            />
          </Form.Item>
          <Form.Item
            name="system_prompt"
            label="系统提示词（可选）"
            help="将作为 system prompt 应用到该数据集的所有评估请求"
          >
            <Input.TextArea rows={2} placeholder="例如：你是一个严谨的助手，只输出 JSON。" />
          </Form.Item>
          <Form.Item
            name="json_items"
            label="题目列表（JSON 数组）"
            rules={[{ required: true, message: "请输入题目列表" }]}
            help='每个元素形如 {"prompt": "问题", "reference_answer": "参考答案", "metadata": {}}'
          >
            <Input.TextArea
              rows={10}
              placeholder='[{"prompt": "2+2 等于几？", "reference_answer": "4"}]'
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                上传
              </Button>
              <Button
                onClick={() => {
                  setUploadModalOpen(false);
                  uploadForm.resetFields();
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DatasetsPage;
