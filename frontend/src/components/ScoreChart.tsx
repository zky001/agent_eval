import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Typography } from "antd";
import { LeaderboardEntry } from "../types";

// Validated categorical palette (fixed slot order — never cycled or re-ranked).
const SERIES_COLORS = [
  "#2a78d6",
  "#eb6834",
  "#1baf7a",
  "#eda100",
  "#e87ba4",
  "#008300",
  "#4a3aa7",
  "#e34948",
];
const MAX_SERIES = SERIES_COLORS.length;

const TEXT_SECONDARY = "#52514e";

interface ScoreChartProps {
  entries: LeaderboardEntry[];
  /** 完整模型名列表（按名称排序）。颜色跟随模型本身，
   *  这样筛选数据集时同一模型不会“换色”。 */
  colorDomain?: string[];
  /** 条数不多时在柱顶显示数值（低对比色的补救标签） */
  showValueLabels?: boolean;
  height?: number;
}

const ScoreChart: React.FC<ScoreChartProps> = ({
  entries,
  colorDomain,
  showValueLabels = false,
  height = 320,
}) => {
  if (entries.length === 0) return null;

  const domain = (
    colorDomain && colorDomain.length > 0
      ? [...colorDomain]
      : [...new Set(entries.map((e) => e.model_name))]
  ).sort((a, b) => a.localeCompare(b));

  const presentModels = domain.filter((m) =>
    entries.some((e) => e.model_name === m)
  );
  const shownModels = presentModels.slice(0, MAX_SERIES);
  const hiddenCount = presentModels.length - shownModels.length;

  const colorOf = (model: string) =>
    SERIES_COLORS[domain.indexOf(model) % MAX_SERIES];

  const datasets = [...new Set(entries.map((e) => e.dataset_name))];
  const data = datasets.map((ds) => {
    const row: Record<string, string | number> = { dataset: ds };
    for (const model of shownModels) {
      const entry = entries.find(
        (e) => e.dataset_name === ds && e.model_name === model
      );
      if (entry) row[model] = entry.score;
    }
    return row;
  });

  const totalBars = data.reduce(
    (acc, row) => acc + shownModels.filter((m) => m in row).length,
    0
  );
  const labelsOn = showValueLabels && totalBars <= 12;

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} barGap={2} barCategoryGap="24%" margin={{ top: labelsOn ? 20 : 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#f0f0f0" />
          <XAxis
            dataKey="dataset"
            tick={{ fill: TEXT_SECONDARY, fontSize: 12 }}
            axisLine={{ stroke: "#e5e5e5" }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: TEXT_SECONDARY, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <Tooltip
            formatter={(value: number | string) => [`${Number(value).toFixed(1)}%`, undefined]}
            cursor={{ fill: "rgba(0,0,0,0.04)" }}
            contentStyle={{ fontSize: 12, borderRadius: 6 }}
          />
          {shownModels.length > 1 && (
            <Legend wrapperStyle={{ fontSize: 12, color: TEXT_SECONDARY }} />
          )}
          {shownModels.map((model) => (
            <Bar
              key={model}
              dataKey={model}
              fill={colorOf(model)}
              maxBarSize={28}
              radius={[4, 4, 0, 0]}
            >
              {labelsOn && (
                <LabelList
                  dataKey={model}
                  position="top"
                  formatter={(v: React.ReactNode) => `${Number(v).toFixed(0)}%`}
                  style={{ fill: TEXT_SECONDARY, fontSize: 11 }}
                />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      {hiddenCount > 0 && (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          图表最多展示 {MAX_SERIES} 个模型，其余 {hiddenCount} 个见下方表格。
        </Typography.Text>
      )}
    </div>
  );
};

export default ScoreChart;
