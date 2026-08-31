import { isAxiosError } from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

import { DashboardSummarySection } from "../components/DashboardSummarySection";
import { ExpenseDetailModal } from "../components/ExpenseDetailModal";
import { ExpensesFilterBar } from "../components/ExpensesFilterBar";
import { ExpensesTable } from "../components/ExpensesTable";
import { ExportControls } from "../components/ExportControls";
import { GlassCard } from "../components/ui/GlassCard";
import { UploadDropzone } from "../components/UploadDropzone";
import { useAuth } from "../lib/auth";
import {
  getDashboardSummary,
  getExpense,
  listExpenses,
  uploadExpense,
  type DashboardSummary,
  type ExpenseFilters,
  type ExpenseListItem,
  type SortOption,
} from "../lib/expenses";
import { firstNameFor } from "../lib/initials";

const PAGE_SIZE = 20;
// Only a multi-page PDF (dispatched to the async worker) ever comes back
// "processing" from the upload call — a single-page image or PDF is always
// processed inline and returns "ready"/"failed" immediately, no polling.
const POLL_INTERVAL_MS = 3000;

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function Dashboard() {
  const { user } = useAuth();
  const [items, setItems] = useState<ExpenseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortOption>("date_desc");
  const [filters, setFilters] = useState<ExpenseFilters>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedExpenseId, setSelectedExpenseId] = useState<string | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isSummaryLoading, setIsSummaryLoading] = useState(true);
  const [processingCount, setProcessingCount] = useState(0);
  const pollIntervalsRef = useRef<number[]>([]);

  useEffect(() => {
    const intervals = pollIntervalsRef.current;
    return () => {
      intervals.forEach((id) => window.clearInterval(id));
    };
  }, []);

  const refresh = useCallback(
    async (targetPage: number, targetSort: SortOption, targetFilters: ExpenseFilters) => {
      setIsLoading(true);
      try {
        const data = await listExpenses({
          page: targetPage,
          sort: targetSort,
          ...targetFilters,
        });
        setItems(data.items);
        setTotal(data.total);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const refreshSummary = useCallback(async () => {
    setIsSummaryLoading(true);
    try {
      setSummary(await getDashboardSummary());
    } finally {
      setIsSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh(page, sort, filters);
  }, [page, sort, filters, refresh]);

  useEffect(() => {
    void refreshSummary();
  }, [refreshSummary]);

  function pollUntilProcessed(expenseId: string) {
    setProcessingCount((n) => n + 1);
    const intervalId = window.setInterval(() => {
      void (async () => {
        let done = true;
        try {
          const detail = await getExpense(expenseId);
          done = detail.status !== "processing";
        } catch {
          done = true; // stop polling on error rather than retrying forever
        }
        if (!done) return;

        window.clearInterval(intervalId);
        pollIntervalsRef.current = pollIntervalsRef.current.filter((id) => id !== intervalId);
        setProcessingCount((n) => Math.max(0, n - 1));
        // Jump to the newest view, same as a synchronous upload completing —
        // by the time this resolves the user may be on a different page/
        // filter than when the upload started, and this row is what they're
        // waiting to see.
        setSort("created_desc");
        setPage(1);
        setFilters({});
        await refresh(1, "created_desc", {});
        await refreshSummary();
      })();
    }, POLL_INTERVAL_MS);
    pollIntervalsRef.current.push(intervalId);
  }

  async function handleFileSelected(file: File) {
    setUploadError(null);
    setIsUploading(true);
    try {
      const result = await uploadExpense(file);
      if (result.status === "failed") {
        setUploadError(
          "We couldn't extract data from that file — it may not be a clear receipt, or " +
            "something went wrong. It's still saved below; try uploading a different file.",
        );
      } else if (result.status === "processing") {
        pollUntilProcessed(result.id);
      }
      // Jump to the most-recently-uploaded view so the new row is visible
      // immediately, regardless of what the user was sorted/paged/filtered to before.
      setSort("created_desc");
      setPage(1);
      setFilters({});
      await refresh(1, "created_desc", {});
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 413) {
        setUploadError("That file is too large.");
      } else if (
        isAxiosError(err) &&
        (err.response?.status === 400 || err.response?.status === 429)
      ) {
        // 429 covers both the per-hour rate limit and the monthly quota —
        // the backend's message already distinguishes which one fired.
        const detail = err.response.data as { detail?: string } | undefined;
        setUploadError(detail?.detail ?? "That file couldn't be processed.");
      } else {
        setUploadError("Upload failed. Please try again.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  function handleReviewUpdated() {
    void refresh(page, sort, filters);
    // A save/confirm can change a row's status or confirmed totals — the
    // dashboard aggregates need to reflect that too.
    void refreshSummary();
  }

  const monthLabel = new Date().toLocaleDateString(undefined, { month: "long", year: "numeric" });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-600">
            {monthLabel}
          </div>
          <h1 className="mt-1 text-[28px] font-bold tracking-tight text-ink-900 sm:text-[31px]">
            {greeting()}
            {user ? `, ${firstNameFor(user.full_name, user.email)}` : ""}
          </h1>
        </div>
      </div>

      {processingCount > 0 && (
        <div
          role="status"
          className="flex items-center gap-3 rounded-2xl border border-brand-blue/25 bg-brand-blue/[0.09] px-4 py-3"
        >
          <span className="h-[15px] w-[15px] flex-none animate-spin rounded-full border-2 border-brand-blue/25 border-t-brand-blue" />
          <p className="text-[13.5px] font-medium text-blue-900">
            {processingCount === 1
              ? "Processing a multi-page PDF in the background. You can keep working — we'll add it to the table when it finishes."
              : `Processing ${processingCount} multi-page PDFs in the background. You can keep working — we'll add them to the table when they finish.`}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12">
        <DashboardSummarySection
          summary={summary}
          isLoading={isSummaryLoading}
          tableTotal={total}
          uploadSlot={
            isUploading ? (
              <GlassCard className="flex h-full min-h-[150px] flex-col items-center justify-center gap-3 p-5 text-center">
                <span className="h-[26px] w-[26px] animate-spin rounded-full border-[2.5px] border-brand-blue/20 border-t-brand-blue" />
                <div className="text-[15px] font-semibold text-ink-900">
                  Uploading and extracting…
                </div>
              </GlassCard>
            ) : uploadError ? (
              <GlassCard className="flex h-full min-h-[150px] flex-col items-center justify-center gap-2.5 border-rose-600/20 bg-rose-600/[0.06] p-5 text-center">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-600/[0.12] text-lg font-bold text-rose-600">
                  !
                </span>
                <div className="text-[15px] font-semibold text-rose-800">
                  We couldn&rsquo;t read that receipt
                </div>
                <p className="max-w-[330px] text-xs leading-relaxed text-ink-600">{uploadError}</p>
                <button
                  onClick={() => setUploadError(null)}
                  className="mt-1 h-8 rounded-[10px] bg-brand-gradient px-3.5 text-xs font-semibold text-white shadow-brand"
                >
                  Try again
                </button>
              </GlassCard>
            ) : (
              <UploadDropzone onFileSelected={handleFileSelected} disabled={isUploading} />
            )
          }
        />

        <div className="col-span-1 sm:col-span-2 lg:col-span-12">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
            <ExpensesFilterBar
              filters={filters}
              onChange={(next) => {
                setFilters(next);
                setPage(1);
              }}
            />
            <ExportControls filters={filters} sort={sort} />
          </div>

          <ExpensesTable
            items={items}
            isLoading={isLoading}
            sort={sort}
            onSortChange={(next) => {
              setSort(next);
              setPage(1);
            }}
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
            onRowClick={setSelectedExpenseId}
          />
        </div>
      </div>

      {selectedExpenseId && (
        <ExpenseDetailModal
          expenseId={selectedExpenseId}
          onClose={() => setSelectedExpenseId(null)}
          onUpdated={handleReviewUpdated}
        />
      )}
    </div>
  );
}
