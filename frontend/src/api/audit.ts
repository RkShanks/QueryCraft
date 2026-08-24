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
import {
  type AuditDownload,
  type AuditExportFormat,
  AuditDownloadError,
  expectedAuditExportMediaType,
  parseAuditExportFilename,
  safeAuditExportFilename,
} from './auditDownload';

export type AuditSearchParams = NonNullable<SearchAuditEntriesData['query']>;
export type AuditEntry = AuditEntryRead;
export type { AuditExportRequest, AuditRetentionResponse, AuditSearchResponse };
export type { AuditDownload, AuditExportFormat } from './auditDownload';
export { AuditDownloadError } from './auditDownload';

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

/**
 * Exports audit entries and validates the download contract (CHUNK-22):
 * the caller's AbortSignal passes through unchanged, the successful media
 * type must match the requested format, and a server filename is honored
 * only when it is a safe contractual basename — otherwise a deterministic
 * safe local fallback is used. Filter values never reach the filename.
 */
export async function exportAuditEntries(
  request: AuditExportRequest,
  signal?: AbortSignal
): Promise<AuditDownload> {
  const format = request.format as AuditExportFormat;
  const response = await exportCanonicalAuditEntries({
    body: request,
    throwOnError: true,
    parseAs: 'blob',
    signal,
  });

  const blob = response.data;
  // Structural guard instead of `instanceof`: the fetch implementation's Blob
  // realm can differ from the DOM global in test and edge environments.
  const looksLikeBlob =
    typeof blob === 'object' &&
    blob !== null &&
    typeof (blob as Blob).text === 'function' &&
    typeof (blob as Blob).size === 'number';
  if (!looksLikeBlob) {
    throw new AuditDownloadError();
  }

  const contentType = response.response.headers.get('content-type') ?? '';
  const actualMediaType = contentType.split(';')[0].trim().toLowerCase();
  const expectedMediaType = expectedAuditExportMediaType(format);
  if (actualMediaType !== expectedMediaType) {
    throw new AuditDownloadError();
  }

  const disposition = response.response.headers.get('content-disposition');
  const serverFilename = parseAuditExportFilename(disposition, format);

  return {
    blob,
    filename: serverFilename ?? safeAuditExportFilename(format),
    mediaType: actualMediaType,
  };
}

export async function getAuditRetention(signal?: AbortSignal): Promise<AuditRetentionResponse> {
  const response = await getCanonicalAuditRetention({ throwOnError: true, signal });
  return response.data;
}
