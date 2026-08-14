import { useQuery } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import type { UseQueryResult } from "@tanstack/react-query";

interface Fetcher<T> {
  (options: { demo?: boolean; signal?: AbortSignal }): Promise<T>;
}

/** How long a snapshot is served without going back to Robinhood. */
const STALE_TIME = 60_000;

/** How long an unmounted view's snapshot survives, so returning to it is instant. */
const GC_TIME = 5 * 60_000;

/**
 * Fetch one live view, honouring the URL's demo flag.
 *
 * A tab switch renders the previous snapshot rather than refetching, and each
 * page states when its snapshot was taken, so an older view cannot pass itself
 * off as current. Refresh always goes back to Robinhood regardless of age.
 *
 * Demo is part of the key, so switching modes refetches rather than reusing the
 * other mode's numbers.
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
    staleTime: STALE_TIME,
    gcTime: GC_TIME,
    refetchOnWindowFocus: false,
    retry: false,
  });
  return { ...query, isDemo };
}
