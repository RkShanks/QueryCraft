import { getQueryLimits as getCanonicalQueryLimits } from './generated/sdk.gen';
import type { QueryLimitsResponse } from './generated/types.gen';

export type { QueryLimitsResponse };

export async function getQueryLimits(signal?: AbortSignal): Promise<QueryLimitsResponse> {
  const response = await getCanonicalQueryLimits({ throwOnError: true, signal });
  return response.data;
}
