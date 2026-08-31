import { Link, Outlet, useLocation } from "react-router-dom";

import { initialsFor } from "../lib/initials";
import { useAuth } from "../lib/auth";
import { Footer } from "./Footer";

function NavPill({ to, active, children }: { to: string; active: boolean; children: string }) {
  return (
    <Link
      to={to}
      className={`rounded-lg px-3.5 py-2 text-sm font-semibold transition ${
        active ? "bg-white/85 text-ink-900" : "text-ink-400 hover:text-ink-900"
      }`}
    >
      {children}
    </Link>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-white/70 bg-white/60 shadow-glass backdrop-blur-xl backdrop-saturate-150">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-5 px-5 py-3 sm:px-7">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5">
              <img
                src="/expensa-logo.png"
                alt=""
                className="h-8 w-8 rounded-[10px] object-cover shadow-brand"
              />
              <span className="text-lg font-extrabold tracking-tight text-ink-900">Expensa</span>
            </Link>
            {user && (
              <nav className="hidden gap-1 sm:flex">
                <NavPill to="/" active={location.pathname === "/"}>
                  Dashboard
                </NavPill>
                <NavPill to="/account" active={location.pathname === "/account"}>
                  Account
                </NavPill>
              </nav>
            )}
          </div>
          {user && (
            <div className="flex items-center gap-3">
              <Link
                to="/account"
                className="flex h-[34px] items-center gap-2 rounded-full border border-ink-900/[0.09] bg-white/60 py-0 pl-[5px] pr-3 hover:bg-white"
              >
                <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-brand-gradient text-[11px] font-bold text-white">
                  {initialsFor(user.full_name, user.email)}
                </span>
                <span className="hidden text-sm font-medium text-ink-900 md:inline">
                  {user.email}
                </span>
              </Link>
              <button
                onClick={() => void logout()}
                className="h-[34px] whitespace-nowrap rounded-full border border-ink-900/10 px-3.5 text-sm font-semibold text-ink-600 hover:bg-white/70 hover:text-ink-900"
              >
                Log out
              </button>
            </div>
          )}
        </div>
        {user && (
          <nav className="flex gap-1 border-t border-white/60 px-5 py-2 sm:hidden">
            <NavPill to="/" active={location.pathname === "/"}>
              Dashboard
            </NavPill>
            <NavPill to="/account" active={location.pathname === "/account"}>
              Account
            </NavPill>
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-[1320px] flex-1 px-5 py-7 sm:px-7 sm:py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
