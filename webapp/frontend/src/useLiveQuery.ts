import { useQuery } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import type { UseQueryResult } from "@tanstack/react-query";

interface Fetcher<T> {
  (options: { demo?: boolean; signal?: AbortSignal }): Promise<T>;
}

/**
 * Fetch one live view, honouring the URL's demo flag.
 *
 * Nothing is cached: quotes and balances move, so every view is a fresh
 * snapshot. Demo is part of the key, so switching modes refetches rather than
 * reusing the other mode's numbers.
 */
export function useLiveQuery<T>(
  key: string,
  fetcher: Fetcher<T>,
): UseQueryResult<T> & { isDemo: boolean } {
  const { demo } = useSearch({ strict: false });
  const isDemo = Boolean(demo);
  const query = useQuery({
    queryKey: [key, isDemo],
    queryFn: ({ signal }) => fetcher({ demo: isDemo, signal }),
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
  return { ...query, isDemo };
}
