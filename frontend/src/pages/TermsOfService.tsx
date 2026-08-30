import { Link } from "react-router-dom";

// Placeholder — replace with a real support address before deploying.
const CONTACT_EMAIL = "support@expensa.app";

export function TermsOfService() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-12 text-sm text-gray-700">
      <Link to="/" className="text-gray-500 hover:underline">
        ← Back
      </Link>
      <h1 className="mb-2 mt-4 text-2xl font-semibold text-gray-900">Terms of Service</h1>
      <p className="mb-8 text-gray-500">Last updated: 30 August 2026.</p>

      <div className="space-y-8">
        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">The service</h2>
          <p>
            Expensa lets you upload receipts and invoices, automatically extracts vendor, date,
            and amount data from them using an AI vision model, and gives you a dashboard of your
            spending. By creating an account, you agree to these terms and to our{" "}
            <Link to="/privacy" className="text-blue-600 underline">
              Privacy Policy
            </Link>
            .
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Your account</h2>
          <p>
            You're responsible for keeping your login credentials secure and for all activity
            under your account. Use a real email address you control — it's how you authenticate
            and how we'd contact you about your account.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Acceptable use</h2>
          <p>You agree not to:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Upload files that aren't genuine receipts or invoices, or that you don't have the right to process.</li>
            <li>Attempt to bypass upload size limits, rate limits, or monthly extraction quotas.</li>
            <li>Use the service to store or transmit unlawful content.</li>
            <li>Attempt to access another user's data or interfere with the service's operation.</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">AI extraction is automated, not audited</h2>
          <p>
            Vendor, date, and amount fields are read off your receipts by an AI model and may be
            wrong — a low-confidence field is flagged in the app for you to check. Review and
            correct extracted data before relying on it for accounting, reimbursement, or tax
            purposes. We aren't liable for decisions made on unreviewed extracted data.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Your content</h2>
          <p>
            You retain ownership of the receipts and data you upload. You grant us the limited
            right to store, process, and display it back to you in order to run the service —
            including sending receipt images to OpenAI for extraction, as described in our{" "}
            <Link to="/privacy" className="text-blue-600 underline">
              Privacy Policy
            </Link>
            .
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Availability</h2>
          <p>
            The service is provided "as is," without uptime guarantees. Features may change or be
            discontinued.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Ending your account</h2>
          <p>
            You may delete your account at any time from Account settings, which permanently
            removes your data as described in our{" "}
            <Link to="/privacy" className="text-blue-600 underline">
              Privacy Policy
            </Link>
            . We may suspend or terminate accounts that violate the acceptable-use terms above.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Changes to these terms</h2>
          <p>
            If we make material changes, we'll update the "last updated" date above. Continued use
            of the service after a change means you accept the updated terms.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Contact</h2>
          <p>
            Questions about these terms: <a href={`mailto:${CONTACT_EMAIL}`} className="text-blue-600 underline">{CONTACT_EMAIL}</a>.
          </p>
        </section>
      </div>
    </div>
  );
}
