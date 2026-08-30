import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-center gap-4 px-6 py-4 text-xs text-gray-600">
        <Link to="/privacy" className="hover:text-gray-900 hover:underline">
          Privacy Policy
        </Link>
        <span aria-hidden="true">·</span>
        <Link to="/terms" className="hover:text-gray-900 hover:underline">
          Terms of Service
        </Link>
      </div>
    </footer>
  );
}
