import axios from "axios";
import { getSession } from "next-auth/react";
import { API_BASE } from "@/lib/constants";

export const apiClient = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30_000,
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
