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
  message,
  Spin,
  Popconfirm,
  Typography,
  Card,
} from "antd";
import { PlusOutlined, UploadOutlined, DeleteOutlined, EyeOutlined } from "@ant-design/icons";
import { listDatasets, importDataset, uploadDataset, deleteDataset } from "../api/datasets";
import { Dataset } from "../types";

const DatasetsPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [importForm] = Form.useForm();
  const [uploadForm] = Form.useForm();

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const data = await listDatasets();
      setDatasets(data);
    } catch {
      message.error("Failed to load datasets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleImport = async (values: { source: string; split?: string; max_items?: number }) => {
    setSubmitting(true);
    try {
      await importDataset(values);
      message.success("Dataset imported successfully");
      setImportModalOpen(false);
      importForm.resetFields();
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "Failed to import dataset");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpload = async (values: { json_data: string }) => {
    setSubmitting(true);
    try {
      const parsed = JSON.parse(values.json_data);
      await uploadDataset(parsed);
      message.success("Dataset uploaded successfully");
      setUploadModalOpen(false);
      uploadForm.resetFields();
      fetchDatasets();
    } catch (err: unknown) {
      if (err instanceof SyntaxError) {
        message.error("Invalid JSON format");
      } else {
        const error = err as { response?: { data?: { detail?: string } } };
        message.error(error.response?.data?.detail || "Failed to upload dataset");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDataset(id);
      message.success("Dataset deleted");
      fetchDatasets();
    } catch {
      message.error("Failed to delete dataset");
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: Dataset) => (
        <a onClick={() => navigate(`/datasets/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: "Type",
      dataIndex: "dataset_type",
      key: "dataset_type",
    },
    {
      title: "Items",
      dataIndex: "total_items",
      key: "total_items",
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? new Date(text).toLocaleDateString() : "--"),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: Dataset) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/datasets/${record.id}`)}
          >
            View
          </Button>
          <Popconfirm
            title="Delete this dataset?"
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
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Datasets
        </Typography.Title>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setImportModalOpen(true)}
          >
            Import Dataset
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>
            Upload Custom
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={datasets}
          columns={columns}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: "No datasets yet. Import or upload one to get started." }}
        />
      </Card>

      <Modal
        title="Import Dataset"
        open={importModalOpen}
        onCancel={() => {
          setImportModalOpen(false);
          importForm.resetFields();
        }}
        footer={null}
      >
        <Form form={importForm} layout="vertical" onFinish={handleImport}>
          <Form.Item
            name="source"
            label="Source"
            rules={[{ required: true, message: "Please select a source" }]}
          >
            <Select placeholder="Select dataset source">
              <Select.Option value="gsm8k">GSM8K</Select.Option>
              <Select.Option value="mmlu">MMLU</Select.Option>
              <Select.Option value="humaneval">HumanEval</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="split" label="Split">
            <Input placeholder="e.g., test, train, validation" />
          </Form.Item>
          <Form.Item name="max_items" label="Max Items">
            <InputNumber min={1} max={10000} style={{ width: "100%" }} placeholder="Leave empty for all" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                Import
              </Button>
              <Button
                onClick={() => {
                  setImportModalOpen(false);
                  importForm.resetFields();
                }}
              >
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Upload Custom Dataset"
        open={uploadModalOpen}
        onCancel={() => {
          setUploadModalOpen(false);
          uploadForm.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form form={uploadForm} layout="vertical" onFinish={handleUpload}>
          <Form.Item
            name="json_data"
            label="JSON Data"
            rules={[{ required: true, message: "Please enter JSON data" }]}
            help='Format: {"name": "My Dataset", "type": "custom", "items": [{"prompt": "...", "reference_answer": "..."}]}'
          >
            <Input.TextArea
              rows={12}
              placeholder='{"name": "My Dataset", "type": "custom", "items": [{"prompt": "What is 2+2?", "reference_answer": "4"}]}'
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                Upload
              </Button>
              <Button
                onClick={() => {
                  setUploadModalOpen(false);
                  uploadForm.resetFields();
                }}
              >
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DatasetsPage;
