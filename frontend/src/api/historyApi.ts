import { listHistory as sdkListHistory, getHistoryEntry } from './generated/sdk.gen';
import type { HistoryListResponse } from './generated/types.gen';

export interface ListHistoryParams {
  cursor?: string;
  page_size?: number;
  schema?: string;
}

export async function listHistory(params: ListHistoryParams = {}): Promise<HistoryListResponse> {
  const res = await sdkListHistory({
    query: {
      cursor: params.cursor,
      limit: params.page_size ?? 20,
    },
    throwOnError: true,
  });
  return res.data;
}

export async function getHistoryItem(id: string) {
  const res = await getHistoryEntry({
    path: { query_id: id },
    throwOnError: true,
  });
  return res.data;
}
