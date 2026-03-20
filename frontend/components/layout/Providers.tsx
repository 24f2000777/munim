"use client";
import { SessionProvider } from "next-auth/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime:           60_000,
            gcTime:              5 * 60_000,
            retry:               1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster
          position="top-center"
          richColors
          toastOptions={{
            style: {
              background: "#FAFAF7",
              border:     "1px solid hsl(48, 15%, 88%)",
              color:      "#1B4332",
              fontFamily: "var(--font-inter)",
            },
          }}
        />
      </QueryClientProvider>
    </SessionProvider>
  );
}
