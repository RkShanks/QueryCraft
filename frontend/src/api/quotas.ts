import {
  deleteQuota as deleteCanonicalQuota,
  getQuotaStatus as getCanonicalQuotaStatus,
  listQuotas as listCanonicalQuotas,
  upsertQuota as upsertCanonicalQuota,
} from './generated/sdk.gen';
import type {
  QuotaDimensionStatus,
  QuotaStatusResponse,
  QuotaSyncPendingErrorResponse,
  RoleQuotaConfig as CanonicalRoleQuotaConfig,
  RoleQuotaStatus,
  RoleQuotaUpsert,
} from './generated/types.gen';

export type RoleQuotaConfig = Omit<
  CanonicalRoleQuotaConfig,
  | 'created_at'
  | 'daily_execution_limit'
  | 'daily_export_limit'
  | 'daily_query_limit'
  | 'updated_at'
> & {
  created_at?: CanonicalRoleQuotaConfig['created_at'];
  daily_execution_limit: NonNullable<CanonicalRoleQuotaConfig['daily_execution_limit']> | null;
  daily_export_limit: NonNullable<CanonicalRoleQuotaConfig['daily_export_limit']> | null;
  daily_query_limit: NonNullable<CanonicalRoleQuotaConfig['daily_query_limit']> | null;
  updated_at?: CanonicalRoleQuotaConfig['updated_at'];
};
export type { QuotaDimensionStatus, RoleQuotaStatus, RoleQuotaUpsert };
export type QuotaStatusPage = QuotaStatusResponse;
type QuotaSynchronizationPending = QuotaSyncPendingErrorResponse & {
  error: 'quota_sync_pending';
  message_key: 'error.quota_sync_pending';
  mutation_applied: true;
};

function normalizeRoleQuota(quota: CanonicalRoleQuotaConfig): RoleQuotaConfig {
  return {
    ...quota,
    daily_execution_limit: quota.daily_execution_limit ?? null,
    daily_export_limit: quota.daily_export_limit ?? null,
    daily_query_limit: quota.daily_query_limit ?? null,
  };
}

export function isQuotaSynchronizationPending(
  error: unknown
): error is QuotaSynchronizationPending {
  if (!error || typeof error !== 'object') {
    return false;
  }
  const response = error as Record<string, unknown>;
  if (
    response.error === 'quota_sync_pending' &&
    response.message_key === 'error.quota_sync_pending' &&
    response.mutation_applied === true
  ) {
    return true;
  }
  return false;
}

export async function listQuotas(): Promise<{ quotas: RoleQuotaConfig[] }> {
  const response = await listCanonicalQuotas({ throwOnError: true });
  return { quotas: response.data.quotas.map(normalizeRoleQuota) };
}

export async function getQuotaStatus(
  cursor?: string,
  signal?: AbortSignal
): Promise<QuotaStatusPage> {
  const response = await getCanonicalQuotaStatus({
    query: { cursor, limit: 50 },
    signal,
    throwOnError: true,
  });
  return response.data;
}

export async function upsertQuota(
  roleId: string,
  data: RoleQuotaUpsert
): Promise<RoleQuotaConfig> {
  const response = await upsertCanonicalQuota({
    path: { role_id: roleId },
    body: data,
    throwOnError: true,
  });
  return normalizeRoleQuota(response.data);
}

export async function deleteQuota(roleId: string): Promise<void> {
  await deleteCanonicalQuota({
    path: { role_id: roleId },
    throwOnError: true,
  });
}
