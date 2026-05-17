"use client";

import React, { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Wraps the application with TanStack React Query's QueryClientProvider.
 * A new QueryClient is created once per component mount (using useState so it
 * survives re-renders without losing the cache).
 *
 * Default options:
 *  - staleTime 60 s  → cached data is considered fresh for 1 minute
 *  - retry 1         → one automatic retry on failure
 *  - refetchOnWindowFocus false → avoids surprise refetches when the user
 *                                 switches tabs (can be enabled per-query)
 */
export function ReactQueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime:          60 * 1000,
            retry:              1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
