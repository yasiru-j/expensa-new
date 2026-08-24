import { useEffect, useState } from "react";

import { CATEGORIES, type ExpenseFilters } from "../lib/expenses";

interface ExpensesFilterBarProps {
  filters: ExpenseFilters;
  onChange: (filters: ExpenseFilters) => void;
}

const SEARCH_DEBOUNCE_MS = 300;

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
    filters.dateFrom || filters.dateTo || filters.category || filters.q,
  );

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white p-3">
      <div>
        <label htmlFor="date-from" className="block text-xs text-gray-500">
          From
        </label>
        <input
          id="date-from"
          type="date"
          value={filters.dateFrom ?? ""}
          onChange={(e) => update({ dateFrom: e.target.value || undefined })}
          className="rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
      <div>
        <label htmlFor="date-to" className="block text-xs text-gray-500">
          To
        </label>
        <input
          id="date-to"
          type="date"
          value={filters.dateTo ?? ""}
          onChange={(e) => update({ dateTo: e.target.value || undefined })}
          className="rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
      <div>
        <label htmlFor="category-filter" className="block text-xs text-gray-500">
          Category
        </label>
        <select
          id="category-filter"
          value={filters.category ?? ""}
          onChange={(e) => update({ category: e.target.value || undefined })}
          className="rounded-md border border-gray-300 px-2 py-1 text-sm"
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
        <label htmlFor="vendor-search" className="block text-xs text-gray-500">
          Search vendor
        </label>
        <input
          id="vendor-search"
          type="text"
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="e.g. Corner Cafe"
          className="w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
      {hasActiveFilters && (
        <button
          onClick={() => onChange({})}
          className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
