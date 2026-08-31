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
import { Button } from "./ui/Button";
import { Pill } from "./ui/Pill";
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
  const lowConfidenceCount = detail
    ? EDITABLE_FIELDS.filter((field) => {
        const p = detail.field_provenance[field];
        return p != null && p.confidence != null && p.confidence < LOW_CONFIDENCE_THRESHOLD;
      }).length
    : 0;

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/[0.34] p-4 backdrop-blur-sm sm:p-8"
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
        className="flex max-h-[88vh] w-full max-w-[1000px] animate-pop flex-col overflow-hidden rounded-[26px] border border-white/90 bg-white/[0.82] shadow-glass-lg backdrop-blur-2xl backdrop-saturate-150 focus:outline-none"
      >
        <div className="flex flex-none items-start justify-between gap-4 border-b border-ink-900/[0.07] bg-white/70 px-5 py-4 backdrop-blur-md sm:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <span id="expense-detail-title" className="text-lg font-bold text-ink-900 sm:text-xl">
                {detail?.vendor || "Expense detail"}
              </span>
              {detail && <StatusBadge status={detail.status} />}
              {detail?.is_potential_duplicate && (
                <Pill tone="warning" dot={false}>
                  Possible duplicate
                </Pill>
              )}
            </div>
            {detail && (
              <div className="mt-1 font-mono text-xs text-ink-600">
                {detail.expense_date ?? "no date"}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 flex-none items-center justify-center rounded-[11px] text-ink-600 hover:bg-ink-900/5"
          >
            ✕
          </button>
        </div>

        <div className="overflow-y-auto">
          {error && (
            <p className="mx-5 mt-4 rounded-xl bg-rose-600/10 px-3 py-2 text-sm text-rose-800 sm:mx-6">
              {error}
            </p>
          )}
          {!detail && !error && <p className="p-6 text-ink-600">Loading…</p>}

          {detail && formValues && (
            <div className="grid gap-5 p-5 sm:px-6 lg:grid-cols-[1.15fr_1fr]">
              <div className="flex flex-col gap-5 text-sm">
                <div>
                  <div className="mb-2.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-600">
                    Extracted fields
                  </div>
                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
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
                </div>

                {detail.line_items.length > 0 && (
                  <div>
                    <div className="mb-2.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-600">
                      Line items
                    </div>
                    <div className="overflow-hidden rounded-2xl border border-ink-900/[0.08] bg-white/60">
                      {detail.line_items.map((li) => (
                        <div
                          key={li.id}
                          className="flex justify-between gap-4 border-b border-ink-900/[0.06] px-3.5 py-2.5 last:border-0"
                        >
                          <span className="text-ink-900">{li.description}</span>
                          <span className="font-mono text-ink-900">{li.amount ?? "—"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-3.5">
                <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-600">
                  Receipt
                </div>
                {!detail.file_url ? (
                  <div className="flex min-h-[220px] flex-1 items-center justify-center rounded-[18px] border border-ink-900/10 bg-ink-900/[0.03] text-sm text-ink-600">
                    No preview available.
                  </div>
                ) : isPdf ? (
                  <a
                    href={detail.file_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex min-h-[220px] flex-1 items-center justify-center rounded-[18px] border border-ink-900/10 bg-ink-900/[0.03] text-sm font-semibold text-brand-blue underline"
                  >
                    View original PDF
                  </a>
                ) : (
                  <img
                    src={detail.file_url}
                    alt="Receipt"
                    className="w-full rounded-[18px] border border-ink-900/10 object-contain"
                  />
                )}
              </div>
            </div>
          )}
        </div>

        {detail && formValues && isEditable && (
          <div className="flex flex-none flex-col items-center justify-between gap-3 border-t border-ink-900/[0.07] bg-white/75 px-5 py-4 backdrop-blur-md sm:flex-row sm:px-6">
            <div className="text-xs text-ink-600">
              {lowConfidenceCount > 0
                ? `${lowConfidenceCount} field${lowConfidenceCount === 1 ? "" : "s"} fell below ${Math.round(LOW_CONFIDENCE_THRESHOLD * 100)}% confidence. Check ${lowConfidenceCount === 1 ? "it" : "them"} before confirming.`
                : ""}
            </div>
            <div className="flex gap-2.5">
              <Button
                variant="secondary"
                onClick={() => void handleSave()}
                disabled={dirtyFields.size === 0 || isSaving}
              >
                {isSaving ? "Saving…" : "Save changes"}
              </Button>
              <Button
                variant="primary"
                onClick={() => void handleConfirm()}
                disabled={dirtyFields.size > 0 || isConfirming}
                title={dirtyFields.size > 0 ? "Save your changes before confirming" : undefined}
              >
                {isConfirming ? "Confirming…" : "Confirm expense"}
              </Button>
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
  const confidencePct =
    provenance?.confidence != null ? Math.round(provenance.confidence * 100) : null;

  const inputClass =
    "w-full rounded-[10px] border border-ink-900/10 bg-white/80 px-2.5 py-1.5 text-sm text-ink-900";

  return (
    <div
      className={`rounded-[14px] border p-3 ${
        needsAttention
          ? "border-amber-500/[0.28] bg-amber-500/[0.08]"
          : "border-ink-900/[0.08] bg-white/70"
      }`}
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <label className="text-[11.5px] text-ink-600">{label}</label>
        <div className="flex items-center gap-1">
          {isUserSourced && (
            <Pill tone="neutral" dot={false} className="!px-1.5 !py-0.5 !text-[10px]">
              edited
            </Pill>
          )}
          {confidencePct != null && (
            <Pill
              tone={needsAttention ? "warning" : "success"}
              className="!px-1.5 !py-0.5 !text-[10px]"
              title={flags.length > 0 ? flags.join(", ") : undefined}
            >
              {confidencePct}%
            </Pill>
          )}
        </div>
      </div>

      {!editable ? (
        <p className="font-mono text-[14.5px] font-medium text-ink-900">{value || "—"}</p>
      ) : field === "category" ? (
        <select value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>
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
          className={inputClass}
        />
      ) : field === "subtotal" || field === "tax" || field === "total" ? (
        <input
          type="number"
          step="0.01"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      )}
    </div>
  );
}
