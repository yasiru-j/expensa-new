import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, refreshAccessToken, setAccessToken, setOnSessionExpired } from "./api";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  email_verified: boolean;
  created_at: string;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  signup: (email: string, password: string, fullName?: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetches the current user — call after PATCH /api/account so the
   * header and anywhere else `user` is read reflect the change immediately. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchCurrentUser(): Promise<User> {
  const res = await api.get<User>("/api/auth/me");
  return res.data;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setOnSessionExpired(() => setUser(null));
    return () => setOnSessionExpired(null);
  }, []);

  useEffect(() => {
    // Rehydrate the in-memory access token from the httpOnly refresh cookie
    // on first load (e.g. after a page refresh). Goes through the shared
    // refreshAccessToken() (not a raw api.post call) so React StrictMode's
    // double-invoked mount effect produces exactly one /api/auth/refresh
    // call, not two racing ones — see api.ts for why that used to log
    // people out. `cancelled` just guards against setting state from a
    // stale invocation after cleanup; it doesn't prevent the double call
    // (the shared in-flight promise already does that).
    let cancelled = false;
    (async () => {
      try {
        const token = await refreshAccessToken();
        if (cancelled) return;
        setAccessToken(token);
        setUser(await fetchCurrentUser());
      } catch {
        if (cancelled) return;
        setAccessToken(null);
        setUser(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signup = useCallback(async (email: string, password: string, fullName?: string) => {
    const res = await api.post<{ access_token: string }>("/api/auth/signup", {
      email,
      password,
      full_name: fullName || undefined,
    });
    setAccessToken(res.data.access_token);
    setUser(await fetchCurrentUser());
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string }>("/api/auth/login", {
      email,
      password,
    });
    setAccessToken(res.data.access_token);
    setUser(await fetchCurrentUser());
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    setUser(await fetchCurrentUser());
  }, []);

  const value = useMemo(
    () => ({ user, isLoading, signup, login, logout, refreshUser }),
    [user, isLoading, signup, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
