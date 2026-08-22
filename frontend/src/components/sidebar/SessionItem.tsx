import React from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2 } from '../icons';
import './SessionItem.css';

export interface SessionItemProps {
  session: {
    id: string;
    preview_text: string | null;
    created_at: string;
    last_activity_at: string;
  };
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
  collapsed?: boolean;
}

export const SessionItem: React.FC<SessionItemProps> = ({
  session,
  isActive,
  onClick,
  onDelete,
  collapsed = false,
}) => {
  const { t } = useTranslation();
  const [isHovered, setIsHovered] = React.useState(false);

  const preview = session.preview_text
    ? session.preview_text.length > 60
      ? session.preview_text.slice(0, 60) + '...'
      : session.preview_text
    : t('session.previewFallback');

  const handleActivationKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className={`session-item ${isActive ? 'session-item-active' : ''} ${collapsed ? 'session-item-collapsed' : ''}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      data-testid={`session-item-${session.id}`}
    >
      {!collapsed && (
        <>
          <button
            type="button"
            className="session-item-main"
            onClick={onClick}
            onKeyDown={handleActivationKeyDown}
            data-testid={`session-item-main-${session.id}`}
          >
            <span className="session-item-preview" title={preview}>
              {preview}
            </span>
          </button>
          <button
            type="button"
            className={`session-item-delete ${isHovered ? 'session-item-delete-visible' : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            aria-label={t('common.delete')}
            data-testid={`session-delete-${session.id}`}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </>
      )}
      {collapsed && (
        <button
          type="button"
          className="session-item-collapsed-control"
          onClick={onClick}
          onKeyDown={handleActivationKeyDown}
          aria-label={preview}
          title={preview}
          data-testid={`session-item-main-${session.id}`}
        >
          <span className="session-item-collapsed-dot" />
        </button>
      )}
    </div>
  );
};
