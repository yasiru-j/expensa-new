import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { StatTile } from "../components/StatTile";
import { deleteAccount, getUsage, updateAccount, type UsageRead } from "../lib/account";
import { useAuth } from "../lib/auth";
import { FIELD_INPUT, FIELD_LABEL } from "../lib/formStyles";
import { initialsFor } from "../lib/initials";

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

  const memberSince = user
    ? new Date(user.created_at).toLocaleDateString(undefined, { month: "long", year: "numeric" })
    : null;

  return (
    <div className="space-y-8">
      <h1 className="text-[28px] font-bold tracking-tight text-ink-900 sm:text-[31px]">Account</h1>

      <section className="space-y-3">
        <GlassCard className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex h-14 w-14 flex-none items-center justify-center rounded-2xl bg-brand-gradient text-lg font-bold text-white shadow-brand">
              {user ? initialsFor(user.full_name, user.email) : ""}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-lg font-bold tracking-tight text-ink-900">
                {user?.full_name || user?.email}
              </div>
              <div className="mt-0.5 truncate text-[13.5px] text-ink-600">
                {user?.email}
                {memberSince && ` · Member since ${memberSince}`}
              </div>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            <div>
              <label htmlFor="full-name" className={FIELD_LABEL}>
                Full name
              </label>
              <div className="mt-1.5 flex items-center gap-2">
                <input
                  id="full-name"
                  type="text"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    setNameSaved(false);
                  }}
                  placeholder="Not set"
                  className={`${FIELD_INPUT} !mt-0`}
                />
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => void handleSaveName()}
                  disabled={!isNameDirty || isSavingName}
                >
                  {isSavingName ? "Saving…" : "Save"}
                </Button>
              </div>
              {nameError && <p className="mt-1.5 text-sm text-rose-600">{nameError}</p>}
              {nameSaved && !isNameDirty && (
                <p className="mt-1.5 text-sm text-emerald-700">Saved.</p>
              )}
            </div>
            <div>
              <span className={FIELD_LABEL}>Email</span>
              <p className={`${FIELD_INPUT} flex items-center !text-ink-600`}>{user?.email}</p>
            </div>
          </div>
        </GlassCard>
      </section>

      <section className="space-y-3">
        <h2 className="text-[15.5px] font-bold tracking-tight text-ink-900">Usage this month</h2>
        {isUsageLoading ? (
          <div className="rounded-[22px] border border-white/80 bg-white/[0.62] p-10 text-center text-ink-600 shadow-glass">
            Loading…
          </div>
        ) : usage ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatTile label="Receipts extracted" value={String(usage.extraction_count)} />
            <StatTile label="Monthly limit" value={String(usage.monthly_limit)} />
            <StatTile label="Remaining" value={String(usage.remaining)} />
          </div>
        ) : (
          <p className="text-sm text-ink-600">Couldn't load usage.</p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-[15.5px] font-bold tracking-tight text-rose-700">Danger zone</h2>
        <GlassCard variant="danger" className="p-5 sm:p-6">
          <p className="max-w-[560px] text-[13.5px] leading-relaxed text-ink-600">
            Deleting your account permanently removes every expense, receipt file, and usage record.
            This can&rsquo;t be undone. Type{" "}
            <span className="font-mono font-medium text-rose-800">{DELETE_CONFIRMATION_TEXT}</span>{" "}
            to confirm.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <label htmlFor="delete-confirm" className="sr-only">
              Type {DELETE_CONFIRMATION_TEXT} to confirm
            </label>
            <input
              id="delete-confirm"
              type="text"
              placeholder="DELETE"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="h-[42px] w-[180px] rounded-xl border border-rose-600/[0.28] bg-white/70 px-3.5 font-mono text-sm text-rose-800"
            />
            <Button
              variant="destructive"
              onClick={() => void handleDeleteAccount()}
              disabled={confirmText !== DELETE_CONFIRMATION_TEXT || isDeleting}
            >
              {isDeleting ? "Deleting…" : "Delete my account"}
            </Button>
            {confirmText !== DELETE_CONFIRMATION_TEXT && (
              <span className="text-xs text-rose-700">Type DELETE exactly to enable this.</span>
            )}
          </div>
          {deleteError && <p className="mt-2 text-sm text-rose-600">{deleteError}</p>}
        </GlassCard>
      </section>
    </div>
  );
}
