// Shared Tailwind class strings for form controls across the auth pages and
// Account — kept as plain constants (not a component) since inputs differ
// enough in wrapping markup (icons, error states) that a wrapper component
// would need almost as many props as it saves lines.
export const FIELD_LABEL = "block text-sm font-semibold text-ink-900";
export const FIELD_INPUT =
  "mt-1.5 h-11 w-full rounded-[13px] border border-ink-900/[0.12] bg-white/70 px-3.5 text-sm text-ink-900 transition";
