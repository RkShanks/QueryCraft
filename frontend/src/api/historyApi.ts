import { listHistory as sdkListHistory, getHistoryEntry } from './generated/sdk.gen';
import type { HistoryListResponse } from './generated/types.gen';

export interface ListHistoryParams {
  cursor?: string;
  page_size?: number;
}

export async function listHistory(
  params: ListHistoryParams = {},
  signal?: AbortSignal
): Promise<HistoryListResponse> {
  const res = await sdkListHistory({
    query: {
      cursor: params.cursor,
      limit: params.page_size ?? 20,
    },
    throwOnError: true,
    signal,
  });
  return res.data;
}

export async function getHistoryItem(id: string, signal?: AbortSignal) {
  const res = await getHistoryEntry({
    path: { query_id: id },
    throwOnError: true,
    signal,
  });
  return res.data;
}
