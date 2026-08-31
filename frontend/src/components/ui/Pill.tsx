import type { ReactNode } from "react";

type PillTone = "success" | "warning" | "danger" | "neutral";

interface PillProps {
  tone?: PillTone;
  dot?: boolean;
  children: ReactNode;
  className?: string;
  title?: string;
}

const TONE_CLASSES: Record<PillTone, string> = {
  success: "bg-emerald-600/10 text-emerald-700",
  warning: "bg-amber-500/[0.13] text-amber-700",
  danger: "bg-rose-600/10 text-rose-700",
  neutral: "bg-ink-900/[0.055] text-ink-600",
};

const DOT_CLASSES: Record<PillTone, string> = {
  success: "bg-emerald-600",
  warning: "bg-amber-500",
  danger: "bg-rose-600",
  neutral: "bg-ink-400",
};

// The small status-dot + label pattern reused for expense status
// (confirmed/needs-review), duplicate warnings, and field-confidence
// badges throughout the table, dashboard, and detail modal.
export function Pill({ tone = "neutral", dot = true, children, className = "", title }: PillProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${TONE_CLASSES[tone]} ${className}`.trim()}
    >
      {dot && <span className={`h-1.5 w-1.5 flex-none rounded-full ${DOT_CLASSES[tone]}`} />}
      {children}
    </span>
  );
}
