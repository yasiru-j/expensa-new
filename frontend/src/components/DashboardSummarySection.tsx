import type { ReactNode } from "react";

import { SpendByCategoryChart } from "./SpendByCategoryChart";
import { SpendOverTimeChart } from "./SpendOverTimeChart";
import { formatMoney, pickPrimaryCurrency } from "../lib/money";
import type { DashboardSummary } from "../lib/expenses";

interface DashboardSummarySectionProps {
  summary: DashboardSummary | null;
  isLoading: boolean;
  /** Table's current row count (see Dashboard.tsx) — used for the confirmed/total
   * ratio on the receipts tile. Reflects whatever filters are currently active
   * on the table (unfiltered by default), not a separately-fetched all-time
   * count — documented trade-off, not worth a new endpoint for one tile. */
  tableTotal: number;
  /** Rendered as the third bento tile in the stats row (the upload dropzone) —
   * kept as a slot rather than importing UploadDropzone here, since this
   * component owns layout, not upload behavior. */
  uploadSlot: ReactNode;
}

function SkeletonTile({ accent }: { accent?: boolean }) {
  return (
    <div
      className={`col-span-1 rounded-[22px] p-5 shadow-glass lg:col-span-3 ${
        accent ? "bg-brand-gradient/20" : "border border-white/80 bg-white/[0.62]"
      }`}
    >
      <div className="h-9 w-3/5 animate-pulse rounded-lg bg-ink-900/10" />
      <div className="mt-3 h-3.5 w-2/5 animate-pulse rounded-md bg-ink-900/[0.08]" />
    </div>
  );
}

export function DashboardSummarySection({
  summary,
  isLoading,
  tableTotal,
  uploadSlot,
}: DashboardSummarySectionProps) {
  if (isLoading || !summary) {
    return (
      <>
        <SkeletonTile accent />
        <SkeletonTile />
        <div className="col-span-1 sm:col-span-2 lg:col-span-6">{uploadSlot}</div>
      </>
    );
  }

  const primaryCurrency = pickPrimaryCurrency(summary);
  const otherCurrencies = [
    ...new Set(
      [...summary.by_category, ...summary.by_month, ...summary.month_to_date]
        .map((row) => row.currency)
        .filter(
          (currency): currency is string => currency !== null && currency !== primaryCurrency,
        ),
    ),
  ];
  const monthToDate = summary.month_to_date.find((row) => row.currency === primaryCurrency);
  const spendTotal = monthToDate
    ? formatMoney(monthToDate.total, monthToDate.currency)
    : primaryCurrency
      ? formatMoney(0, primaryCurrency)
      : "—";
  const confirmedPct =
    tableTotal > 0 ? Math.min(100, Math.round((summary.receipt_count / tableTotal) * 100)) : 0;

  return (
    <>
      <div className="relative col-span-1 overflow-hidden rounded-[22px] bg-brand-gradient p-5 text-white shadow-brand lg:col-span-3">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(300px_160px_at_100%_0%,rgba(255,255,255,0.28),transparent_70%)]" />
        <div className="relative font-mono text-[10.5px] uppercase tracking-[0.14em] opacity-80">
          This month&rsquo;s spend
        </div>
        <div className="relative mt-3 text-[32px] font-bold leading-none tracking-tight sm:text-[37px]">
          {spendTotal}
        </div>
      </div>

      <div className="col-span-1 rounded-[22px] border border-white/80 bg-white/[0.62] p-5 shadow-glass lg:col-span-3">
        <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-600">
          Confirmed receipts
        </div>
        <div className="mt-3 flex items-baseline gap-1.5">
          <div className="text-[32px] font-bold leading-none tracking-tight text-ink-900 sm:text-[37px]">
            {summary.receipt_count}
          </div>
          <div className="text-[15px] font-medium text-ink-600">/ {tableTotal}</div>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-ink-900/[0.08]">
          <div
            className="h-full rounded-full bg-brand-gradient"
            style={{ width: `${confirmedPct}%` }}
          />
        </div>
      </div>

      <div className="col-span-1 sm:col-span-2 lg:col-span-6">{uploadSlot}</div>

      {otherCurrencies.length > 0 && (
        <p className="col-span-1 -mt-2 text-xs text-ink-600 sm:col-span-2 lg:col-span-12">
          Showing {primaryCurrency} — you also have confirmed expenses in{" "}
          {otherCurrencies.join(", ")}, not included in the charts below.
        </p>
      )}

      {primaryCurrency ? (
        <>
          <div className="col-span-1 sm:col-span-2 lg:col-span-7">
            <SpendOverTimeChart data={summary.by_month} currency={primaryCurrency} />
          </div>
          <div className="col-span-1 sm:col-span-2 lg:col-span-5">
            <SpendByCategoryChart data={summary.by_category} currency={primaryCurrency} />
          </div>
        </>
      ) : (
        <div className="col-span-1 rounded-[22px] border border-dashed border-ink-900/[0.14] p-10 text-center text-ink-600 sm:col-span-2 lg:col-span-12">
          No confirmed expenses yet — once you review and confirm a receipt, your spending insights
          will show up here.
        </div>
      )}
    </>
  );
}
