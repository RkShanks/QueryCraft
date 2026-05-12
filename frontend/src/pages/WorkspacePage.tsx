import React from 'react';
import { useTranslation } from 'react-i18next';
import { useUIStore } from '../stores/uiStore';
import { useSessionDetail } from '../hooks/useSessions';
import { MessageSquare } from '../components/icons';
import './WorkspacePage.css';

export const WorkspacePage: React.FC = () => {
  const { t } = useTranslation();
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const { data: sessionDetail, isLoading } = useSessionDetail(activeSessionId ?? '');

  return (
    <div className="workspace-page" data-testid="workspace-page">
      {activeSessionId === null ? (
        <div className="workspace-empty-state">
          <MessageSquare className="w-12 h-12 workspace-empty-icon" />
          <h2 className="workspace-empty-title">
            {t('workspace.emptyState')}
          </h2>
          <p className="workspace-empty-subtitle">
            {t('workspace.placeholder')}
          </p>
        </div>
      ) : isLoading ? (
        <div className="workspace-loading">
          <div className="workspace-spinner" />
          <p>{t('history.loading')}</p>
        </div>
      ) : (
        <div className="workspace-active">
          <div className="workspace-session-header">
            <h2 className="workspace-session-title">
              {sessionDetail?.preview_text || t('session.previewFallback')}
            </h2>
          </div>
          <div className="workspace-chat-placeholder">
            <p className="workspace-placeholder-text">
              {t('workspace.chatPlaceholder')}
            </p>
            {sessionDetail?.attempts && sessionDetail.attempts.length > 0 && (
              <div className="workspace-attempts-count">
                {t('workspace.attemptsCount', { count: sessionDetail.attempts.length })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
