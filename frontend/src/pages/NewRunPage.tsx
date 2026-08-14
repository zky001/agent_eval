import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Form,
  Select,
  Button,
  Card,
  Typography,
  message,
  Spin,
  Input,
  Tag,
  Space,
  Alert,
} from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import { listDatasets } from "../api/datasets";
import { listModels } from "../api/models";
import { createBatchRuns } from "../api/runs";
import { Dataset, ModelConfig, DATASET_TYPE_LABELS } from "../types";

const NewRunPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);

  const datasetIds: number[] = Form.useWatch("dataset_ids", form) ?? [];
  const modelIds: number[] = Form.useWatch("model_config_ids", form) ?? [];
  const totalRuns = datasetIds.length * modelIds.length;

  // 选中的数据集里包含 LLM 裁判类型时，必须指定裁判模型
  const needsJudge = datasets.some(
    (ds) => datasetIds.includes(ds.id) && ds.dataset_type === "llm_judge"
  );

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
        message.error("加载数据失败");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSubmit = async (values: {
    dataset_ids: number[];
    model_config_ids: number[];
    judge_model_config_id?: number;
    params_override?: string;
  }) => {
    setSubmitting(true);
    try {
      let paramsOverride: Record<string, unknown> | undefined;
      if (values.params_override && values.params_override.trim()) {
        try {
          paramsOverride = JSON.parse(values.params_override);
        } catch {
          message.error("参数覆盖不是合法的 JSON");
          setSubmitting(false);
          return;
        }
      }

      const runs = await createBatchRuns({
        dataset_ids: values.dataset_ids,
        model_config_ids: values.model_config_ids,
        judge_model_config_id: values.judge_model_config_id,
        params_override: paramsOverride,
      });

      message.success(`成功创建 ${runs.length} 个评估任务`);

      if (runs.length === 1) {
        navigate(`/runs/${runs[0].id}`);
      } else {
        navigate("/runs");
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || "创建评估任务失败");
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
    <div style={{ maxWidth: 680, margin: "0 auto" }}>
      <Typography.Title level={3}>新建评估任务</Typography.Title>

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          requiredMark="optional"
        >
          <Form.Item
            name="dataset_ids"
            label="数据集（可多选）"
            rules={[{ required: true, message: "请至少选择一个数据集" }]}
          >
            <Select
              mode="multiple"
              placeholder="选择一个或多个数据集"
              showSearch
              optionFilterProp="label"
              options={datasets.map((ds) => ({
                label: `${ds.name}（${DATASET_TYPE_LABELS[ds.dataset_type] || ds.dataset_type}，${ds.total_items} 题）`,
                value: ds.id,
              }))}
              notFoundContent={
                datasets.length === 0 ? "暂无数据集，请先导入" : "无匹配结果"
              }
            />
          </Form.Item>

          <Form.Item
            name="model_config_ids"
            label="被评估模型（可多选）"
            rules={[{ required: true, message: "请至少选择一个模型" }]}
          >
            <Select
              mode="multiple"
              placeholder="选择一个或多个模型"
              showSearch
              optionFilterProp="label"
              options={models.map((m) => ({
                label: `${m.name} (${m.provider} / ${m.model_id})`,
                value: m.id,
              }))}
              notFoundContent={
                models.length === 0 ? "暂无模型配置，请先添加" : "无匹配结果"
              }
            />
          </Form.Item>

          {needsJudge && (
            <>
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
                message="所选数据集包含「LLM 裁判评分」类型，需要指定一个裁判模型来给回答打分。建议使用能力较强的模型作裁判。"
              />
              <Form.Item
                name="judge_model_config_id"
                label="裁判模型"
                rules={[{ required: true, message: "请选择裁判模型" }]}
              >
                <Select
                  placeholder="选择用于打分的裁判模型"
                  showSearch
                  optionFilterProp="label"
                  options={models.map((m) => ({
                    label: `${m.name} (${m.provider} / ${m.model_id})`,
                    value: m.id,
                  }))}
                />
              </Form.Item>
            </>
          )}

          {totalRuns > 0 && (
            <Form.Item>
              <Space wrap>
                <Tag color="blue">
                  将创建 <strong>{totalRuns}</strong> 个评估任务
                  （{datasetIds.length} 个数据集 × {modelIds.length} 个模型）
                </Tag>
              </Space>
            </Form.Item>
          )}

          <Form.Item
            name="params_override"
            label="参数覆盖（JSON，可选）"
            help='覆盖所有任务的默认模型参数，例如 {"temperature": 0, "max_tokens": 512}。也支持 "system"（系统提示词）和 "timeout"（超时秒数）。'
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
              rows={3}
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
              disabled={totalRuns === 0}
            >
              {totalRuns > 1 ? `批量启动 ${totalRuns} 个评估任务` : "启动评估"}
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default NewRunPage;
