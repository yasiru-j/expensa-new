import { Cell, Pie, PieChart, Tooltip } from "recharts";

import { GlassCard } from "./ui/GlassCard";
import { formatMoney, formatMoneyShort } from "../lib/money";
import type { CategoryBreakdown } from "../lib/expenses";

interface SpendByCategoryChartProps {
  data: CategoryBreakdown[];
  currency: string;
}

const PALETTE = ["#2f6bf6", "#4b32e0", "#7c5cf6", "#9aa8f7", "#c3cbf9"];

export function SpendByCategoryChart({ data, currency }: SpendByCategoryChartProps) {
  const slices = data
    .filter((row) => row.currency === currency)
    .map((row, i) => ({
      category: row.category,
      total: Number(row.total),
      color: PALETTE[i % PALETTE.length],
    }))
    .sort((a, b) => b.total - a.total);

  const grandTotal = slices.reduce((sum, s) => sum + s.total, 0);

  return (
    <GlassCard className="p-5">
      <div className="text-[15.5px] font-bold tracking-tight text-ink-900">Spend by category</div>
      <div className="mt-1 text-xs text-ink-600">{currency}</div>

      {slices.length === 0 ? (
        <div className="mt-5 flex h-[190px] items-center justify-center rounded-2xl border border-dashed border-ink-900/[0.14] p-5 text-center">
          <div className="max-w-[240px] text-xs leading-relaxed text-ink-600">
            Categories appear once your first receipt is confirmed.
          </div>
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-5">
          <div className="relative h-[132px] w-[132px] flex-none">
            <PieChart width={132} height={132}>
              <Pie
                data={slices}
                dataKey="total"
                nameKey="category"
                cx={66}
                cy={66}
                innerRadius={41}
                outerRadius={66}
                stroke="none"
                startAngle={90}
                endAngle={-270}
              >
                {slices.map((s) => (
                  <Cell key={s.category} fill={s.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#fff",
                  border: "1px solid rgba(19,26,58,0.08)",
                  borderRadius: 10,
                  fontSize: 12,
                }}
                formatter={(value: number, _name, entry) => [
                  formatMoney(value, currency),
                  entry.payload.category as string,
                ]}
              />
            </PieChart>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-[19px] font-bold tracking-tight text-ink-900">
                {formatMoneyShort(grandTotal, currency)}
              </div>
              <div className="text-[10.5px] text-ink-600">total</div>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-2.5">
            {slices.map((s) => (
              <div key={s.category} className="flex items-center gap-2">
                <span className="h-2 w-2 flex-none rounded-[3px]" style={{ background: s.color }} />
                <span className="flex-1 truncate text-sm font-medium text-ink-900">
                  {s.category}
                </span>
                <span className="font-mono text-xs text-ink-600">
                  {formatMoney(s.total, currency)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
