import { Link } from "react-router-dom";

// Placeholder — replace with a real support address before deploying.
const CONTACT_EMAIL = "support@expensa.app";

export function PrivacyPolicy() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12 text-sm text-gray-700">
      <Link to="/" className="text-gray-500 hover:underline">
        ← Back
      </Link>
      <h1 className="mb-2 mt-4 text-2xl font-semibold text-gray-900">Privacy Policy</h1>
      <p className="mb-8 text-gray-500">Last updated: 30 August 2026.</p>

      <div className="space-y-8">
        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">What we collect</h2>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Account details:</strong> your email address, and a bcrypt hash of your
              password (never the password itself). If you sign in with Google instead, we
              receive your Google account email and don't store a password at all.
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
          <h2 className="mb-2 text-lg font-medium text-gray-900">
            Receipts are sent to OpenAI
          </h2>
          <p>
            Every receipt image you upload — or, for a multi-page PDF, an image rendered from its
            first page — is sent to OpenAI's API so it can automatically read the vendor, date,
            and amounts off it. This is how the extraction feature works; there's no way to use it
            without that step. We don't send your email, password, or any other account data to
            OpenAI — only the receipt image itself. OpenAI processes that image under its own API
            terms, separate from this policy.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">How we use your data</h2>
          <p>
            Solely to run the expense-tracking features you're using: storing and displaying your
            receipts, extracting data from them, building your spending dashboard, and enforcing
            usage limits. We don't sell your data or use it for advertising.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Data isolation</h2>
          <p>
            Every query the app makes is scoped to your account at the database level (Postgres
            row-level security), not just in application code — so even a bug in a query can't
            surface another user's rows.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Deleting your data</h2>
          <p>
            You can permanently delete your account at any time from{" "}
            <Link to="/account" className="text-blue-600 underline">
              Account
            </Link>
            . This immediately and permanently removes every expense record, line item, uploaded
            receipt file, and usage record we hold for you — there's no recovery period, and
            support can't undo it after the fact.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Contact</h2>
          <p>
            Questions about this policy: <a href={`mailto:${CONTACT_EMAIL}`} className="text-blue-600 underline">{CONTACT_EMAIL}</a>.
          </p>
        </section>
      </div>
    </main>
  );
}
