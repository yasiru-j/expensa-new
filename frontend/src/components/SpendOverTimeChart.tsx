import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHART_COLORS } from "../lib/chartTokens";
import type { MonthlyBreakdown } from "../lib/expenses";

interface SpendOverTimeChartProps {
  data: MonthlyBreakdown[];
  currency: string;
}

function formatMonthLabel(month: string): string {
  const [year, monthNum] = month.split("-");
  const date = new Date(Number(year), Number(monthNum) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

export function SpendOverTimeChart({ data, currency }: SpendOverTimeChartProps) {
  const points = data
    .filter((row) => row.currency === currency)
    .map((row) => ({ label: formatMonthLabel(row.month), total: Number(row.total) }));

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-gray-700">Spend over time ({currency})</h3>
      {points.length === 0 ? (
        <div className="flex h-60 items-center justify-center rounded-lg border border-dashed border-gray-300 text-gray-400">
          No confirmed spending yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={CHART_COLORS.gridline} vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: CHART_COLORS.baseline }}
              tick={{ fill: CHART_COLORS.muted, fontSize: 12 }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={56}
              tick={{ fill: CHART_COLORS.muted, fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                background: CHART_COLORS.surface,
                border: `1px solid ${CHART_COLORS.gridline}`,
                borderRadius: 6,
                fontSize: 12,
              }}
              labelStyle={{ color: CHART_COLORS.textSecondary }}
              itemStyle={{ color: CHART_COLORS.textPrimary }}
              formatter={(value: number) => [`${value.toFixed(2)} ${currency}`, "Spend"]}
            />
            <Line
              dataKey="total"
              stroke={CHART_COLORS.primary}
              strokeWidth={2}
              dot={{ r: 4, fill: CHART_COLORS.primary, stroke: CHART_COLORS.surface, strokeWidth: 2 }}
              activeDot={{
                r: 5,
                fill: CHART_COLORS.primary,
                stroke: CHART_COLORS.surface,
                strokeWidth: 2,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
