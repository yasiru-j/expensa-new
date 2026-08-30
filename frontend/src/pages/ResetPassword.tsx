import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../lib/api";

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  return token ? <ConfirmResetForm token={token} /> : <RequestResetForm />;
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
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-semibold text-gray-900">Reset your password</h1>

        {message ? (
          <p className="text-center text-sm text-gray-600">{message}</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:border-gray-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-gray-900 px-3 py-2 text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}

        <p className="text-center text-sm text-gray-500">
          <Link to="/login" className="hover:underline">
            Back to log in
          </Link>
        </p>
      </div>
    </main>
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
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-semibold text-gray-900">Set a new password</h1>

        {status === "success" ? (
          <p className="text-center text-sm text-gray-600">
            Password updated.{" "}
            <Link to="/login" className="hover:underline">
              Log in
            </Link>
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                New password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:border-gray-500 focus:outline-none"
              />
            </div>

            {status === "error" && (
              <p className="text-sm text-red-600">
                That reset link is invalid or has expired.
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-gray-900 px-3 py-2 text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Updating…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
