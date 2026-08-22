import React from 'react';
import { useTranslation } from 'react-i18next';
import { useDeleteSession } from '../../hooks/useSessions';
import {
  beginSessionDeletion,
  rollbackSessionDeletion,
} from '../../sessionDeletionLifecycle';
import './UndoToast.css';

export interface UndoToastItem {
  id: string;
  sessionId: string;
  message: string;
}

interface UndoToastProps {
  item: UndoToastItem;
  onUndo: () => void;
  onDeleteStarted: () => boolean;
  onDeleteFailed: (restoreActiveSession: boolean) => void;
  onExpired: () => void;
}

const UNDO_DURATION_MS = 5000;

export const UndoToast: React.FC<UndoToastProps> = ({
  item,
  onUndo,
  onDeleteStarted,
  onDeleteFailed,
  onExpired,
}) => {
  const { t } = useTranslation();
  const deleteMutation = useDeleteSession();
  const [remainingMs, setRemainingMs] = React.useState(UNDO_DURATION_MS);
  const [paused, setPaused] = React.useState(false);
  const [deleteStarted, setDeleteStarted] = React.useState(false);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const remainingRef = React.useRef(UNDO_DURATION_MS);
  const expiredRef = React.useRef(false);

  const deleteMutationRef = React.useRef(deleteMutation);
  const onExpiredRef = React.useRef(onExpired);
  const onDeleteStartedRef = React.useRef(onDeleteStarted);
  const onDeleteFailedRef = React.useRef(onDeleteFailed);

  React.useEffect(() => {
    deleteMutationRef.current = deleteMutation;
    onExpiredRef.current = onExpired;
    onDeleteStartedRef.current = onDeleteStarted;
    onDeleteFailedRef.current = onDeleteFailed;
  }, [deleteMutation, onDeleteFailed, onDeleteStarted, onExpired]);

  const fireDeletion = React.useCallback(() => {
    if (expiredRef.current) return;
    expiredRef.current = true;
    beginSessionDeletion(item.sessionId);
    const restoreActiveSession = onDeleteStartedRef.current();
    setDeleteStarted(true);
    deleteMutationRef.current.mutate(item.sessionId, {
      onSuccess: () => onExpiredRef.current(),
      onError: () => {
        rollbackSessionDeletion(item.sessionId);
        onDeleteFailedRef.current(restoreActiveSession);
        onExpiredRef.current();
      },
    });
  }, [item.sessionId]);

  // Countdown runs only while not paused; pausing keeps the remaining
  // duration so resuming continues from the same point.
  React.useEffect(() => {
    if (paused || expiredRef.current) return;
    const base = remainingRef.current;
    if (base <= 0) return;

    const startTime = Date.now();
    intervalRef.current = setInterval(() => {
      const remaining = Math.max(0, base - (Date.now() - startTime));
      remainingRef.current = remaining;
      setRemainingMs(remaining);
      if (remaining <= 0 && intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    }, 100);

    timerRef.current = setTimeout(fireDeletion, base);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [paused, fireDeletion]);

  // Unmount safety net: no timer may outlive the toast.
  React.useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const handleUndo = () => {
    if (expiredRef.current) return;
    expiredRef.current = true;
    onUndo();
  };

  const pauseCountdown = () => setPaused(true);
  const resumeCountdown = () => setPaused(false);

  const progressPercent = (remainingMs / UNDO_DURATION_MS) * 100;

  return (
    <div
      className="undo-toast"
      role="status"
      onMouseEnter={pauseCountdown}
      onMouseLeave={resumeCountdown}
      onFocusCapture={pauseCountdown}
      onBlurCapture={resumeCountdown}
      data-testid={`undo-toast-${item.id}`}
    >
      <div className="undo-toast-content">
        <span className="undo-toast-message">{item.message}</span>
        <button
          type="button"
          className="undo-toast-button"
          onClick={handleUndo}
          disabled={deleteStarted}
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
