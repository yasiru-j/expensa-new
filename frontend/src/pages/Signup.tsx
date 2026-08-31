import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { isAxiosError } from "axios";

import { AuthHeader } from "../components/AuthHeader";
import { Footer } from "../components/Footer";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { FIELD_INPUT, FIELD_LABEL } from "../lib/formStyles";
import { useAuth } from "../lib/auth";

// Purely cosmetic strength cue derived from length — real enforcement
// (min 8 chars) is server-side (Pydantic) and via the input's minLength.
function passwordBarColor(len: number, threshold: number, color: string): string {
  return len >= threshold ? color : "rgba(19,26,58,0.1)";
}

export function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await signup(email, password, fullName);
      navigate("/", { replace: true });
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) {
        setError("An account with that email already exists.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <AuthHeader />
      <main className="flex flex-1 items-center justify-center px-4 pb-10 pt-2">
        <div className="w-full max-w-[440px] animate-rise">
          <GlassCard variant="auth" className="p-8 sm:p-9">
            <h1 className="text-[23px] font-bold tracking-tight text-ink-900">
              Create your account
            </h1>
            <p className="mb-6 mt-1.5 text-sm leading-relaxed text-ink-600">
              Free while you log your first 50 receipts.
            </p>

            {error && (
              <div className="mb-4 flex items-start gap-2.5 rounded-2xl border border-rose-600/[0.24] bg-rose-600/[0.08] px-3.5 py-2.5">
                <span className="mt-1.5 h-[7px] w-[7px] flex-none rounded-full bg-rose-600" />
                <p className="text-[13px] font-medium leading-relaxed text-rose-800">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="fullName" className={FIELD_LABEL}>
                  Full name <span className="font-normal text-ink-600">(optional)</span>
                </label>
                <input
                  id="fullName"
                  type="text"
                  placeholder="Alex Nguyen"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className={FIELD_INPUT}
                />
              </div>

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
                <label htmlFor="password" className={FIELD_LABEL}>
                  Password
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
                <div className="mt-1.5 flex gap-1.5">
                  <div
                    className="h-1 flex-1 rounded-full"
                    style={{ background: passwordBarColor(password.length, 1, "#f59e0b") }}
                  />
                  <div
                    className="h-1 flex-1 rounded-full"
                    style={{ background: passwordBarColor(password.length, 8, "#2f6bf6") }}
                  />
                  <div
                    className="h-1 flex-1 rounded-full"
                    style={{ background: passwordBarColor(password.length, 12, "#059669") }}
                  />
                </div>
              </div>

              <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "Creating account…" : "Create account"}
              </Button>
            </form>

            <p className="mt-5 text-center text-xs leading-relaxed text-ink-600">
              By signing up, you agree to our{" "}
              <Link to="/terms" className="font-medium text-brand-blue hover:underline">
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link to="/privacy" className="font-medium text-brand-blue hover:underline">
                Privacy Policy
              </Link>
              , including that uploaded receipts are sent to OpenAI for extraction.
            </p>

            <p className="mt-4 text-center text-sm text-ink-600">
              Already have an account?{" "}
              <Link to="/login" className="font-semibold text-brand-blue hover:underline">
                Log in
              </Link>
            </p>
          </GlassCard>
        </div>
      </main>
      <Footer />
    </div>
  );
}
