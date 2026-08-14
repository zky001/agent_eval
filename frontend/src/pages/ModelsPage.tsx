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
      message.error("加载模型列表失败");
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
        // 接口只返回掩码后的 Key；不能把掩码回填进表单，
        // 否则保存时会用掩码覆盖真实 Key
        api_key: "",
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
          message.error("默认参数不是合法的 JSON");
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
        message.success("模型更新成功");
      } else {
        await createModel(payload);
        message.success("模型创建成功");
      }

      closeDrawer();
      fetchModels();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(
        error.response?.data?.detail ||
          (editingModel ? "模型更新失败" : "模型创建失败")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteModel(String(id));
      message.success("模型已删除");
      fetchModels();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "删除失败");
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
      message.error(error.response?.data?.detail || "连通性测试失败");
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
      title: "名称",
      dataIndex: "name",
      key: "name",
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: "提供商",
      dataIndex: "provider",
      key: "provider",
      render: (text: string) => (
        <Tag color={providerColors[text] || "default"}>
          {text.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: "模型 ID",
      dataIndex: "model_id",
      key: "model_id",
      render: (text: string) => <code>{text}</code>,
    },
    {
      title: "API Key",
      dataIndex: "api_key",
      key: "api_key",
      render: (text: string | undefined) =>
        text ? <code>{text}</code> : <Tag>未配置</Tag>,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) =>
        text ? new Date(text).toLocaleDateString() : "--",
    },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: ModelConfig) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openDrawer(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            icon={<ExperimentOutlined />}
            onClick={() => handleTest(record)}
          >
            测试
          </Button>
          <Popconfirm
            title="删除这个模型？"
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
          模型管理
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => openDrawer()}
        >
          添加模型
        </Button>
      </div>

      <Card>
        <Table
          dataSource={models}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{
            emptyText: "还没有配置模型，点击右上角添加。",
          }}
        />
      </Card>

      <Drawer
        title={editingModel ? "编辑模型" : "添加模型"}
        placement="right"
        width={480}
        onClose={closeDrawer}
        open={drawerOpen}
        extra={
          <Space>
            <Button onClick={closeDrawer}>取消</Button>
            <Button type="primary" loading={submitting} onClick={() => form.submit()}>
              {editingModel ? "更新" : "创建"}
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
            label="名称"
            rules={[{ required: true, message: "请输入模型名称" }]}
          >
            <Input placeholder="例如：GPT-4o" />
          </Form.Item>

          <Form.Item
            name="provider"
            label="提供商"
            rules={[{ required: true, message: "请选择提供商" }]}
          >
            <Select placeholder="选择提供商">
              <Select.Option value="openai">OpenAI（及兼容接口）</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="local">本地 / 自定义端点</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="model_id"
            label="模型 ID"
            rules={[{ required: true, message: "请输入模型 ID" }]}
          >
            <Input placeholder="例如：gpt-4o、claude-sonnet-4-5" />
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API Key"
            extra={
              editingModel?.api_key
                ? `当前已配置 (${editingModel.api_key})，留空则保持不变`
                : undefined
            }
          >
            <Input.Password
              placeholder={
                editingModel?.api_key ? "留空保持现有 API Key" : "输入 API Key"
              }
            />
          </Form.Item>

          <Form.Item
            name="api_base_url"
            label="API Base URL（可选）"
            help="留空使用官方地址；OpenAI 兼容接口、代理或本地服务在此填写"
          >
            <Input placeholder="例如：http://localhost:11434/v1" />
          </Form.Item>

          <Form.Item
            name="default_params"
            label="默认参数（JSON）"
            rules={[
              {
                validator: (_, value) => {
                  if (!value || !value.trim()) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(new Error("请输入合法的 JSON"));
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
        title="模型连通性测试"
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
            关闭
          </Button>,
        ]}
        width={600}
      >
        {testing ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>
              <Typography.Text type="secondary">
                正在发送测试请求...
              </Typography.Text>
            </div>
          </div>
        ) : testResult ? (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="状态">
              <Tag color={testResult.success ? "success" : "error"}>
                {testResult.success ? "成功" : "失败"}
              </Tag>
            </Descriptions.Item>
            {testResult.response && (
              <Descriptions.Item label="响应">
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
              <Descriptions.Item label="错误">
                <Typography.Text type="danger">{testResult.error}</Typography.Text>
              </Descriptions.Item>
            )}
            {testResult.latency_ms && (
              <Descriptions.Item label="延迟">
                {testResult.latency_ms}ms
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">暂无结果</Typography.Text>
        )}
      </Modal>
    </div>
  );
};

export default ModelsPage;
