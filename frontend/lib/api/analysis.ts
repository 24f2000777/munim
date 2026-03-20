import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  MetricsResponse,
  AnomaliesResponse,
  CustomersResponse,
  AnalysisHistoryItem,
  Severity,
} from "@/lib/types";

export function useAnalysisMetrics(uploadId: string) {
  return useQuery<MetricsResponse>({
    queryKey: ["analysis", uploadId, "metrics"],
    queryFn:  () =>
      apiClient.get(`/analysis/${uploadId}/metrics`).then((r) => r.data),
    enabled:  !!uploadId,
  });
}

export function useAnalysisAnomalies(uploadId: string, severity?: Severity) {
  return useQuery<AnomaliesResponse>({
    queryKey: ["analysis", uploadId, "anomalies", severity],
    queryFn:  () =>
      apiClient
        .get(`/analysis/${uploadId}/anomalies`, {
          params: severity ? { severity } : undefined,
        })
        .then((r) => r.data),
    enabled: !!uploadId,
  });
}

export function useAnalysisCustomers(uploadId: string) {
  return useQuery<CustomersResponse>({
    queryKey: ["analysis", uploadId, "customers"],
    queryFn:  () =>
      apiClient.get(`/analysis/${uploadId}/customers`).then((r) => r.data),
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
