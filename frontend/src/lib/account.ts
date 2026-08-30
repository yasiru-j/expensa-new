import { api } from "./api";
import type { User } from "./auth";

export interface UsageRead {
  period_month: string; // "YYYY-MM-DD", always the first of the month
  extraction_count: number;
  monthly_limit: number;
  remaining: number;
}

export async function getUsage(): Promise<UsageRead> {
  const res = await api.get<UsageRead>("/api/usage");
  return res.data;
}

// Irreversible — hard-deletes every row and stored file for the caller.
// The frontend requires an explicit typed confirmation before ever calling
// this; see the AccountPage.
export async function deleteAccount(): Promise<void> {
  await api.delete("/api/account");
}

// full_name: null explicitly clears it (distinct from omitting the field,
// which the backend leaves untouched — see AccountUpdate on the server).
export async function updateAccount(fullName: string | null): Promise<User> {
  const res = await api.patch<User>("/api/account", { full_name: fullName });
  return res.data;
}
