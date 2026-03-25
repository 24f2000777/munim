import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  MetricsResponse,
  AnomaliesResponse,
  CustomersResponse,
  AnalysisHistoryItem,
  Severity,
} from "@/lib/types";

function tokenConfig(token?: string) {
  return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
}

export function useAnalysisMetrics(uploadId: string, token?: string) {
  return useQuery<MetricsResponse>({
    queryKey: ["analysis", uploadId, "metrics", token],
    queryFn:  () =>
      apiClient
        .get(`/analysis/${uploadId}/metrics`, tokenConfig(token))
        .then((r) => r.data),
    enabled:  !!uploadId,
  });
}

export function useAnalysisAnomalies(uploadId: string, severity?: Severity, token?: string) {
  return useQuery<AnomaliesResponse>({
    queryKey: ["analysis", uploadId, "anomalies", severity, token],
    queryFn:  () =>
      apiClient
        .get(`/analysis/${uploadId}/anomalies`, {
          params: severity ? { severity } : undefined,
          ...tokenConfig(token),
        })
        .then((r) => r.data),
    enabled: !!uploadId,
  });
}

export function useAnalysisCustomers(uploadId: string, token?: string) {
  return useQuery<CustomersResponse>({
    queryKey: ["analysis", uploadId, "customers", token],
    queryFn:  () =>
      apiClient
        .get(`/analysis/${uploadId}/customers`, tokenConfig(token))
        .then((r) => r.data),
    enabled:  !!uploadId,
  });
}

export function useAnalysisHistory(page = 1, pageSize = 10) {
  return useQuery<{ items: AnalysisHistoryItem[]; total: number }>({
    queryKey: ["analysis", "history", page],
    queryFn:  () =>
      apiClient
        .get("/analysis/history/list", { params: { page, page_size: pageSize } })
        .then((r) => r.data),
  });
}
