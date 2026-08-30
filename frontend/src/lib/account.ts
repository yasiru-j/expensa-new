import { api } from "./api";

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
