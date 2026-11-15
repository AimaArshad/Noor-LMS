import { QueryClient } from "@tanstack/react-query";

import { getStatus } from "@/api/errors";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Never retry 4xx answers (404, 403, ...); retry network errors / 5xx twice.
      retry: (failureCount, error) => {
        const status = getStatus(error);
        if (status !== undefined && status < 500) return false;
        return failureCount < 2;
      },
    },
  },
});
