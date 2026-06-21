import { client } from './generated/client.gen';

export interface RoleQuotaConfig {
  role_id: string;
  role_name: string;
  daily_query_limit: number | null;
  daily_execution_limit: number | null;
  daily_export_limit: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface RoleQuotaUpsert {
  daily_query_limit?: number | null;
  daily_execution_limit?: number | null;
  daily_export_limit?: number | null;
}

export interface QuotaDimensionStatus {
  limit: number | null;
  used: number;
  remaining: number | null;
}

export interface RoleQuotaStatus {
  role_id: string;
  role_name: string;
  dimensions: {
    queries: QuotaDimensionStatus;
    executions: QuotaDimensionStatus;
    exports: QuotaDimensionStatus;
  };
  reset_at: string;
}

export async function listQuotas(): Promise<{ quotas: RoleQuotaConfig[] }> {
  const res = await client.get({
    url: '/admin/quotas',
    throwOnError: true,
  });
  return res.data as { quotas: RoleQuotaConfig[] };
}

export async function getQuotaStatus(): Promise<{ status: RoleQuotaStatus[] }> {
  const res = await client.get({
    url: '/admin/quotas/status',
    throwOnError: true,
  });
  return res.data as { status: RoleQuotaStatus[] };
}

export async function upsertQuota(
  roleId: string,
  data: RoleQuotaUpsert
): Promise<RoleQuotaConfig> {
  const res = await client.put({
    url: `/admin/quotas/${roleId}`,
    body: data,
    throwOnError: true,
  });
  return res.data as RoleQuotaConfig;
}

export async function deleteQuota(roleId: string): Promise<void> {
  await client.delete({
    url: `/admin/quotas/${roleId}`,
    throwOnError: true,
  });
}
