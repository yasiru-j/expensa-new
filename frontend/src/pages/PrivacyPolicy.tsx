import { Link } from "react-router-dom";

import { GlassCard } from "../components/ui/GlassCard";

const CONTACT_EMAIL = "hi@yasiruj.com";

export function PrivacyPolicy() {
  return (
    <main className="mx-auto max-w-[760px] px-4 py-10 sm:py-14">
      <Link to="/" className="text-sm text-ink-600 hover:text-ink-900 hover:underline">
        ← Back
      </Link>
      <GlassCard variant="auth" className="mt-4 p-6 sm:p-11">
        <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-600">
          Last updated 30 August 2026
        </div>
        <h1 className="mt-2.5 text-[26px] font-bold tracking-tight text-ink-900 sm:text-[30px]">
          Privacy Policy
        </h1>
        <div className="my-6 h-px bg-ink-900/[0.08]" />

        <div className="flex flex-col gap-6 text-sm text-ink-900">
          <section>
            <h2 className="mb-2 text-base font-bold tracking-tight text-ink-900">
              What we collect
            </h2>
            <ul className="list-disc space-y-2 pl-5 leading-relaxed text-ink-900/90">
              <li>
                <strong>Account details:</strong> your email address, and a bcrypt hash of your
                password (never the password itself). If you sign in with Google instead, we receive
                your Google account email and don't store a password at all.
              </li>
              <li>
                <strong>Receipts you upload:</strong> the original image or PDF file, stored in our
                object storage.
              </li>
              <li>
                <strong>Extracted expense data:</strong> vendor, date, amounts, currency, category,
                payment method, and line items — read automatically off each receipt, and editable
                by you afterward.
              </li>
              <li>
                <strong>Usage counts:</strong> how many receipts you've had processed this month, so
                we can enforce your plan's monthly limit.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-base font-bold tracking-tight text-ink-900">
              Receipts are sent to OpenAI
            </h2>
            <p className="leading-relaxed text-ink-900/90">
              Every receipt image you upload — or, for a multi-page PDF, an image rendered from its
              first page — is sent to OpenAI's API so it can automatically read the vendor, date,
              and amounts off it. This is how the extraction feature works; there's no way to use it
              without that step. We don't send your email, password, or any other account data to
              OpenAI — only the receipt image itself. OpenAI processes that image under its own API
              terms, separate from this policy.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-base font-bold tracking-tight text-ink-900">
              How we use your data
            </h2>
            <p className="leading-relaxed text-ink-900/90">
              Solely to run the expense-tracking features you're using: storing and displaying your
              receipts, extracting data from them, building your spending dashboard, and enforcing
              usage limits. We don't sell your data or use it for advertising.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-base font-bold tracking-tight text-ink-900">Data isolation</h2>
            <p className="leading-relaxed text-ink-900/90">
              Every query the app makes is scoped to your account at the database level (Postgres
              row-level security), not just in application code — so even a bug in a query can't
              surface another user's rows.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-base font-bold tracking-tight text-ink-900">
              Deleting your data
            </h2>
            <p className="leading-relaxed text-ink-900/90">
              You can permanently delete your account at any time from{" "}
              <Link to="/account" className="font-medium text-brand-blue underline">
                Account
              </Link>
              . This immediately and permanently removes every expense record, line item, uploaded
              receipt file, and usage record we hold for you — there's no recovery period, and
              support can't undo it after the fact.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-base font-bold tracking-tight text-ink-900">Contact</h2>
            <p className="leading-relaxed text-ink-900/90">
              Questions about this policy:{" "}
              <a href={`mailto:${CONTACT_EMAIL}`} className="font-medium text-brand-blue underline">
                {CONTACT_EMAIL}
              </a>
              .
            </p>
          </section>
        </div>
      </GlassCard>
    </main>
  );
}
