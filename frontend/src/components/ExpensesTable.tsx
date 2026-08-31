import { formatMoney } from "../lib/money";
import type { ExpenseListItem, SortOption } from "../lib/expenses";
import { GlassCard } from "./ui/GlassCard";
import { Pill } from "./ui/Pill";
import { StatusBadge } from "./StatusBadge";

function formatAmount(total: string | null, currency: string | null): string {
  return total === null ? "—" : formatMoney(total, currency);
}

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

function DuplicateBadge() {
  return (
    <Pill tone="warning" dot={false} className="whitespace-nowrap">
      Possible duplicate
    </Pill>
  );
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
    <GlassCard className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[15.5px] font-bold tracking-tight text-ink-900">Expenses</div>
          <div className="mt-0.5 text-xs text-ink-600">
            {total} expense{total === 1 ? "" : "s"}
          </div>
        </div>
        <div>
          <label htmlFor="expenses-sort" className="sr-only">
            Sort expenses
          </label>
          <select
            id="expenses-sort"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortOption)}
            className="rounded-[10px] border border-ink-900/10 bg-white/70 px-2.5 py-1.5 text-sm text-ink-900"
          >
            <option value="date_desc">Date (newest)</option>
            <option value="date_asc">Date (oldest)</option>
            <option value="created_desc">Uploaded (newest)</option>
            <option value="created_asc">Uploaded (oldest)</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-12 animate-pulse rounded-xl bg-ink-900/5" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2.5 rounded-2xl border border-dashed border-ink-900/[0.14] px-6 py-12 text-center">
          <span className="flex h-[42px] w-[42px] items-center justify-center rounded-2xl bg-brand-blue/10 text-xl font-semibold text-brand-blue">
            +
          </span>
          <div className="text-base font-bold text-ink-900">No expenses yet</div>
          <p className="max-w-[360px] text-sm leading-relaxed text-ink-600">
            Upload a receipt and Expensa pulls out the vendor, date, total, and line items for you
            to confirm.
          </p>
        </div>
      ) : (
        <>
          {/* Desktop / tablet: a real table (keyboard nav + AT semantics from
              the a11y pass stay intact). Below `md` this is hidden in favor
              of the stacked card list — a fixed-column table has no good
              mobile rendering, and the design brief asked for real
              responsiveness rather than horizontal scroll. */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-900/[0.08] text-left font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-600">
                  <th className="px-3 pb-2.5 font-medium">Vendor</th>
                  <th className="px-3 pb-2.5 font-medium">Date</th>
                  <th className="px-3 pb-2.5 font-medium">Category</th>
                  <th className="px-3 pb-2.5 text-right font-medium">Amount</th>
                  <th className="px-3 pb-2.5 font-medium">Status</th>
                  <th className="px-3 pb-2.5" />
                </tr>
              </thead>
              <tbody>
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
                    className="cursor-pointer rounded-xl border-b border-ink-900/[0.055] transition hover:bg-white/75 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-blue/50"
                  >
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink-900">{item.vendor ?? "—"}</span>
                        {item.is_potential_duplicate && <DuplicateBadge />}
                      </div>
                    </td>
                    <td className="px-3 py-3 font-mono text-[12.5px] text-ink-600">
                      {item.expense_date ?? "—"}
                    </td>
                    <td className="px-3 py-3">
                      {item.category && (
                        <span className="inline-block rounded-full bg-ink-900/[0.055] px-2.5 py-1 text-xs font-medium text-ink-600">
                          {item.category}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[13px] font-medium text-ink-900">
                      {formatAmount(item.total, item.currency)}
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-3 py-3 text-right text-ink-300">→</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile: stacked cards. */}
          <ul className="flex flex-col gap-2 md:hidden">
            {items.map((item) => (
              <li key={item.id}>
                <div
                  role="button"
                  onClick={() => onRowClick(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onRowClick(item.id);
                    }
                  }}
                  tabIndex={0}
                  aria-label={`View details for ${item.vendor ?? "expense"} on ${item.expense_date ?? "unknown date"}`}
                  className="flex cursor-pointer flex-col gap-1.5 rounded-2xl border border-ink-900/[0.07] bg-white/70 p-3.5 focus:outline-none focus:ring-2 focus:ring-brand-blue/50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-ink-900">{item.vendor ?? "—"}</span>
                    <span className="font-mono text-sm font-medium text-ink-900">
                      {formatAmount(item.total, item.currency)}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-xs text-ink-600">
                      {item.expense_date ?? "—"}
                    </span>
                    {item.category && (
                      <span className="rounded-full bg-ink-900/[0.055] px-2 py-0.5 text-[11px] font-medium text-ink-600">
                        {item.category}
                      </span>
                    )}
                    <StatusBadge status={item.status} />
                    {item.is_potential_duplicate && <DuplicateBadge />}
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {total > pageSize && (
            <div className="mt-4 flex items-center justify-between text-sm text-ink-600">
              <button
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                className="rounded-[10px] border border-ink-900/10 bg-white/70 px-3 py-1.5 font-medium disabled:opacity-40"
              >
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                className="rounded-[10px] border border-ink-900/10 bg-white/70 px-3 py-1.5 font-medium disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </GlassCard>
  );
}
