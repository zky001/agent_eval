import React, { useEffect, useState } from "react";
import {
  Table,
  Button,
  Space,
  Drawer,
  Form,
  Input,
  Select,
  message,
  Popconfirm,
  Typography,
  Card,
  Modal,
  Spin,
  Descriptions,
  Tag,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";
import { listModels, createModel, updateModel, deleteModel, testModel } from "../api/models";
import { ModelConfig } from "../types";

const ModelsPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; response?: string; error?: string; latency_ms?: number } | null>(null);
  const [testing, setTesting] = useState(false);
  const [form] = Form.useForm();
  const [selectedProvider, setSelectedProvider] = useState<string>("");

  const fetchModels = async () => {
    setLoading(true);
    try {
      const data = await listModels();
      setModels(data);
    } catch {
      message.error("Failed to load models");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const openDrawer = (model?: ModelConfig) => {
    if (model) {
      setEditingModel(model);
      setSelectedProvider(model.provider);
      form.setFieldsValue({
        name: model.name,
        provider: model.provider,
        model_id: model.model_id,
        api_key: model.api_key || "",
        api_base_url: model.api_base_url || "",
        default_params: model.default_params
          ? JSON.stringify(model.default_params, null, 2)
          : "",
      });
    } else {
      setEditingModel(null);
      setSelectedProvider("");
      form.resetFields();
    }
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditingModel(null);
    setSelectedProvider("");
    form.resetFields();
  };

  const handleSubmit = async (values: {
    name: string;
    provider: string;
    model_id: string;
    api_key?: string;
    api_base_url?: string;
    default_params?: string;
  }) => {
    setSubmitting(true);
    try {
      let defaultParams: Record<string, unknown> | undefined;
      if (values.default_params && values.default_params.trim()) {
        try {
          defaultParams = JSON.parse(values.default_params);
        } catch {
          message.error("Invalid JSON in default parameters");
          setSubmitting(false);
          return;
        }
      }

      const payload = {
        name: values.name,
        provider: values.provider,
        model_id: values.model_id,
        api_key: values.api_key || undefined,
        api_base_url: values.api_base_url || undefined,
        default_params: defaultParams,
      };

      if (editingModel) {
        await updateModel(String(editingModel.id), payload);
        message.success("Model updated successfully");
      } else {
        await createModel(payload);
        message.success("Model created successfully");
      }

      closeDrawer();
      fetchModels();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(
        error.response?.data?.detail ||
          `Failed to ${editingModel ? "update" : "create"} model`
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteModel(String(id));
      message.success("Model deleted");
      fetchModels();
    } catch {
      message.error("Failed to delete model");
    }
  };

  const handleTest = async (model: ModelConfig) => {
    setTesting(true);
    setTestResult(null);
    setTestModalOpen(true);
    try {
      const result = await testModel(String(model.id));
      setTestResult(result);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "Model test failed");
      setTestModalOpen(false);
    } finally {
      setTesting(false);
    }
  };

  const providerColors: Record<string, string> = {
    openai: "green",
    anthropic: "blue",
    local: "orange",
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: "Provider",
      dataIndex: "provider",
      key: "provider",
      render: (text: string) => (
        <Tag color={providerColors[text] || "default"}>
          {text.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: "Model ID",
      dataIndex: "model_id",
      key: "model_id",
      render: (text: string) => <code>{text}</code>,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) =>
        text ? new Date(text).toLocaleDateString() : "--",
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: ModelConfig) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openDrawer(record)}
          >
            Edit
          </Button>
          <Button
            type="link"
            icon={<ExperimentOutlined />}
            onClick={() => handleTest(record)}
          >
            Test
          </Button>
          <Popconfirm
            title="Delete this model?"
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
          Models
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => openDrawer()}
        >
          Add Model
        </Button>
      </div>

      <Card>
        <Table
          dataSource={models}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{
            emptyText: "No models configured yet. Add one to get started.",
          }}
        />
      </Card>

      <Drawer
        title={editingModel ? "Edit Model" : "Add Model"}
        placement="right"
        width={480}
        onClose={closeDrawer}
        open={drawerOpen}
        extra={
          <Space>
            <Button onClick={closeDrawer}>Cancel</Button>
            <Button type="primary" loading={submitting} onClick={() => form.submit()}>
              {editingModel ? "Update" : "Create"}
            </Button>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          onValuesChange={(changed) => {
            if (changed.provider !== undefined) {
              setSelectedProvider(changed.provider);
            }
          }}
        >
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: "Please enter a model name" }]}
          >
            <Input placeholder="e.g., GPT-4 Turbo" />
          </Form.Item>

          <Form.Item
            name="provider"
            label="Provider"
            rules={[{ required: true, message: "Please select a provider" }]}
          >
            <Select placeholder="Select provider">
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="local">Local</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="model_id"
            label="Model ID"
            rules={[{ required: true, message: "Please enter the model ID" }]}
          >
            <Input placeholder="e.g., gpt-4-turbo, claude-3-opus-20240229" />
          </Form.Item>

          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="Enter API key" />
          </Form.Item>

          {(selectedProvider === "local" || selectedProvider === "") && (
            <Form.Item name="api_base_url" label="API Base URL">
              <Input placeholder="e.g., http://localhost:11434/v1" />
            </Form.Item>
          )}

          <Form.Item
            name="default_params"
            label="Default Parameters (JSON)"
            rules={[
              {
                validator: (_, value) => {
                  if (!value || !value.trim()) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(
                      new Error("Please enter valid JSON")
                    );
                  }
                },
              },
            ]}
          >
            <Input.TextArea
              rows={4}
              placeholder='{"temperature": 0.7, "max_tokens": 1024}'
            />
          </Form.Item>
        </Form>
      </Drawer>

      <Modal
        title="Model Test Result"
        open={testModalOpen}
        onCancel={() => {
          setTestModalOpen(false);
          setTestResult(null);
        }}
        footer={[
          <Button
            key="close"
            onClick={() => {
              setTestModalOpen(false);
              setTestResult(null);
            }}
          >
            Close
          </Button>,
        ]}
        width={600}
      >
        {testing ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>
              <Typography.Text type="secondary">
                Sending test request...
              </Typography.Text>
            </div>
          </div>
        ) : testResult ? (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="Status">
              <Tag color={testResult.success ? "success" : "error"}>
                {testResult.success ? "SUCCESS" : "FAILED"}
              </Tag>
            </Descriptions.Item>
            {testResult.response && (
              <Descriptions.Item label="Response">
                <div
                  style={{
                    maxHeight: 300,
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {testResult.response}
                </div>
              </Descriptions.Item>
            )}
            {testResult.error && (
              <Descriptions.Item label="Error">
                <Typography.Text type="danger">{testResult.error}</Typography.Text>
              </Descriptions.Item>
            )}
            {testResult.latency_ms && (
              <Descriptions.Item label="Latency">
                {testResult.latency_ms}ms
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">No result</Typography.Text>
        )}
      </Modal>
    </div>
  );
};

export default ModelsPage;
