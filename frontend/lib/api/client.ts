import axios from "axios";
import { getSession } from "next-auth/react";
import { API_BASE } from "@/lib/constants";

export const apiClient = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30_000,
  headers: {
    // Bypass ngrok's browser-warning interstitial page in development.
    // Without this, every GET/POST through a free ngrok URL returns HTML
    // instead of JSON, breaking all polling and API calls silently.
    // Harmless on non-ngrok servers (header is simply ignored).
    "ngrok-skip-browser-warning": "true",
  },
});

apiClient.interceptors.request.use(async (config) => {
  const session = await getSession();
  const token   = (session as any)?.accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    const msg =
      error.response?.data?.detail ??
      error.message ??
      "Something went wrong";
    return Promise.reject(new Error(String(msg)));
  }
);
