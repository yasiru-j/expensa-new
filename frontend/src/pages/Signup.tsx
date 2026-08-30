import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { isAxiosError } from "axios";

import { Footer } from "../components/Footer";
import { useAuth } from "../lib/auth";

export function Signup() {
  const { signup } = useAuth();
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
      await signup(email, password);
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
    <div className="flex min-h-screen flex-col bg-gray-50">
      <main className="flex flex-1 items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-6">
          <h1 className="text-center text-2xl font-semibold text-gray-900">Create your account</h1>

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

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
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
              <p className="mt-1 text-xs text-gray-500">At least 8 characters.</p>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-gray-900 px-3 py-2 text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Creating account…" : "Sign up"}
            </button>
          </form>

          <p className="text-center text-xs text-gray-600">
            By signing up, you agree to our{" "}
            <Link to="/terms" className="hover:underline">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link to="/privacy" className="hover:underline">
              Privacy Policy
            </Link>
            , including that uploaded receipts are sent to OpenAI for extraction.
          </p>

          <p className="text-center text-sm text-gray-500">
            Already have an account?{" "}
            <Link to="/login" className="hover:underline">
              Log in
            </Link>
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
