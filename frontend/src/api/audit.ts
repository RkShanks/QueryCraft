import { client } from './generated/client.gen';

export interface AuditSearchParams {
  start_date?: string;
  end_date?: string;
  action_type?: string;
  actor_identity?: string;
  outcome?: string;
  resource_type?: string;
  page?: number;
  page_size?: number;
}

export interface AuditEntry {
  sequence_number: number;
  timestamp: string;
  actor_identity: string | null;
  action_type: string;
  resource_type: string | null;
  resource_id: string | null;
  outcome: string;
  context: Record<string, any>;
}

export interface AuditSearchResponse {
  entries: AuditEntry[];
  pagination: {
    page: number;
    page_size: number;
    total_entries: number;
    total_pages: number;
  };
}

export interface AuditExportRequest {
  format: 'csv' | 'json';
  start_date?: string;
  end_date?: string;
  action_type?: string;
  actor_identity?: string;
  outcome?: string;
  resource_type?: string;
}

export interface AuditRetentionResponse {
  retention_months: number;
  last_purge_at: string | null;
  purged_count: number | null;
}

export async function searchAuditEntries(params: AuditSearchParams): Promise<AuditSearchResponse> {
  const res = await client.get({
    url: '/admin/audit/entries',
    query: params as any,
    throwOnError: true,
  });
  return res.data as AuditSearchResponse;
}

export async function exportAuditEntries(request: AuditExportRequest): Promise<Blob> {
  const res = await client.post({
    url: '/admin/audit/export',
    body: request,
    throwOnError: true,
    parseAs: 'blob',
  });
  return res.data as Blob;
}

export async function getAuditRetention(): Promise<AuditRetentionResponse> {
  const res = await client.get({
    url: '/admin/audit/retention',
    throwOnError: true,
  });
  return res.data as AuditRetentionResponse;
}
