import React from 'react';
import { useTranslation } from 'react-i18next';
import { useDeleteSession } from '../../hooks/useSessions';
import './UndoToast.css';

export interface UndoToastItem {
  id: string;
  sessionId: string;
  message: string;
}

interface UndoToastProps {
  item: UndoToastItem;
  onUndo: () => void;
  onExpired: () => void;
}

const UNDO_DURATION_MS = 5000;

export const UndoToast: React.FC<UndoToastProps> = ({ item, onUndo, onExpired }) => {
  const { t } = useTranslation();
  const deleteMutation = useDeleteSession();
  const [remainingMs, setRemainingMs] = React.useState(UNDO_DURATION_MS);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const expiredRef = React.useRef(false);

  const deleteMutationRef = React.useRef(deleteMutation);
  const onExpiredRef = React.useRef(onExpired);

  React.useEffect(() => {
    deleteMutationRef.current = deleteMutation;
    onExpiredRef.current = onExpired;
  }, [deleteMutation, onExpired]);

  React.useEffect(() => {
    const startTime = Date.now();

    intervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, UNDO_DURATION_MS - elapsed);
      setRemainingMs(remaining);

      if (remaining <= 0 && intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    }, 100);

    timerRef.current = setTimeout(() => {
      if (!expiredRef.current) {
        expiredRef.current = true;
        deleteMutationRef.current.mutate(item.sessionId);
        onExpiredRef.current();
      }
    }, UNDO_DURATION_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [item.sessionId]);

  const handleUndo = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);
    onUndo();
  };

  const progressPercent = (remainingMs / UNDO_DURATION_MS) * 100;

  return (
    <div className="undo-toast" data-testid={`undo-toast-${item.id}`}>
      <div className="undo-toast-content">
        <span className="undo-toast-message">{item.message}</span>
        <button
          className="undo-toast-button"
          onClick={handleUndo}
          data-testid={`undo-button-${item.id}`}
        >
          {t('sidebar.undo')}
        </button>
      </div>
      <div className="undo-toast-progress">
        <div
          className="undo-toast-progress-bar"
          style={{ width: `${progressPercent}%` }}
          data-testid={`undo-progress-${item.id}`}
        />
      </div>
    </div>
  );
};
