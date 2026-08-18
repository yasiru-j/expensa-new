import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// The access token lives only in memory, never in localStorage/sessionStorage,
// so it can't be lifted by an XSS payload reading browser storage. The
// refresh token is a separate httpOnly cookie the browser manages for us.
let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setOnSessionExpired(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // send/receive the httpOnly refresh cookie
});

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  refreshPromise ??= api
    .post<{ access_token: string }>("/api/auth/refresh")
    .then((res) => res.data.access_token)
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const isAuthEndpoint = config?.url?.startsWith("/api/auth/");

    if (error.response?.status !== 401 || !config || config._retried || isAuthEndpoint) {
      throw error;
    }

    config._retried = true;

    try {
      const newAccessToken = await refreshAccessToken();
      setAccessToken(newAccessToken);
      config.headers.Authorization = `Bearer ${newAccessToken}`;
      return await api.request(config);
    } catch (refreshError) {
      setAccessToken(null);
      onSessionExpired?.();
      throw refreshError;
    }
  },
);
