import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import { UPLOAD_POLL_INTERVAL_MS } from "@/lib/constants";
import type { UploadResponse, UploadStatusResponse } from "@/lib/types";

export function useUploadFile() {
  return useMutation<UploadResponse, Error, File>({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiClient
        .post("/upload", form, {
          headers: { "Content-Type": "multipart/form-data" },
        })
        .then((r) => r.data);
    },
  });
}

export function useUploadStatus(uploadId: string | null) {
  return useQuery<UploadStatusResponse>({
    queryKey:       ["upload-status", uploadId],
    queryFn:        () =>
      apiClient.get(`/upload/${uploadId}/status`).then((r) => r.data),
    enabled:        !!uploadId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return UPLOAD_POLL_INTERVAL_MS;
    },
  });
}
