import { SpendByCategoryChart } from "./SpendByCategoryChart";
import { SpendOverTimeChart } from "./SpendOverTimeChart";
import { StatTile } from "./StatTile";
import type { DashboardSummary } from "../lib/expenses";

function formatMoney(total: string, currency: string | null): string {
  const amount = Number(total);
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency ?? "AUD",
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency ?? ""}`.trim();
  }
}

// Charts plot a single currency at a time — mixing units on one axis would
// be as misleading as summing them. The currency with the most confirmed
// spend becomes "the" dashboard; any others are disclosed, not hidden.
function pickPrimaryCurrency(summary: DashboardSummary): string | null {
  const totals = new Map<string, number>();
  for (const row of summary.by_category) {
    if (!row.currency) continue;
    totals.set(row.currency, (totals.get(row.currency) ?? 0) + Number(row.total));
  }
  if (totals.size === 0) return null;
  return [...totals.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

interface DashboardSummarySectionProps {
  summary: DashboardSummary | null;
  isLoading: boolean;
}

export function DashboardSummarySection({ summary, isLoading }: DashboardSummarySectionProps) {
  if (isLoading || !summary) {
    return (
      <div className="rounded-lg border border-gray-200 p-10 text-center text-gray-600">
        Loading dashboard…
      </div>
    );
  }

  const primaryCurrency = pickPrimaryCurrency(summary);
  const otherCurrencies = [
    ...new Set(
      [...summary.by_category, ...summary.by_month, ...summary.month_to_date]
        .map((row) => row.currency)
        .filter((currency): currency is string => currency !== null && currency !== primaryCurrency),
    ),
  ];
  const monthToDate = summary.month_to_date.find((row) => row.currency === primaryCurrency);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatTile
          label="This month"
          value={
            monthToDate
              ? formatMoney(monthToDate.total, monthToDate.currency)
              : primaryCurrency
                ? formatMoney("0", primaryCurrency)
                : "—"
          }
        />
        <StatTile label="Confirmed receipts" value={String(summary.receipt_count)} />
      </div>

      {otherCurrencies.length > 0 && (
        <p className="text-xs text-gray-600">
          Showing {primaryCurrency} — you also have confirmed expenses in{" "}
          {otherCurrencies.join(", ")}, not included in the charts below.
        </p>
      )}

      {primaryCurrency ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SpendOverTimeChart data={summary.by_month} currency={primaryCurrency} />
          <SpendByCategoryChart data={summary.by_category} currency={primaryCurrency} />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-gray-600">
          No confirmed expenses yet — once you review and confirm a receipt, your spending
          insights will show up here.
        </div>
      )}
    </div>
  );
}
