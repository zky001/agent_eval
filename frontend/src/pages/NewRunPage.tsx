import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Form,
  Input,
  Select,
  Button,
  Card,
  Typography,
  message,
  Spin,
} from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import { listDatasets } from "../api/datasets";
import { listModels } from "../api/models";
import { createRun } from "../api/runs";
import { Dataset, ModelConfig } from "../types";

const NewRunPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [ds, ms] = await Promise.all([
          listDatasets().catch(() => []),
          listModels().catch(() => []),
        ]);
        setDatasets(ds);
        setModels(ms);
      } catch {
        message.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSubmit = async (values: {
    dataset_id: number;
    model_config_id: number;
    name?: string;
    params_override?: string;
  }) => {
    setSubmitting(true);
    try {
      let paramsOverride: Record<string, unknown> | undefined;
      if (values.params_override && values.params_override.trim()) {
        try {
          paramsOverride = JSON.parse(values.params_override);
        } catch {
          message.error("Invalid JSON in parameters override");
          setSubmitting(false);
          return;
        }
      }

      const run = await createRun({
        dataset_id: values.dataset_id,
        model_config_id: values.model_config_id,
        name: values.name || undefined,
        params_override: paramsOverride,
      });

      message.success("Evaluation run created");
      navigate(`/runs/${run.id}`);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(
        error.response?.data?.detail || "Failed to create evaluation run"
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 600, margin: "0 auto" }}>
      <Typography.Title level={3}>New Evaluation Run</Typography.Title>

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          requiredMark="optional"
        >
          <Form.Item
            name="name"
            label="Run Name"
            help="Optional. A descriptive name for this evaluation run."
          >
            <Input placeholder="e.g., GPT-4 on GSM8K test" />
          </Form.Item>

          <Form.Item
            name="dataset_id"
            label="Dataset"
            rules={[{ required: true, message: "Please select a dataset" }]}
          >
            <Select
              placeholder="Select a dataset"
              showSearch
              optionFilterProp="label"
              options={datasets.map((ds) => ({
                label: `${ds.name} (${ds.total_items} items)`,
                value: ds.id,
              }))}
              notFoundContent={
                datasets.length === 0
                  ? "No datasets available. Import one first."
                  : "No matches found"
              }
            />
          </Form.Item>

          <Form.Item
            name="model_config_id"
            label="Model"
            rules={[{ required: true, message: "Please select a model" }]}
          >
            <Select
              placeholder="Select a model"
              showSearch
              optionFilterProp="label"
              options={models.map((m) => ({
                label: `${m.name} (${m.provider} / ${m.model_id})`,
                value: m.id,
              }))}
              notFoundContent={
                models.length === 0
                  ? "No models configured. Add one first."
                  : "No matches found"
              }
            />
          </Form.Item>

          <Form.Item
            name="params_override"
            label="Parameters Override (JSON)"
            help="Optional. Override default model parameters for this run."
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
              placeholder='{"temperature": 0, "max_tokens": 512}'
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              icon={<ThunderboltOutlined />}
              size="large"
              block
            >
              Start Evaluation
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default NewRunPage;
