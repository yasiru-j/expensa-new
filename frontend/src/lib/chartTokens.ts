// Light-mode chart tokens, matching the validated default palette. The rest
// of Expensa has no dark-mode support anywhere (every existing component
// uses fixed light Tailwind classes), so charts intentionally stay
// light-only too rather than being the one dark-aware surface in the app.
export const CHART_COLORS = {
  primary: "#2a78d6", // categorical slot 1 (blue) — the single hue for magnitude encoding
  surface: "#fcfcfb",
  textPrimary: "#0b0b0b",
  textSecondary: "#52514e",
  muted: "#898781",
  gridline: "#e1e0d9",
  baseline: "#c3c2b7",
} as const;
