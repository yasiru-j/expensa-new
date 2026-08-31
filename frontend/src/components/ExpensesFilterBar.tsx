import { useEffect, useState } from "react";

import { CATEGORIES, type ExpenseFilters, type ExpenseStatus } from "../lib/expenses";

interface ExpensesFilterBarProps {
  filters: ExpenseFilters;
  onChange: (filters: ExpenseFilters) => void;
}

const SEARCH_DEBOUNCE_MS = 300;

const STATUS_PILLS: { label: string; status: ExpenseStatus | undefined }[] = [
  { label: "All", status: undefined },
  { label: "Needs review", status: "ready" },
  { label: "Confirmed", status: "confirmed" },
];

const inputClass =
  "rounded-[10px] border border-ink-900/10 bg-white/70 px-2.5 py-1.5 text-sm text-ink-900";

export function ExpensesFilterBar({ filters, onChange }: ExpensesFilterBarProps) {
  // The vendor search box is debounced locally so typing doesn't fire a
  // request per keystroke; every other filter commits immediately.
  const [qInput, setQInput] = useState(filters.q ?? "");

  useEffect(() => {
    setQInput(filters.q ?? "");
  }, [filters.q]);

  useEffect(() => {
    const handle = setTimeout(() => {
      if (qInput !== (filters.q ?? "")) {
        onChange({ ...filters, q: qInput || undefined });
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
    // Deliberately reacting only to qInput — filters/onChange changing
    // shouldn't restart the debounce timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput]);

  function update(patch: Partial<ExpenseFilters>) {
    onChange({ ...filters, ...patch });
  }

  const hasActiveFilters = Boolean(
    filters.dateFrom || filters.dateTo || filters.category || filters.q || filters.status,
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-1 self-start rounded-[11px] bg-ink-900/5 p-[3px]">
        {STATUS_PILLS.map((pill) => {
          const active = filters.status === pill.status;
          return (
            <button
              key={pill.label}
              onClick={() => update({ status: pill.status })}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                active ? "bg-white text-ink-900 shadow-sm" : "text-ink-600 hover:text-ink-900"
              }`}
            >
              {pill.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="date-from" className="block text-xs text-ink-600">
            From
          </label>
          <input
            id="date-from"
            type="date"
            value={filters.dateFrom ?? ""}
            onChange={(e) => update({ dateFrom: e.target.value || undefined })}
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="date-to" className="block text-xs text-ink-600">
            To
          </label>
          <input
            id="date-to"
            type="date"
            value={filters.dateTo ?? ""}
            onChange={(e) => update({ dateTo: e.target.value || undefined })}
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="category-filter" className="block text-xs text-ink-600">
            Category
          </label>
          <select
            id="category-filter"
            value={filters.category ?? ""}
            onChange={(e) => update({ category: e.target.value || undefined })}
            className={`mt-1 ${inputClass}`}
          >
            <option value="">All categories</option>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[10rem] flex-1">
          <label htmlFor="vendor-search" className="block text-xs text-ink-600">
            Search vendor
          </label>
          <input
            id="vendor-search"
            type="text"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="e.g. Corner Cafe"
            className={`mt-1 w-full ${inputClass}`}
          />
        </div>
        {hasActiveFilters && (
          <button
            onClick={() => onChange({})}
            className="h-[33px] rounded-[10px] border border-ink-900/10 bg-white/70 px-3 text-sm font-medium text-ink-600 hover:bg-white hover:text-ink-900"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}
