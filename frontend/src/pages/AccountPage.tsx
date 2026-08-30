import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { StatTile } from "../components/StatTile";
import { deleteAccount, getUsage, updateAccount, type UsageRead } from "../lib/account";
import { useAuth } from "../lib/auth";

const DELETE_CONFIRMATION_TEXT = "DELETE";

export function AccountPage() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [usage, setUsage] = useState<UsageRead | null>(null);
  const [isUsageLoading, setIsUsageLoading] = useState(true);

  const [fullName, setFullName] = useState("");
  const [isSavingName, setIsSavingName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);

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

  // Seed the editable field from the loaded user, once — not on every
  // `user` change, so the input doesn't get clobbered mid-edit by the
  // refreshUser() call this same form triggers on save.
  useEffect(() => {
    if (user) setFullName(user.full_name ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user === null]);

  const isNameDirty = fullName.trim() !== (user?.full_name ?? "");

  async function handleSaveName() {
    setNameError(null);
    setNameSaved(false);
    setIsSavingName(true);
    try {
      await updateAccount(fullName.trim() || null);
      await refreshUser();
      setNameSaved(true);
    } catch {
      setNameError("Couldn't save your name. Please try again.");
    } finally {
      setIsSavingName(false);
    }
  }

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
        <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
          <div>
            <span className="block text-xs font-medium text-gray-500">Email</span>
            <p className="text-sm text-gray-700">{user?.email}</p>
          </div>

          <div>
            <label htmlFor="full-name" className="block text-xs font-medium text-gray-500">
              Full name
            </label>
            <div className="mt-1 flex max-w-sm items-center gap-2">
              <input
                id="full-name"
                type="text"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  setNameSaved(false);
                }}
                placeholder="Not set"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
              />
              <button
                onClick={() => void handleSaveName()}
                disabled={!isNameDirty || isSavingName}
                className="whitespace-nowrap rounded-md bg-gray-900 px-3 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-40"
              >
                {isSavingName ? "Saving…" : "Save"}
              </button>
            </div>
            {nameError && <p className="mt-1 text-sm text-red-600">{nameError}</p>}
            {nameSaved && !isNameDirty && <p className="mt-1 text-sm text-green-700">Saved.</p>}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-gray-900">Usage this month</h2>
        {isUsageLoading ? (
          <div className="rounded-lg border border-gray-200 p-10 text-center text-gray-600">
            Loading…
          </div>
        ) : usage ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatTile label="Receipts extracted" value={String(usage.extraction_count)} />
            <StatTile label="Monthly limit" value={String(usage.monthly_limit)} />
            <StatTile label="Remaining" value={String(usage.remaining)} />
          </div>
        ) : (
          <p className="text-sm text-gray-600">Couldn't load usage.</p>
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
