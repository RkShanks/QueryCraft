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

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === 'number' && value >= 0;
}

function isTimezoneAwareTimestamp(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function parseAuditRetentionResponse(value: unknown): AuditRetentionResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid audit retention response');
  }

  const candidate = value as Record<string, unknown>;
  const lastPurgeAt = candidate.last_purge_at;
  const purgedCount = candidate.purged_count;
  if (
    !isNonNegativeInteger(candidate.retention_months) ||
    (lastPurgeAt !== null && !isTimezoneAwareTimestamp(lastPurgeAt)) ||
    (purgedCount !== null && !isNonNegativeInteger(purgedCount))
  ) {
    throw new Error('Invalid audit retention response');
  }

  return {
    retention_months: candidate.retention_months,
    last_purge_at: lastPurgeAt,
    purged_count: purgedCount,
  };
}

export async function searchAuditEntries(params: AuditSearchParams): Promise<AuditSearchResponse> {
  const response = await searchCanonicalAuditEntries({
    query: params as Record<string, unknown>,
    throwOnError: true,
  });
  return response.data;
}

export async function exportAuditEntries(request: AuditExportRequest): Promise<Blob> {
  const response = await exportCanonicalAuditEntries({
    body: request,
    throwOnError: true,
    parseAs: 'blob',
  });
  return response.data;
}

export async function getAuditRetention(): Promise<AuditRetentionResponse> {
  const response = await getCanonicalAuditRetention({ throwOnError: true });
  return parseAuditRetentionResponse(response.data);
}
