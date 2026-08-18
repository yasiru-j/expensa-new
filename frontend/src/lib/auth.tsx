import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, setAccessToken, setOnSessionExpired } from "./api";

export interface User {
  id: string;
  email: string;
  email_verified: boolean;
  created_at: string;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  signup: (email: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
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
    // on first load (e.g. after a page refresh).
    (async () => {
      try {
        const res = await api.post<{ access_token: string }>("/api/auth/refresh");
        setAccessToken(res.data.access_token);
        setUser(await fetchCurrentUser());
      } catch {
        setAccessToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string }>("/api/auth/signup", {
      email,
      password,
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

  const value = useMemo(
    () => ({ user, isLoading, signup, login, logout }),
    [user, isLoading, signup, login, logout],
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
