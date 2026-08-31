import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-white/70 bg-white/50 backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex max-w-[1320px] items-center justify-center gap-4 px-6 py-4 text-xs text-ink-600">
        <Link to="/privacy" className="hover:text-ink-900 hover:underline">
          Privacy Policy
        </Link>
        <span aria-hidden="true">·</span>
        <Link to="/terms" className="hover:text-ink-900 hover:underline">
          Terms of Service
        </Link>
      </div>
    </footer>
  );
}
