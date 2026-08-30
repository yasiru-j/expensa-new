import type { ExpenseListItem, SortOption } from "../lib/expenses";
import { StatusBadge } from "./StatusBadge";

interface ExpensesTableProps {
  items: ExpenseListItem[];
  isLoading: boolean;
  sort: SortOption;
  onSortChange: (sort: SortOption) => void;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onRowClick: (id: string) => void;
}

function formatAmount(total: string | null, currency: string | null): string {
  if (total === null) return "—";
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

export function ExpensesTable({
  items,
  isLoading,
  sort,
  onSortChange,
  page,
  pageSize,
  total,
  onPageChange,
  onRowClick,
}: ExpensesTableProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Expenses</h2>
        <label htmlFor="expenses-sort" className="sr-only">
          Sort expenses
        </label>
        <select
          id="expenses-sort"
          value={sort}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className="rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-700"
        >
          <option value="date_desc">Date (newest)</option>
          <option value="date_asc">Date (oldest)</option>
          <option value="created_desc">Uploaded (newest)</option>
          <option value="created_asc">Uploaded (oldest)</option>
        </select>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-gray-200 p-10 text-center text-gray-600">Loading…</div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-gray-600">
          No expenses yet — upload a receipt above to get started.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Vendor</th>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Total</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {items.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => onRowClick(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onRowClick(item.id);
                    }
                  }}
                  tabIndex={0}
                  aria-label={`View details for ${item.vendor ?? "expense"} on ${item.expense_date ?? "unknown date"}`}
                  className="cursor-pointer hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-gray-400"
                >
                  <td className="px-4 py-2 text-gray-900">
                    <div className="flex items-center gap-2">
                      {item.vendor ?? "—"}
                      {item.is_potential_duplicate && (
                        <span
                          title="Another expense has the same vendor, date, and total"
                          className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
                        >
                          Possible duplicate
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-gray-600">{item.expense_date ?? "—"}</td>
                  <td className="px-4 py-2 text-gray-900">{formatAmount(item.total, item.currency)}</td>
                  <td className="px-4 py-2 text-gray-600">{item.category ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={item.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > pageSize && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="rounded-md border border-gray-300 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="rounded-md border border-gray-300 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
