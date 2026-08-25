import { useState } from "react";

import { exportExpenses, type ExpenseFilters, type ExportFormat, type SortOption } from "../lib/expenses";

interface ExportControlsProps {
  filters: ExpenseFilters;
  sort: SortOption;
}

export function ExportControls({ filters, sort }: ExportControlsProps) {
  const [pending, setPending] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(format: ExportFormat) {
    setError(null);
    setPending(format);
    try {
      // The exported file always reflects these same filters — including an
      // empty result, which downloads as a valid headers-only file rather
      // than failing or doing nothing.
      await exportExpenses(format, sort, filters);
    } catch {
      setError("Export failed. Please try again.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500">Export:</span>
      <button
        onClick={() => handleExport("csv")}
        disabled={pending !== null}
        className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        {pending === "csv" ? "Exporting…" : "CSV"}
      </button>
      <button
        onClick={() => handleExport("xlsx")}
        disabled={pending !== null}
        className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        {pending === "xlsx" ? "Exporting…" : "Excel"}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
