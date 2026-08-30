import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { Footer } from "./Footer";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold text-gray-900">
            Expensa
          </Link>
          {user && (
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <Link to="/account" className="hover:underline">
                {user.email}
              </Link>
              <button
                onClick={() => void logout()}
                className="rounded-md border border-gray-300 px-3 py-1.5 hover:bg-gray-100"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
