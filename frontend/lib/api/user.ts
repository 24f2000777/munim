import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { UserProfile, Language } from "@/lib/types";

export function useUserProfile() {
  return useQuery<UserProfile>({
    queryKey: ["user", "profile"],
    queryFn:  () => apiClient.get("/auth/me").then((r) => r.data),
  });
}

interface UpdateProfileParams {
  language_preference?: Language;
  phone?:              string;
  whatsapp_opted_in?:  boolean;
  notify_on_anomaly?:  boolean;
  notify_weekly?:      boolean;
  notify_monthly?:     boolean;
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation<UserProfile, Error, UpdateProfileParams>({
    mutationFn: (body) =>
      apiClient.put("/auth/profile", body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user"] }),
  });
}
