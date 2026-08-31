import { useState } from "react";

import { Button } from "./ui/Button";
import {
  exportExpenses,
  type ExpenseFilters,
  type ExportFormat,
  type SortOption,
} from "../lib/expenses";

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
      <Button
        variant="secondary"
        size="sm"
        onClick={() => handleExport("csv")}
        disabled={pending !== null}
      >
        {pending === "csv" ? "Exporting…" : "Export CSV"}
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => handleExport("xlsx")}
        disabled={pending !== null}
      >
        {pending === "xlsx" ? "Exporting…" : "Export Excel"}
      </Button>
      {error && <span className="text-xs text-rose-600">{error}</span>}
    </div>
  );
}
