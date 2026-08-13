import { useEffect, useRef, useState } from 'react';
import { FlaskConical, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type {
  DraftPolicyTestRequest,
  PolicyTestResponse,
} from '../../api/generated/types.gen';
import {
  useDraftRolePolicyPreview,
  type ConnectionPolicyItem,
} from '../../hooks/useAdminRoles';

type PreviewState =
  | 'empty'
  | 'loading'
  | 'allowed'
  | 'blocked'
  | 'invalid'
  | 'retry'
  | 'permission-denied'
  | 'stale';

interface PreviewRecord {
  fingerprint: string;
  response?: PolicyTestResponse;
  state: Exclude<PreviewState, 'empty' | 'loading' | 'stale'>;
}

interface RolePolicyPreviewProps {
  policy: ConnectionPolicyItem;
}

function draftRequest(
  question: string,
  sampleSql: string,
  policy: ConnectionPolicyItem
): DraftPolicyTestRequest {
  return {
    question: question.trim(),
    sample_sql: sampleSql.trim() || null,
    connection_policy: {
      connection_id: policy.connection_id,
      allowed_tables: policy.allowed_tables,
      row_filters: policy.row_filters,
      column_masks: policy.column_masks,
    },
  };
}

function requestFingerprint(request: DraftPolicyTestRequest): string {
  return JSON.stringify(request);
}

function errorStatus(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const status = Reflect.get(error, 'status');
  return typeof status === 'number' ? status : undefined;
}

function errorMessageKey(error: unknown): string | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const directMessageKey = Reflect.get(error, 'message_key');
  if (typeof directMessageKey === 'string') return directMessageKey;
  const body = Reflect.get(error, 'body');
  if (body && typeof body === 'object') {
    const bodyMessageKey = Reflect.get(body, 'message_key');
    if (typeof bodyMessageKey === 'string') return bodyMessageKey;
  }
  const detail = Reflect.get(error, 'detail');
  if (detail && typeof detail === 'object') {
    const detailMessageKey = Reflect.get(detail, 'message_key');
    if (typeof detailMessageKey === 'string') return detailMessageKey;
  }
  return undefined;
}

function failureState(error: unknown): PreviewRecord['state'] {
  const status = errorStatus(error);
  const messageKey = errorMessageKey(error);
  if (
    status === 401 ||
    status === 403 ||
    messageKey === 'error.unauthorized' ||
    messageKey === 'error.forbidden'
  ) {
    return 'permission-denied';
  }
  if (status === 422 || messageKey === 'error.filterValidationFailed') {
    return 'invalid';
  }
  return 'retry';
}

function previewMessageKey(state: PreviewState): string {
  return `admin.roles.preview.state.${state}`;
}

export function RolePolicyPreview({ policy }: RolePolicyPreviewProps) {
  const { t } = useTranslation();
  const previewMutation = useDraftRolePolicyPreview();
  const [question, setQuestion] = useState('');
  const [sampleSql, setSampleSql] = useState('');
  const [record, setRecord] = useState<PreviewRecord | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inFlightRef = useRef(false);
  const statusRef = useRef<HTMLDivElement>(null);

  const request = draftRequest(question, sampleSql, policy);
  const fingerprint = requestFingerprint(request);
  const state: PreviewState = isSubmitting
    ? 'loading'
    : record && record.fingerprint !== fingerprint
      ? 'stale'
      : record?.state ?? 'empty';

  useEffect(() => {
    if (!['empty', 'loading'].includes(state)) {
      statusRef.current?.focus();
    }
  }, [state]);

  const finishRequest = () => {
    inFlightRef.current = false;
    setIsSubmitting(false);
  };

  const runPreview = () => {
    if (!request.question || inFlightRef.current) return;

    inFlightRef.current = true;
    setIsSubmitting(true);
    previewMutation.mutate(request, {
      onSuccess: (response) => {
        setRecord({
          fingerprint,
          response,
          state: response.would_be_allowed ? 'allowed' : 'blocked',
        });
        finishRequest();
      },
      onError: (error) => {
        setRecord({ fingerprint, state: failureState(error) });
        finishRequest();
      },
    });
  };

  const response = state === 'allowed' || state === 'blocked' ? record?.response : undefined;
  const accessibleTables = response?.accessible_tables ?? [];
  const blockedTables = response?.blocked_tables ?? [];
  const accessibleColumns = response?.accessible_columns ?? {};
  const filters = response?.applicable_row_filters ?? [];
  const masks = response?.masked_columns ?? {};

  return (
    <section
      aria-labelledby="role-policy-preview-heading"
      className="space-y-4 rounded-xl border border-gray-800 bg-gray-900/60 p-4"
    >
      <div className="space-y-1">
        <h4
          id="role-policy-preview-heading"
          className="flex items-center gap-2 text-sm font-semibold text-white"
        >
          <FlaskConical aria-hidden="true" className="h-4 w-4 text-neon-cyan" />
          {t('admin.roles.preview.title')}
        </h4>
        <p className="text-xs text-gray-400">{t('admin.roles.preview.description')}</p>
        <p className="text-xs text-gray-500">{t('admin.roles.preview.noExecution')}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="space-y-1 text-sm text-gray-300">
          <span>{t('admin.roles.preview.question')}</span>
          <input
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="w-full rounded-lg border border-gray-800 bg-gray-950 px-3 py-2 text-white outline-none focus:border-neon-cyan"
          />
        </label>
        <label className="space-y-1 text-sm text-gray-300">
          <span>{t('admin.roles.preview.sampleSql')}</span>
          <textarea
            dir="ltr"
            rows={2}
            value={sampleSql}
            onChange={(event) => setSampleSql(event.target.value)}
            className="w-full resize-y rounded-lg border border-gray-800 bg-gray-950 px-3 py-2 font-mono text-sm text-white outline-none focus:border-neon-cyan"
          />
        </label>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={runPreview}
          disabled={!question.trim() || isSubmitting}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-neon-cyan px-4 py-2 text-sm font-semibold text-neon-cyan transition-colors hover:bg-neon-cyan/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {state === 'loading' && (
            <span
              aria-hidden="true"
              className="h-4 w-4 animate-spin rounded-full border-2 border-neon-cyan border-t-transparent"
            />
          )}
          {t('admin.roles.preview.test')}
        </button>
        {state === 'retry' && (
          <button
            type="button"
            onClick={runPreview}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-200 hover:border-gray-600"
          >
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            {t('admin.roles.preview.retry')}
          </button>
        )}
      </div>

      <div
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        data-testid="policy-preview-status"
        data-state={state}
        className="rounded-lg border border-gray-800 bg-gray-950 p-3 outline-none focus:ring-2 focus:ring-neon-cyan"
      >
        <p className="text-sm text-gray-200">{t(previewMessageKey(state))}</p>

        {response && (
          <dl className="mt-3 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="font-semibold text-gray-400">{t('admin.roles.preview.accessibleTables')}</dt>
              <dd dir="ltr" className="mt-1 text-gray-200">
                {accessibleTables.length ? accessibleTables.join(', ') : t('admin.roles.preview.none')}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-gray-400">{t('admin.roles.preview.blockedTables')}</dt>
              <dd dir="ltr" className="mt-1 text-gray-200">
                {blockedTables.length ? blockedTables.join(', ') : t('admin.roles.preview.none')}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-gray-400">{t('admin.roles.preview.accessibleColumns')}</dt>
              <dd className="mt-1 space-y-1 text-gray-200">
                {Object.keys(accessibleColumns).length
                  ? Object.entries(accessibleColumns).map(([table, columns]) => (
                      <span key={table} dir="ltr" className="block">
                        {table}: {columns.join(', ')}
                      </span>
                    ))
                  : t('admin.roles.preview.none')}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-gray-400">{t('admin.roles.preview.filters')}</dt>
              <dd className="mt-1 space-y-1 text-gray-200">
                {filters.length
                  ? filters.map((filter, index) => (
                      <span key={index} dir="ltr" className="block">
                        {typeof filter.filter === 'string'
                          ? filter.filter
                          : t('admin.roles.preview.none')}
                      </span>
                    ))
                  : t('admin.roles.preview.none')}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-gray-400">{t('admin.roles.preview.masks')}</dt>
              <dd className="mt-1 space-y-1 text-gray-200">
                {Object.keys(masks).length
                  ? Object.entries(masks).map(([table, columns]) => (
                      <span key={table} dir="ltr" className="block">
                        {table}: {columns.join(', ')}
                      </span>
                    ))
                  : t('admin.roles.preview.none')}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </section>
  );
}
