import { useEffect, useMemo, useRef, useState } from "react";

import {
  CATEGORIES,
  EDITABLE_FIELDS,
  confirmExpense,
  getExpense,
  patchExpense,
  type EditableField,
  type ExpenseDetail,
  type ExpensePatch,
  type FieldProvenanceEntry,
} from "../lib/expenses";
import { StatusBadge } from "./StatusBadge";

interface ExpenseDetailModalProps {
  expenseId: string;
  onClose: () => void;
  /** Called after a successful save or confirm, so the caller (the expenses
   * table) can refresh and pick up the new status/values. */
  onUpdated?: () => void;
}

const FIELD_LABELS: Record<EditableField, string> = {
  vendor: "Vendor",
  vendor_tax_id: "Vendor tax ID",
  expense_date: "Date",
  subtotal: "Subtotal",
  tax: "Tax",
  total: "Total",
  currency: "Currency",
  category: "Category",
  payment_method: "Payment method",
};

// We only ever have one overall model-reported confidence, duplicated across
// every field's provenance entry — this threshold is a soft "the model
// wasn't very sure about this extraction at all" signal. The `flags` array
// is the sharper, field-specific signal (an actual validation issue).
const LOW_CONFIDENCE_THRESHOLD = 0.7;

type FormValues = Record<EditableField, string>;

function toFormValues(detail: ExpenseDetail): FormValues {
  const values = {} as FormValues;
  for (const field of EDITABLE_FIELDS) {
    values[field] = detail[field] ?? "";
  }
  return values;
}

export function ExpenseDetailModal({ expenseId, onClose, onUpdated }: ExpenseDetailModalProps) {
  const [detail, setDetail] = useState<ExpenseDetail | null>(null);
  const [formValues, setFormValues] = useState<FormValues | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const FOCUSABLE_SELECTOR =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  // Keyboard/AT users get a full dialog contract even though the backdrop's
  // click-to-close (below) is mouse-only: Escape closes from anywhere, Tab
  // is trapped inside the panel (this view can have as little as one
  // focusable element — the Close button, for a non-editable "confirmed"
  // expense — so without wrapping, Tab would walk straight out into the
  // page behind an still-open dialog), and focus moves onto the dialog on
  // open and back to whatever triggered it on close.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );
      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setFormValues(null);
    setError(null);

    getExpense(expenseId)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setFormValues(toFormValues(data));
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this expense.");
      });

    return () => {
      cancelled = true;
    };
  }, [expenseId]);

  const dirtyFields = useMemo(() => {
    if (!detail || !formValues) return new Set<EditableField>();
    const original = toFormValues(detail);
    return new Set(EDITABLE_FIELDS.filter((field) => formValues[field] !== original[field]));
  }, [detail, formValues]);

  const isEditable = detail?.status === "ready";
  const isPdf = detail?.file_url?.split("?")[0].toLowerCase().endsWith(".pdf") ?? false;

  function handleFieldChange(field: EditableField, value: string) {
    setFormValues((prev) => (prev ? { ...prev, [field]: value } : prev));
  }

  async function handleSave() {
    if (!detail || !formValues || dirtyFields.size === 0) return;
    setError(null);
    setIsSaving(true);
    try {
      const patch: ExpensePatch = {};
      for (const field of dirtyFields) {
        patch[field] = formValues[field] === "" ? null : formValues[field];
      }
      const updated = await patchExpense(expenseId, patch);
      setDetail(updated);
      setFormValues(toFormValues(updated));
      onUpdated?.();
    } catch {
      setError("Couldn't save your changes. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConfirm() {
    setError(null);
    setIsConfirming(true);
    try {
      const updated = await confirmExpense(expenseId);
      setDetail(updated);
      setFormValues(toFormValues(updated));
      onUpdated?.();
    } catch {
      setError("Couldn't confirm this expense. Please try again.");
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    // Backdrop click-to-close is a mouse-only convenience — Escape (handled
    // in the effect above) and the Close button below give keyboard/AT
    // users the same result, so this one handler is deliberately exempt.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="expense-detail-title"
        tabIndex={-1}
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl focus:outline-none"
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 id="expense-detail-title" className="text-lg font-semibold text-gray-900">
            Expense detail
          </h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700" aria-label="Close">
            ✕
          </button>
        </div>

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
        {!detail && !error && <p className="text-gray-600">Loading…</p>}

        {detail && formValues && (
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="space-y-4 text-sm">
              <div className="flex items-center gap-2">
                <StatusBadge status={detail.status} />
                {detail.is_potential_duplicate && (
                  <span
                    title="Another expense has the same vendor, date, and total"
                    className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
                  >
                    Possible duplicate
                  </span>
                )}
              </div>

              <div className="space-y-3">
                {EDITABLE_FIELDS.map((field) => (
                  <FieldRow
                    key={field}
                    label={FIELD_LABELS[field]}
                    field={field}
                    value={formValues[field]}
                    provenance={detail.field_provenance[field]}
                    editable={isEditable}
                    onChange={(value) => handleFieldChange(field, value)}
                  />
                ))}
              </div>

              {detail.line_items.length > 0 && (
                <div>
                  <p className="font-medium text-gray-700">Line items</p>
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

              {isEditable && (
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => void handleSave()}
                    disabled={dirtyFields.size === 0 || isSaving}
                    className="rounded-md bg-gray-900 px-3 py-1.5 text-sm text-white hover:bg-gray-800 disabled:opacity-40"
                  >
                    {isSaving ? "Saving…" : "Save changes"}
                  </button>
                  <button
                    onClick={() => void handleConfirm()}
                    disabled={dirtyFields.size > 0 || isConfirming}
                    title={dirtyFields.size > 0 ? "Save your changes before confirming" : undefined}
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-40"
                  >
                    {isConfirming ? "Confirming…" : "Confirm"}
                  </button>
                </div>
              )}
            </div>

            <div>
              {!detail.file_url ? (
                <p className="text-gray-600">No preview available.</p>
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

interface FieldRowProps {
  field: EditableField;
  label: string;
  value: string;
  provenance: FieldProvenanceEntry | undefined;
  editable: boolean;
  onChange: (value: string) => void;
}

function FieldRow({ field, label, value, provenance, editable, onChange }: FieldRowProps) {
  const flags = provenance?.flags ?? [];
  const isLowConfidence =
    provenance != null &&
    provenance.confidence != null &&
    provenance.confidence < LOW_CONFIDENCE_THRESHOLD;
  const needsAttention = flags.length > 0 || isLowConfidence;
  const isUserSourced = provenance?.source === "user";

  return (
    <div className={`rounded-md p-2 ${needsAttention ? "border border-amber-300 bg-amber-50" : ""}`}>
      <div className="mb-1 flex items-center justify-between">
        <label className="text-xs font-medium text-gray-500">{label}</label>
        <div className="flex items-center gap-1">
          {isUserSourced && (
            <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] text-blue-700">
              edited
            </span>
          )}
          {needsAttention && (
            <span
              className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800"
              title={flags.length > 0 ? flags.join(", ") : "Low confidence"}
            >
              check this
            </span>
          )}
        </div>
      </div>

      {!editable ? (
        <p className="text-gray-900">{value || "—"}</p>
      ) : field === "category" ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-2 py-1"
        >
          <option value="">—</option>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
      ) : field === "expense_date" ? (
        <input
          type="date"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-2 py-1"
        />
      ) : field === "subtotal" || field === "tax" || field === "total" ? (
        <input
          type="number"
          step="0.01"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-2 py-1"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-2 py-1"
        />
      )}
    </div>
  );
}
