import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { listHistory, getHistoryItem } from '../api/historyApi';
import { PERMISSIONS } from '../auth/permissions';
import { usePermission } from './usePermission';

export interface UseHistoryOptions {
  pageSize?: number;
}

export function useHistory(opts: UseHistoryOptions = {}) {
  const canViewHistory = usePermission(PERMISSIONS.QUERY_HISTORY_VIEW);
  const query = useInfiniteQuery({
    queryKey: ['history', opts.pageSize ?? 20],
    queryFn: ({ pageParam, signal }) =>
      listHistory(
        {
          cursor: pageParam as string | undefined,
          page_size: opts.pageSize ?? 20,
        },
        signal
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: canViewHistory,
  });

  return {
    ...query,
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

export function useHistoryDetail(id: string | null) {
  const canViewHistory = usePermission(PERMISSIONS.QUERY_HISTORY_VIEW);
  const query = useQuery({
    queryKey: ['history', 'detail', id],
    queryFn: ({ signal }) => getHistoryItem(id!, signal),
    enabled: !!id && canViewHistory,
  });

  return {
    ...query,
    item: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error as Error | null,
  };
}
