import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

import { GlassCard } from "./ui/GlassCard";
import { CHART_COLORS } from "../lib/chartTokens";
import type { MonthlyBreakdown } from "../lib/expenses";
import { useElementWidth } from "../lib/useElementWidth";

interface SpendOverTimeChartProps {
  data: MonthlyBreakdown[];
  currency: string;
}

function formatMonthLabel(month: string): string {
  const [year, monthNum] = month.split("-");
  const date = new Date(Number(year), Number(monthNum) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short" });
}

export function SpendOverTimeChart({ data, currency }: SpendOverTimeChartProps) {
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const points = data
    .filter((row) => row.currency === currency)
    .map((row) => ({ label: formatMonthLabel(row.month), total: Number(row.total) }));

  return (
    <GlassCard className="p-5">
      <div className="text-[15.5px] font-bold tracking-tight text-ink-900">Spend over time</div>
      <div className="mt-1 text-xs text-ink-600">Confirmed expenses ({currency})</div>
      {points.length === 0 ? (
        <div className="mt-5 flex h-[190px] flex-col items-center justify-center gap-1.5 rounded-2xl border border-dashed border-ink-900/[0.14] p-5 text-center">
          <div className="text-sm font-semibold text-ink-900">No confirmed spending yet</div>
          <div className="max-w-[280px] text-xs leading-relaxed text-ink-600">
            Confirm a receipt and this chart starts filling in from that date forward.
          </div>
        </div>
      ) : (
        <div ref={ref} className="mt-3 w-full">
          {width > 0 && (
            <BarChart
              width={width}
              height={214}
              data={points}
              margin={{ top: 8, right: 4, bottom: 0, left: 0 }}
            >
              <defs>
                <linearGradient id="spendOverTimeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2f6bf6" />
                  <stop offset="100%" stopColor="#4b32e0" />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={CHART_COLORS.gridline} vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: CHART_COLORS.baseline }}
                tick={{
                  fill: CHART_COLORS.muted,
                  fontSize: 11,
                  fontFamily: "JetBrains Mono, monospace",
                }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={48}
                tick={{ fill: CHART_COLORS.muted, fontSize: 11 }}
              />
              <Tooltip
                cursor={{ fill: "rgba(47,107,246,0.06)" }}
                contentStyle={{
                  background: "#fff",
                  border: `1px solid ${CHART_COLORS.gridline}`,
                  borderRadius: 10,
                  fontSize: 12,
                }}
                labelStyle={{ color: CHART_COLORS.textSecondary }}
                itemStyle={{ color: CHART_COLORS.textPrimary }}
                formatter={(value: number) => [`${value.toFixed(2)} ${currency}`, "Spend"]}
              />
              <Bar
                dataKey="total"
                fill="url(#spendOverTimeFill)"
                radius={[8, 8, 3, 3]}
                maxBarSize={44}
              />
            </BarChart>
          )}
        </div>
      )}
    </GlassCard>
  );
}
