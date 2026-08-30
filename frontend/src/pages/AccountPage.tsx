import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { StatTile } from "../components/StatTile";
import { deleteAccount, getUsage, type UsageRead } from "../lib/account";
import { useAuth } from "../lib/auth";

const DELETE_CONFIRMATION_TEXT = "DELETE";

export function AccountPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [usage, setUsage] = useState<UsageRead | null>(null);
  const [isUsageLoading, setIsUsageLoading] = useState(true);

  const [confirmText, setConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getUsage()
      .then((data) => {
        if (!cancelled) setUsage(data);
      })
      .finally(() => {
        if (!cancelled) setIsUsageLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleDeleteAccount() {
    setDeleteError(null);
    setIsDeleting(true);
    try {
      await deleteAccount();
      // The backend already cleared the refresh cookie; drop the in-memory
      // session state the same way a normal logout would.
      await logout().catch(() => {});
      navigate("/login", { replace: true });
    } catch {
      setDeleteError("Couldn't delete your account. Please try again.");
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-gray-900">Account</h1>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-gray-900">Profile</h2>
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700">
          {user?.email}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-gray-900">Usage this month</h2>
        {isUsageLoading ? (
          <div className="rounded-lg border border-gray-200 p-10 text-center text-gray-400">
            Loading…
          </div>
        ) : usage ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatTile label="Receipts extracted" value={String(usage.extraction_count)} />
            <StatTile label="Monthly limit" value={String(usage.monthly_limit)} />
            <StatTile label="Remaining" value={String(usage.remaining)} />
          </div>
        ) : (
          <p className="text-sm text-gray-400">Couldn't load usage.</p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-red-700">Danger zone</h2>
        <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-800">
            Deleting your account permanently removes every expense, receipt file, and usage
            record. This can't be undone.
          </p>
          <div>
            <label htmlFor="delete-confirm" className="block text-sm font-medium text-red-800">
              Type {DELETE_CONFIRMATION_TEXT} to confirm
            </label>
            <input
              id="delete-confirm"
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="mt-1 w-full max-w-xs rounded-md border border-red-300 px-3 py-2 focus:border-red-500 focus:outline-none"
            />
          </div>
          {deleteError && <p className="text-sm text-red-600">{deleteError}</p>}
          <button
            onClick={() => void handleDeleteAccount()}
            disabled={confirmText !== DELETE_CONFIRMATION_TEXT || isDeleting}
            className="rounded-md bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-40"
          >
            {isDeleting ? "Deleting…" : "Delete my account"}
          </button>
        </div>
      </section>
    </div>
  );
}
