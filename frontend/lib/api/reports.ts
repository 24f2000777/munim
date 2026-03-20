import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Report, Language, ReportType } from "@/lib/types";

export function useReports(page = 1) {
  return useQuery<{ items: Report[]; total: number }>({
    queryKey: ["reports", page],
    queryFn:  () =>
      apiClient
        .get("/reports", { params: { page, page_size: 20 } })
        .then((r) => r.data),
  });
}

export function useReport(reportId: string) {
  return useQuery<Report>({
    queryKey: ["reports", reportId],
    queryFn:  () =>
      apiClient.get(`/reports/${reportId}`).then((r) => r.data),
    enabled:  !!reportId,
  });
}

interface GenerateReportParams {
  upload_id:   string;
  language:    Language;
  report_type: ReportType;
}

export function useGenerateReport() {
  return useMutation<Report, Error, GenerateReportParams>({
    mutationFn: (params) =>
      apiClient.post("/reports/generate", params).then((r) => r.data),
  });
}

export function useSendReportWhatsApp() {
  return useMutation<
    { status: string; message_id: string },
    Error,
    { reportId: string; phone_number: string }
  >({
    mutationFn: ({ reportId, phone_number }) =>
      apiClient
        .post(`/reports/${reportId}/send`, { phone_number })
        .then((r) => r.data),
  });
}
