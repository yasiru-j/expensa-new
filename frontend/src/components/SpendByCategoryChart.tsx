import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "../lib/chartTokens";
import type { CategoryBreakdown } from "../lib/expenses";

interface SpendByCategoryChartProps {
  data: CategoryBreakdown[];
  currency: string;
}

export function SpendByCategoryChart({ data, currency }: SpendByCategoryChartProps) {
  const bars = data
    .filter((row) => row.currency === currency)
    .map((row) => ({ category: row.category, total: Number(row.total) }))
    .sort((a, b) => b.total - a.total);

  const height = Math.max(160, bars.length * 36 + 32);

  return (
    <div>
      <h2 className="mb-2 text-sm font-medium text-gray-700">Spend by category ({currency})</h2>
      {bars.length === 0 ? (
        <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-gray-300 text-gray-600">
          No confirmed spending yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={bars} layout="vertical" margin={{ top: 8, right: 48, bottom: 0, left: 8 }}>
            <CartesianGrid stroke={CHART_COLORS.gridline} horizontal={false} />
            <XAxis
              type="number"
              tickLine={false}
              axisLine={false}
              tick={{ fill: CHART_COLORS.muted, fontSize: 12 }}
            />
            <YAxis
              type="category"
              dataKey="category"
              tickLine={false}
              axisLine={false}
              width={120}
              tick={{ fill: CHART_COLORS.textPrimary, fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                background: CHART_COLORS.surface,
                border: `1px solid ${CHART_COLORS.gridline}`,
                borderRadius: 6,
                fontSize: 12,
              }}
              itemStyle={{ color: CHART_COLORS.textPrimary }}
              formatter={(value: number) => [`${value.toFixed(2)} ${currency}`, "Spend"]}
            />
            <Bar dataKey="total" fill={CHART_COLORS.primary} radius={[0, 4, 4, 0]} maxBarSize={24}>
              <LabelList
                dataKey="total"
                position="right"
                formatter={(value: number) => value.toFixed(2)}
                style={{ fill: CHART_COLORS.textPrimary, fontSize: 12 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
