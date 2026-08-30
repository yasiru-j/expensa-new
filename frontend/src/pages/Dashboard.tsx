import { isAxiosError } from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

import { DashboardSummarySection } from "../components/DashboardSummarySection";
import { ExpenseDetailModal } from "../components/ExpenseDetailModal";
import { ExpensesFilterBar } from "../components/ExpensesFilterBar";
import { ExpensesTable } from "../components/ExpensesTable";
import { ExportControls } from "../components/ExportControls";
import { UploadDropzone } from "../components/UploadDropzone";
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

const PAGE_SIZE = 20;
// Only a multi-page PDF (dispatched to the async worker) ever comes back
// "processing" from the upload call — a single-page image or PDF is always
// processed inline and returns "ready"/"failed" immediately, no polling.
const POLL_INTERVAL_MS = 3000;

export function Dashboard() {
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
      } else if (isAxiosError(err) && (err.response?.status === 400 || err.response?.status === 429)) {
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <DashboardSummarySection summary={summary} isLoading={isSummaryLoading} />
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900">Upload a receipt</h2>
        <p className="mt-1 text-gray-600">JPEG, PNG, or a single-page PDF.</p>
        <div className="mt-4">
          <UploadDropzone onFileSelected={handleFileSelected} disabled={isUploading} />
        </div>
        {isUploading && <p className="mt-2 text-sm text-gray-500">Uploading and extracting…</p>}
        {processingCount > 0 && (
          <p className="mt-2 text-sm text-gray-500" role="status">
            {processingCount === 1
              ? "Processing a multi-page PDF in the background — this can take a moment."
              : `Processing ${processingCount} multi-page PDFs in the background — this can take a moment.`}
          </p>
        )}
        {uploadError && <p className="mt-2 text-sm text-red-600">{uploadError}</p>}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
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
