import React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ScoreHistoryPoint } from "../types";

// Same validated categorical palette as ScoreChart (fixed slot order)
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

interface TrendChartProps {
  points: ScoreHistoryPoint[];
  /** 完整模型名列表（排序后），保证颜色跟随模型而非排名 */
  colorDomain?: string[];
  height?: number;
}

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return "";
  const d = new Date(iso);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes()
  ).padStart(2, "0")}`;
};

const TrendChart: React.FC<TrendChartProps> = ({
  points,
  colorDomain,
  height = 260,
}) => {
  if (points.length === 0) return null;

  const domain = (
    colorDomain && colorDomain.length > 0
      ? [...colorDomain]
      : [...new Set(points.map((p) => p.model_name))]
  ).sort((a, b) => a.localeCompare(b));
  const models = [
    ...new Set(points.map((p) => p.model_name)),
  ].slice(0, MAX_SERIES);
  const colorOf = (model: string) =>
    SERIES_COLORS[domain.indexOf(model) % MAX_SERIES];

  // One row per run, keyed by time label; lines connect through missing values
  const data = points.map((p) => ({
    time: `${formatTime(p.completed_at)} (#${p.run_id})`,
    [p.model_name]: p.score,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#f0f0f0" />
        <XAxis
          dataKey="time"
          tick={{ fill: TEXT_SECONDARY, fontSize: 11 }}
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
          formatter={(value: number | string) => [
            `${Number(value).toFixed(1)}%`,
            undefined,
          ]}
          contentStyle={{ fontSize: 12, borderRadius: 6 }}
        />
        {models.length > 1 && (
          <Legend wrapperStyle={{ fontSize: 12, color: TEXT_SECONDARY }} />
        )}
        {models.map((model) => (
          <Line
            key={model}
            type="monotone"
            dataKey={model}
            stroke={colorOf(model)}
            strokeWidth={2}
            dot={{ r: 4, fill: colorOf(model), strokeWidth: 0 }}
            activeDot={{ r: 5 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
};

export default TrendChart;
