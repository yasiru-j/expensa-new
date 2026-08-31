import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AuthHeader } from "../components/AuthHeader";
import { Footer } from "../components/Footer";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { FIELD_INPUT, FIELD_LABEL } from "../lib/formStyles";
import { api } from "../lib/api";

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  return (
    <div className="flex min-h-screen flex-col">
      <AuthHeader />
      <main className="flex flex-1 items-center justify-center px-4 pb-10 pt-2">
        <div className="w-full max-w-[440px] animate-rise">
          {token ? <ConfirmResetForm token={token} /> : <RequestResetForm />}
        </div>
      </main>
      <Footer />
    </div>
  );
}

function RequestResetForm() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.post("/api/auth/password-reset/request", { email });
      setMessage("If that email is registered, a reset link has been sent.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <GlassCard variant="auth" className="p-8 sm:p-9">
      <h1 className="text-[23px] font-bold tracking-tight text-ink-900">Reset your password</h1>
      <p className="mb-6 mt-1.5 text-sm leading-relaxed text-ink-600">
        We will email you a link that stays valid for 30 minutes.
      </p>

      {message && (
        <div className="mb-5 flex items-start gap-2.5 rounded-2xl border border-emerald-600/[0.26] bg-emerald-600/[0.09] px-3.5 py-3">
          <span className="mt-1.5 h-[7px] w-[7px] flex-none rounded-full bg-emerald-600" />
          <p className="text-[13px] font-medium leading-relaxed text-emerald-800">{message}</p>
        </div>
      )}

      {!message && (
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

          <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full">
            {isSubmitting ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}

      <p className="mt-5 text-center text-sm text-ink-600">
        <Link to="/login" className="font-semibold text-brand-blue hover:underline">
          Back to log in
        </Link>
      </p>
    </GlassCard>
  );
}

function ConfirmResetForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.post("/api/auth/password-reset/confirm", { token, new_password: password });
      setStatus("success");
    } catch {
      setStatus("error");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <GlassCard variant="auth" className="p-8 sm:p-9">
      <div className="mb-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-600">
        Secure link verified
      </div>
      <h1 className="text-[23px] font-bold tracking-tight text-ink-900">Set a new password</h1>

      {status === "success" ? (
        <p className="mt-5 text-center text-sm text-ink-600">
          Password updated.{" "}
          <Link to="/login" className="font-semibold text-brand-blue hover:underline">
            Log in
          </Link>
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label htmlFor="password" className={FIELD_LABEL}>
              New password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={FIELD_INPUT}
            />
          </div>

          {status === "error" && (
            <div className="flex items-start gap-2.5 rounded-2xl border border-rose-600/[0.24] bg-rose-600/[0.08] px-3.5 py-2.5">
              <span className="mt-1.5 h-[7px] w-[7px] flex-none rounded-full bg-rose-600" />
              <p className="text-[13px] font-medium leading-relaxed text-rose-800">
                That reset link is invalid or has expired.
              </p>
            </div>
          )}

          <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full">
            {isSubmitting ? "Updating…" : "Update password"}
          </Button>
        </form>
      )}
    </GlassCard>
  );
}
