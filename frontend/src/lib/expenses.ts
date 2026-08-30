import { api } from "./api";

// Decimal fields (total, subtotal, tax, quantity, unit_price, amount,
// extracted_confidence) come back as JSON strings, not numbers — Pydantic v2
// serializes Decimal to string by default to avoid float precision loss.

export type ExpenseStatus = "pending" | "processing" | "ready" | "confirmed" | "failed";
export type SortOption = "date_desc" | "date_asc" | "created_desc" | "created_asc";

// Mirrors app/extraction/schema.py CATEGORIES exactly.
export const CATEGORIES = [
  "Meals",
  "Travel",
  "Office Supplies",
  "Software",
  "Utilities",
  "Professional Services",
  "Other",
] as const;

export interface LineItem {
  id: string;
  description: string | null;
  quantity: string | null;
  unit_price: string | null;
  amount: string | null;
}

export interface ExpenseListItem {
  id: string;
  vendor: string | null;
  expense_date: string | null;
  total: string | null;
  currency: string | null;
  category: string | null;
  status: ExpenseStatus;
  extracted_confidence: string | null;
  created_at: string;
  // True when another of the caller's expenses shares vendor + expense_date
  // + total — a warning, never a block.
  is_potential_duplicate: boolean;
}

// The scalar fields tracked in field_provenance and editable via PATCH.
// line_items are a list, not a single value, and aren't provenance-tracked
// or user-editable in this phase.
export const EDITABLE_FIELDS = [
  "vendor",
  "vendor_tax_id",
  "expense_date",
  "subtotal",
  "tax",
  "total",
  "currency",
  "category",
  "payment_method",
] as const;

export type EditableField = (typeof EDITABLE_FIELDS)[number];

export interface FieldProvenanceEntry {
  source: "ai" | "user";
  ai_value: string | number | boolean | null;
  confidence: number | null;
  flags?: string[];
}

export type FieldProvenance = Partial<Record<EditableField, FieldProvenanceEntry>>;

export interface ExpenseDetail extends ExpenseListItem {
  vendor_tax_id: string | null;
  subtotal: string | null;
  tax: string | null;
  payment_method: string | null;
  updated_at: string;
  line_items: LineItem[];
  file_url: string | null;
  field_provenance: FieldProvenance;
}

// Form inputs naturally produce strings (including for date/decimal
// fields) — the backend's Pydantic model parses ISO date/Decimal strings
// directly, so there's no need to convert before sending.
export type ExpensePatch = Partial<Record<EditableField, string | null>>;

export interface PaginatedExpenses {
  items: ExpenseListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface UploadResponse {
  id: string;
  status: ExpenseStatus;
}

export async function uploadExpense(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  // No explicit Content-Type: axios/the browser must generate the multipart
  // boundary themselves, which a manually-set header would break.
  const res = await api.post<UploadResponse>("/api/expenses/upload", formData);
  return res.data;
}

export interface ExpenseFilters {
  status?: ExpenseStatus;
  dateFrom?: string; // ISO date
  dateTo?: string; // ISO date
  category?: string;
  q?: string; // free-text vendor search
}

export async function listExpenses(
  params: { page?: number; pageSize?: number; sort?: SortOption } & ExpenseFilters,
): Promise<PaginatedExpenses> {
  const res = await api.get<PaginatedExpenses>("/api/expenses", {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      sort: params.sort ?? "date_desc",
      status: params.status,
      date_from: params.dateFrom,
      date_to: params.dateTo,
      category: params.category,
      q: params.q,
    },
  });
  return res.data;
}

export async function getExpense(id: string): Promise<ExpenseDetail> {
  const res = await api.get<ExpenseDetail>(`/api/expenses/${id}`);
  return res.data;
}

export async function patchExpense(id: string, patch: ExpensePatch): Promise<ExpenseDetail> {
  const res = await api.patch<ExpenseDetail>(`/api/expenses/${id}`, patch);
  return res.data;
}

export async function confirmExpense(id: string): Promise<ExpenseDetail> {
  const res = await api.post<ExpenseDetail>(`/api/expenses/${id}/confirm`);
  return res.data;
}

// Every aggregate is grouped by currency alongside its own dimension — never
// summed across different currencies into one number.
export interface CurrencyAmount {
  currency: string | null;
  total: string;
}

export interface CategoryBreakdown {
  category: string;
  currency: string | null;
  total: string;
  count: number;
}

export interface MonthlyBreakdown {
  month: string; // "YYYY-MM"
  currency: string | null;
  total: string;
}

export interface DashboardSummary {
  month_to_date: CurrencyAmount[];
  receipt_count: number;
  by_category: CategoryBreakdown[];
  by_month: MonthlyBreakdown[];
}

export async function getDashboardSummary(months = 12): Promise<DashboardSummary> {
  const res = await api.get<DashboardSummary>("/api/dashboard/summary", { params: { months } });
  return res.data;
}

export type ExportFormat = "csv" | "xlsx";

const DEFAULT_EXPORT_FILENAME: Record<ExportFormat, string> = {
  csv: "expensa-expenses.csv",
  xlsx: "expensa-expenses.xlsx",
};

// GET /api/export requires the same bearer auth as every other endpoint, so
// a plain <a href="/api/export"> can't be used (no way to attach the
// Authorization header) — instead we fetch as a blob and hand the browser a
// synthetic download via an object URL.
export async function exportExpenses(
  format: ExportFormat,
  sort: SortOption,
  filters: ExpenseFilters,
): Promise<void> {
  const res = await api.get<Blob>("/api/export", {
    responseType: "blob",
    params: {
      format,
      sort,
      status: filters.status,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
      category: filters.category,
      q: filters.q,
    },
  });

  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename = disposition?.match(/filename="([^"]+)"/)?.[1] ?? DEFAULT_EXPORT_FILENAME[format];

  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
