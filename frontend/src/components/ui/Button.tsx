import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "border-none bg-brand-gradient text-white shadow-brand hover:brightness-[1.07] disabled:opacity-40 disabled:hover:brightness-100",
  secondary: "border border-ink-900/10 bg-white/70 text-ink-900 hover:bg-white disabled:opacity-40",
  ghost: "border-none bg-transparent p-0 text-brand-blue hover:underline disabled:opacity-40",
  destructive:
    "border-none bg-rose-600 text-white shadow-danger hover:brightness-[1.05] disabled:cursor-not-allowed disabled:bg-ink-900/5 disabled:text-ink-300 disabled:shadow-none",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-11 px-4 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: ButtonProps) {
  const shape = variant === "ghost" ? "" : "rounded-xl font-semibold";
  const sizing = variant === "ghost" ? "" : SIZE_CLASSES[size];
  return (
    <button
      className={`inline-flex cursor-pointer items-center justify-center gap-2 transition ${shape} ${sizing} ${VARIANT_CLASSES[variant]} ${className}`.trim()}
      {...props}
    />
  );
}
