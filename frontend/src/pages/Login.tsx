import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AuthHeader } from "../components/AuthHeader";
import { Footer } from "../components/Footer";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { FIELD_INPUT, FIELD_LABEL } from "../lib/formStyles";
import { useAuth } from "../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch {
      setError("Incorrect email or password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <AuthHeader />
      <main className="flex flex-1 items-center justify-center px-4 pb-16 pt-2">
        <div className="w-full max-w-[440px] animate-rise">
          <GlassCard variant="auth" className="p-8 sm:p-9">
            <img
              src="/expensa-logo.png"
              alt="Expensa"
              className="mx-auto -mt-3 mb-1.5 block h-24 w-24 object-cover"
            />
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <h1 className="text-[23px] font-bold tracking-tight text-ink-900">
                  Log in to Expensa
                </h1>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-600">
                  Enter your email below to get back to your receipts.
                </p>
              </div>
              <Link
                to="/signup"
                className="mt-1 flex-none text-sm font-semibold text-brand-blue hover:underline"
              >
                Sign up
              </Link>
            </div>

            {error && (
              <div className="mb-4 flex items-start gap-2.5 rounded-2xl border border-rose-600/[0.24] bg-rose-600/[0.08] px-3.5 py-2.5">
                <span className="mt-1.5 h-[7px] w-[7px] flex-none rounded-full bg-rose-600" />
                <p className="text-[13px] font-medium leading-relaxed text-rose-800">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className={FIELD_LABEL}>
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={FIELD_INPUT}
                />
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className={FIELD_LABEL}>
                    Password
                  </label>
                  <Link
                    to="/reset-password"
                    className="text-[13px] text-ink-600 hover:text-brand-blue hover:underline"
                  >
                    Forgot your password?
                  </Link>
                </div>
                <input
                  id="password"
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={FIELD_INPUT}
                />
              </div>

              <div className="flex flex-col gap-2.5 pt-2">
                <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full">
                  {isSubmitting ? "Logging in…" : "Log in"}
                </Button>
                <a
                  href={`${API_BASE_URL}/api/auth/google`}
                  className="flex h-11 w-full items-center justify-center rounded-xl border border-ink-900/[0.12] bg-white/50 text-sm font-semibold text-ink-900 hover:bg-white/85"
                >
                  Continue with Google
                </a>
              </div>
            </form>
          </GlassCard>

          <div className="mt-5 flex justify-center gap-4 text-xs text-ink-600">
            <Link to="/privacy" className="hover:text-ink-900 hover:underline">
              Privacy Policy
            </Link>
            <Link to="/terms" className="hover:text-ink-900 hover:underline">
              Terms of Service
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
