import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, Database, WifiOff, FileX, Ban, RefreshCw } from 'lucide-react';

export type ConnectionErrorKind =
  | 'noConnections'
  | 'disabled'
  | 'unhealthy'
  | 'noSchema'
  | 'queryExecutionFailed';

interface ErrorConfig {
  icon: React.ReactNode;
  titleKey: string;
  bodyKey: string;
  actionKey?: string;
  actionIcon?: React.ReactNode;
  severity: 'error' | 'warning' | 'info';
}

const configMap: Record<ConnectionErrorKind, ErrorConfig> = {
  noConnections: {
    icon: <Database className="w-5 h-5" aria-hidden="true" />,
    titleKey: 'error.noConnections.title',
    bodyKey: 'error.noConnections.body',
    actionKey: 'error.noConnections.action',
    actionIcon: <Database className="w-4 h-4" aria-hidden="true" />,
    severity: 'warning',
  },
  disabled: {
    icon: <Ban className="w-5 h-5" aria-hidden="true" />,
    titleKey: 'error.disabled.title',
    bodyKey: 'error.disabled.body',
    actionKey: 'error.disabled.action',
    severity: 'error',
  },
  unhealthy: {
    icon: <WifiOff className="w-5 h-5" aria-hidden="true" />,
    titleKey: 'error.unhealthy.title',
    bodyKey: 'error.unhealthy.body',
    actionKey: 'error.unhealthy.action',
    severity: 'error',
  },
  noSchema: {
    icon: <FileX className="w-5 h-5" aria-hidden="true" />,
    titleKey: 'error.noSchema.title',
    bodyKey: 'error.noSchema.body',
    actionKey: 'error.noSchema.action',
    actionIcon: <RefreshCw className="w-4 h-4" aria-hidden="true" />,
    severity: 'warning',
  },
  queryExecutionFailed: {
    icon: <AlertCircle className="w-5 h-5" aria-hidden="true" />,
    titleKey: 'error.queryExecutionFailed.title',
    bodyKey: 'error.queryExecutionFailed.body',
    actionKey: 'error.queryExecutionFailed.action',
    severity: 'error',
  },
};

const severityStyles: Record<ErrorConfig['severity'], string> = {
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  info: 'bg-sky-50 border-sky-200 text-sky-800',
};

const iconStyles: Record<ErrorConfig['severity'], string> = {
  error: 'text-red-600',
  warning: 'text-amber-600',
  info: 'text-sky-600',
};

const actionStyles: Record<ErrorConfig['severity'], string> = {
  error: 'text-red-800 bg-red-100 border-red-300 hover:bg-red-200 focus:ring-red-500',
  warning: 'text-amber-800 bg-amber-100 border-amber-300 hover:bg-amber-200 focus:ring-amber-500',
  info: 'text-sky-800 bg-sky-100 border-sky-300 hover:bg-sky-200 focus:ring-sky-500',
};

export interface ConnectionErrorCardProps {
  kind: ConnectionErrorKind;
  onAction?: () => void;
}

export const ConnectionErrorCard: React.FC<ConnectionErrorCardProps> = ({
  kind,
  onAction,
}) => {
  const { t } = useTranslation();
  const cfg = configMap[kind] ?? {
    icon: <AlertCircle className="w-5 h-5" aria-hidden="true" />,
    titleKey: 'error.unknown.title',
    bodyKey: 'error.unknown.message',
    severity: 'error',
  };

  return (
    <div
      role="alert"
      className={`rounded-lg border p-4 flex flex-col gap-3 ${severityStyles[cfg.severity]}`}
      data-testid="connection-error-card"
    >
      <div className="flex items-start gap-3">
        <div className={`shrink-0 mt-0.5 ${iconStyles[cfg.severity]}`}>
          {cfg.icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold">
            {t(cfg.titleKey)}
          </h3>
          <p className="text-sm mt-1 opacity-90">
            {t(cfg.bodyKey)}
          </p>
        </div>
      </div>
      {cfg.actionKey && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onAction}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border rounded-md transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 ${actionStyles[cfg.severity]}`}
          >
            {cfg.actionIcon}
            {t(cfg.actionKey)}
          </button>
        </div>
      )}
    </div>
  );
};
