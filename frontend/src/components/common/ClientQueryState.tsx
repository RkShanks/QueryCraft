import { RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { isClientContractError } from '../../api/responseValidation';

interface QueryStateSource {
  data?: unknown;
  error?: unknown;
  isError: boolean;
  isFetching: boolean;
  refetch: () => unknown;
}

interface ClientQueryStateProps {
  query: QueryStateSource;
  fallbackErrorKey: string;
  getOrdinaryErrorMessage?: (error: unknown) => string;
  hasData?: boolean;
  isPartial?: boolean;
}

export function ClientQueryState({
  query,
  fallbackErrorKey,
  getOrdinaryErrorMessage,
  hasData = query.data !== undefined,
  isPartial = false,
}: ClientQueryStateProps) {
  const { t } = useTranslation();

  if (query.isError) {
    const isContractError = isClientContractError(query.error);
    const messageKey = isContractError
      ? hasData
        ? 'clientContract.invalidRefresh'
        : 'clientContract.invalidInitial'
      : hasData
        ? 'clientContract.refreshError'
        : fallbackErrorKey;
    const message =
      !isContractError && !hasData && getOrdinaryErrorMessage
        ? getOrdinaryErrorMessage(query.error)
        : t(messageKey);

    return (
      <div
        role="alert"
        aria-label={message}
        className="flex min-w-0 flex-col items-center justify-center gap-3 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-4 text-center text-sm text-red-300"
      >
        <p>{message}</p>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-red-400/30 px-4 py-2 font-semibold text-red-200 transition-colors hover:border-red-300 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t('common.retry')}
        </button>
      </div>
    );
  }

  if (hasData && query.isFetching) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-2 text-sm text-text-secondary"
      >
        <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
        {t('clientContract.refreshing')}
      </div>
    );
  }

  if (hasData && isPartial) {
    return (
      <div role="status" aria-live="polite" className="text-sm text-text-secondary">
        {t('clientContract.partial')}
      </div>
    );
  }

  return null;
}
