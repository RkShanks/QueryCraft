import { useInfiniteQuery } from '@tanstack/react-query';
import { listHistory } from '../api/historyApi';

export interface UseHistoryOptions {
  pageSize?: number;
  schema?: string;
}

export function useHistory(opts: UseHistoryOptions = {}) {
  const query = useInfiniteQuery({
    queryKey: ['history', opts.schema, opts.pageSize ?? 20],
    queryFn: ({ pageParam }) => listHistory({
      cursor: pageParam as string | undefined,
      page_size: opts.pageSize ?? 20,
      schema: opts.schema,
    }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  return {
    items: query.data?.pages.flatMap((p) => p.items) ?? [],
    total: query.data?.pages[0]?.total ?? 0,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    hasNextPage: query.hasNextPage ?? false,
    fetchNextPage: query.fetchNextPage,
    refetch: query.refetch,
  };
}
