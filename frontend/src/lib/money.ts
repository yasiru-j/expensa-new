import type { DashboardSummary } from "./expenses";

export function formatMoney(total: string | number, currency: string | null): string {
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

// Short form for tight spaces (e.g. "A$4.3k" instead of "A$4,318.60").
export function formatMoneyShort(total: string | number, currency: string | null): string {
  const amount = Number(total);
  if (Math.abs(amount) < 1000) return formatMoney(amount, currency);
  try {
    const parts = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency ?? "AUD",
      notation: "compact",
      maximumFractionDigits: 1,
    }).formatToParts(amount);
    return parts.map((p) => p.value).join("");
  } catch {
    return `${(amount / 1000).toFixed(1)}k ${currency ?? ""}`.trim();
  }
}

// Charts plot a single currency at a time — mixing units on one axis would
// be as misleading as summing them. The currency with the most confirmed
// spend becomes "the" dashboard; any others are disclosed, not hidden.
export function pickPrimaryCurrency(summary: DashboardSummary): string | null {
  const totals = new Map<string, number>();
  for (const row of summary.by_category) {
    if (!row.currency) continue;
    totals.set(row.currency, (totals.get(row.currency) ?? 0) + Number(row.total));
  }
  if (totals.size === 0) return null;
  return [...totals.entries()].sort((a, b) => b[1] - a[1])[0][0];
}
