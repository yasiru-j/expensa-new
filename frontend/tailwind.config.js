import defaultTheme from "tailwindcss/defaultTheme";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand palette from the Claude Design mockup (Design /Expensa System
        // Design/Expensa.dc.html) — `ink` gets Tailwind's automatic /opacity
        // modifiers for free (e.g. `border-ink-900/10`).
        ink: {
          900: "#131a3a",
          600: "#5a6285",
          400: "#7a83a6",
          300: "#9aa2c0",
        },
        brand: {
          blue: "#2f6bf6",
          purple: "#4b32e0",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', ...defaultTheme.fontFamily.sans],
        mono: ['"JetBrains Mono"', ...defaultTheme.fontFamily.mono],
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg,#2f6bf6,#4b32e0)",
      },
      boxShadow: {
        glass: "0 1px 0 rgba(255,255,255,0.9) inset, 0 20px 44px -26px rgba(30,41,120,0.4)",
        "glass-lg": "0 1px 0 rgba(255,255,255,0.95) inset, 0 30px 70px -28px rgba(30,41,120,0.38)",
        brand: "0 14px 28px -14px rgba(47,80,230,0.85)",
        danger: "0 14px 28px -14px rgba(225,29,72,0.8)",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(14px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pop: {
          from: { opacity: "0", transform: "translateY(18px) scale(0.985)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        rise: "rise 0.5s cubic-bezier(0.2,0.7,0.2,1) both",
        pop: "pop 0.28s cubic-bezier(0.2,0.7,0.2,1) both",
      },
    },
  },
  plugins: [],
};
