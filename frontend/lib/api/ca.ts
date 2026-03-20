import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { CAClient, CADashboard } from "@/lib/types";

export function useCADashboard() {
  return useQuery<CADashboard>({
    queryKey: ["ca", "dashboard"],
    queryFn:  () => apiClient.get("/ca/dashboard").then((r) => r.data),
  });
}

export function useCAClients(activeOnly = true) {
  return useQuery<{ items: CAClient[]; total: number }>({
    queryKey: ["ca", "clients", activeOnly],
    queryFn:  () =>
      apiClient
        .get("/ca/clients", { params: { active_only: activeOnly } })
        .then((r) => r.data),
  });
}

export function useAddCAClient() {
  const qc = useQueryClient();
  return useMutation<
    CAClient,
    Error,
    { client_name: string; client_phone?: string; client_email?: string }
  >({
    mutationFn: (body) =>
      apiClient.post("/ca/clients", body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ca"] }),
  });
}

export function useDeleteCAClient() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (clientId) =>
      apiClient.delete(`/ca/clients/${clientId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ca"] }),
  });
}
