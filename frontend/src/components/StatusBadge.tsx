import { Pill } from "./ui/Pill";
import type { ExpenseStatus } from "../lib/expenses";

const TONE: Record<ExpenseStatus, "success" | "warning" | "danger" | "neutral"> = {
  pending: "neutral",
  processing: "neutral",
  ready: "warning", // extracted, awaiting confirmation — "needs review"
  confirmed: "success",
  failed: "danger",
};

const LABEL: Record<ExpenseStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  ready: "Needs review",
  confirmed: "Confirmed",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: ExpenseStatus }) {
  return (
    <Pill tone={TONE[status]} className="whitespace-nowrap">
      {LABEL[status]}
    </Pill>
  );
}
