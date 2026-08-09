import { useCallback, useMemo, useState } from 'react';
import type { RoleQuotaUpsert } from '../api/quotas';

export type QuotaMutationRecovery =
  | { kind: 'upsert'; roleId: string; data: RoleQuotaUpsert }
  | { kind: 'delete'; roleId: string };

interface StoredRecovery {
  version: 1;
  operation: QuotaMutationRecovery;
}

interface RecoveryState {
  userId: string | undefined;
  operation: QuotaMutationRecovery | null;
}

const STORAGE_PREFIX = 'querycraft:quota-recovery:v1:';

function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}${userId}`;
}

function isQuotaLimit(value: unknown): value is number | null {
  return (
    value === null ||
    (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0)
  );
}

function isUpsertData(value: unknown): value is RoleQuotaUpsert {
  if (!value || typeof value !== 'object') return false;
  const data = value as Record<string, unknown>;
  return (
    isQuotaLimit(data.daily_query_limit) &&
    isQuotaLimit(data.daily_execution_limit) &&
    isQuotaLimit(data.daily_export_limit)
  );
}

function isRecoveryOperation(value: unknown): value is QuotaMutationRecovery {
  if (!value || typeof value !== 'object') return false;
  const operation = value as Record<string, unknown>;
  if (typeof operation.roleId !== 'string' || !operation.roleId) return false;
  if (operation.kind === 'delete') return true;
  return operation.kind === 'upsert' && isUpsertData(operation.data);
}

function readRecovery(userId: string | undefined): QuotaMutationRecovery | null {
  if (!userId || typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(storageKey(userId));
    if (!raw) return null;
    const stored = JSON.parse(raw) as Partial<StoredRecovery>;
    return stored.version === 1 && isRecoveryOperation(stored.operation)
      ? stored.operation
      : null;
  } catch {
    return null;
  }
}

function writeRecovery(
  userId: string,
  operation: QuotaMutationRecovery | null
): void {
  try {
    if (operation) {
      const stored: StoredRecovery = { version: 1, operation };
      window.sessionStorage.setItem(storageKey(userId), JSON.stringify(stored));
    } else {
      window.sessionStorage.removeItem(storageKey(userId));
    }
  } catch {
    // Recovery remains available for the current render when storage is blocked.
  }
}

export function useQuotaMutationRecovery(userId: string | undefined) {
  const restoredOperation = useMemo(() => readRecovery(userId), [userId]);
  const [recoveryState, setRecoveryState] = useState<RecoveryState>(() => ({
    userId,
    operation: restoredOperation,
  }));
  const operation =
    recoveryState.userId === userId
      ? recoveryState.operation
      : restoredOperation;

  const remember = useCallback(
    (nextOperation: QuotaMutationRecovery) => {
      if (userId) writeRecovery(userId, nextOperation);
      setRecoveryState({ userId, operation: nextOperation });
    },
    [userId]
  );

  const clear = useCallback(() => {
    if (userId) writeRecovery(userId, null);
    setRecoveryState({ userId, operation: null });
  }, [userId]);

  return { operation, remember, clear };
}
