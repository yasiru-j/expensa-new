import { isAxiosError } from "axios";
import { useCallback, useEffect, useState } from "react";

import { DashboardSummarySection } from "../components/DashboardSummarySection";
import { ExpenseDetailModal } from "../components/ExpenseDetailModal";
import { ExpensesFilterBar } from "../components/ExpensesFilterBar";
import { ExpensesTable } from "../components/ExpensesTable";
import { UploadDropzone } from "../components/UploadDropzone";
import {
  getDashboardSummary,
  listExpenses,
  uploadExpense,
  type DashboardSummary,
  type ExpenseFilters,
  type ExpenseListItem,
  type SortOption,
} from "../lib/expenses";

const PAGE_SIZE = 20;

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
        {uploadError && <p className="mt-2 text-sm text-red-600">{uploadError}</p>}
      </div>

      <div className="space-y-3">
        <ExpensesFilterBar
          filters={filters}
          onChange={(next) => {
            setFilters(next);
            setPage(1);
          }}
        />

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
