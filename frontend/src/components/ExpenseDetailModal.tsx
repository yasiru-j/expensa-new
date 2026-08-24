import { useEffect, useState } from "react";

import { getExpense, type ExpenseDetail } from "../lib/expenses";
import { StatusBadge } from "./StatusBadge";

interface ExpenseDetailModalProps {
  expenseId: string;
  onClose: () => void;
}

export function ExpenseDetailModal({ expenseId, onClose }: ExpenseDetailModalProps) {
  const [detail, setDetail] = useState<ExpenseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);

    getExpense(expenseId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this expense.");
      });

    return () => {
      cancelled = true;
    };
  }, [expenseId]);

  const isPdf = detail?.file_url?.split("?")[0].toLowerCase().endsWith(".pdf") ?? false;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Expense detail</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close">
            ✕
          </button>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {!detail && !error && <p className="text-gray-400">Loading…</p>}

        {detail && (
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="space-y-3 text-sm">
              <StatusBadge status={detail.status} />

              <dl className="space-y-1">
                <Row label="Vendor" value={detail.vendor} />
                <Row label="Date" value={detail.expense_date} />
                <Row
                  label="Total"
                  value={detail.total ? `${detail.total} ${detail.currency ?? ""}`.trim() : null}
                />
                <Row label="Subtotal" value={detail.subtotal} />
                <Row label="Tax" value={detail.tax} />
                <Row label="Category" value={detail.category} />
                <Row label="Payment method" value={detail.payment_method} />
                <Row label="Vendor tax ID" value={detail.vendor_tax_id} />
              </dl>

              {detail.line_items.length > 0 && (
                <div>
                  <p className="mt-3 font-medium text-gray-700">Line items</p>
                  <ul className="mt-1 space-y-1">
                    {detail.line_items.map((li) => (
                      <li key={li.id} className="flex justify-between gap-4 text-gray-600">
                        <span>{li.description}</span>
                        <span>{li.amount ?? "—"}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div>
              {!detail.file_url ? (
                <p className="text-gray-400">No preview available.</p>
              ) : isPdf ? (
                <a
                  href={detail.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 underline"
                >
                  View original PDF
                </a>
              ) : (
                <img
                  src={detail.file_url}
                  alt="Receipt"
                  className="w-full rounded-md border border-gray-200"
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-gray-900">{value ?? "—"}</dd>
    </div>
  );
}
