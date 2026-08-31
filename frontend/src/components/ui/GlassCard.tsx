import type { HTMLAttributes } from "react";

type GlassCardVariant = "default" | "auth" | "danger" | "small";

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: GlassCardVariant;
}

// The single most-reused visual pattern in the design: a translucent,
// blurred panel. `variant` covers the few real deviations (the auth card's
// stronger blur/shadow, the danger-zone's rose tint, the smaller radius
// used for compact state cards) rather than exposing every CSS knob.
const VARIANT_CLASSES: Record<GlassCardVariant, string> = {
  default:
    "bg-white/[0.62] backdrop-blur-xl backdrop-saturate-150 border border-white/80 shadow-glass rounded-[22px]",
  auth: "bg-white/60 backdrop-blur-2xl backdrop-saturate-150 border border-white/80 shadow-glass-lg rounded-[26px]",
  danger:
    "bg-rose-600/5 backdrop-blur-xl border border-rose-600/[0.22] shadow-glass rounded-[22px]",
  small: "bg-white/[0.55] border border-white/80 shadow-glass rounded-[20px]",
};

export function GlassCard({ variant = "default", className = "", ...props }: GlassCardProps) {
  return <div className={`${VARIANT_CLASSES[variant]} ${className}`.trim()} {...props} />;
}
