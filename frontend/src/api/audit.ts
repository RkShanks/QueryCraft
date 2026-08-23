import {
  exportAuditEntries as exportCanonicalAuditEntries,
  getAuditRetention as getCanonicalAuditRetention,
  searchAuditEntries as searchCanonicalAuditEntries,
} from './generated/sdk.gen';
import type {
  AuditEntryRead,
  AuditExportRequest,
  AuditRetentionResponse,
  AuditSearchResponse,
  SearchAuditEntriesData,
} from './generated/types.gen';

export type AuditSearchParams = NonNullable<SearchAuditEntriesData['query']>;
export type AuditEntry = AuditEntryRead;
export type { AuditExportRequest, AuditRetentionResponse, AuditSearchResponse };

export async function searchAuditEntries(
  params: AuditSearchParams,
  signal?: AbortSignal
): Promise<AuditSearchResponse> {
  const response = await searchCanonicalAuditEntries({
    query: params as Record<string, unknown>,
    throwOnError: true,
    signal,
  });
  return response.data;
}

export async function exportAuditEntries(
  request: AuditExportRequest,
  signal?: AbortSignal
): Promise<Blob> {
  const response = await exportCanonicalAuditEntries({
    body: request,
    throwOnError: true,
    parseAs: 'blob',
    signal,
  });
  return response.data;
}

export async function getAuditRetention(signal?: AbortSignal): Promise<AuditRetentionResponse> {
  const response = await getCanonicalAuditRetention({ throwOnError: true, signal });
  return response.data;
}
