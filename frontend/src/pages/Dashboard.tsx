import { useAuth } from "../lib/auth";

export function Dashboard() {
  const { user } = useAuth();

  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
      <p className="text-gray-600">
        Signed in as <span className="font-medium">{user?.email}</span>. Upload, extraction, and
        spending insights land in later phases.
      </p>
    </div>
  );
}
