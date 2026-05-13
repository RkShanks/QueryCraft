import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { ThumbsUp, ThumbsDown } from '../icons';
import './ResponseFeedbackBar.css';

interface ResponseFeedbackBarProps {
  attemptId: string;
  currentFeedback?: number | null;
  saved?: boolean;
  onFeedback: (attemptId: string, feedback: number) => void;
}

export const ResponseFeedbackBar: React.FC<ResponseFeedbackBarProps> = ({
  attemptId,
  currentFeedback,
  saved,
  onFeedback,
}) => {
  const { t } = useTranslation();

  const isThumbsUp = currentFeedback === 1;
  const isThumbsDown = currentFeedback === -1;

  const handleThumbsUp = useCallback(() => {
    if (!isThumbsUp) {
      onFeedback(attemptId, 1);
    }
  }, [attemptId, isThumbsUp, onFeedback]);

  const handleThumbsDown = useCallback(() => {
    if (!isThumbsDown) {
      onFeedback(attemptId, -1);
    }
  }, [attemptId, isThumbsDown, onFeedback]);

  const handleRemoveFeedback = useCallback(() => {
    if (isThumbsUp || isThumbsDown) {
      onFeedback(attemptId, 0);
    }
  }, [attemptId, isThumbsUp, isThumbsDown, onFeedback]);

  const onThumbsUpClick = useCallback(() => {
    if (isThumbsUp) {
      handleRemoveFeedback();
    } else {
      handleThumbsUp();
    }
  }, [isThumbsUp, handleRemoveFeedback, handleThumbsUp]);

  const onThumbsDownClick = useCallback(() => {
    if (isThumbsDown) {
      handleRemoveFeedback();
    } else {
      handleThumbsDown();
    }
  }, [isThumbsDown, handleRemoveFeedback, handleThumbsDown]);

  return (
    <div className="response-feedback-bar" data-testid="response-feedback-bar">
      <button
        className={`feedback-btn ${isThumbsUp ? 'feedback-btn-active-up' : ''}`}
        onClick={onThumbsUpClick}
        data-testid="feedback-thumbs-up"
        title={t('feedback.thumbsUp')}
        aria-pressed={isThumbsUp}
      >
        <ThumbsUp className="feedback-icon" />
        {isThumbsUp && saved && (
          <span className="feedback-saved-label" data-testid="feedback-saved-label">
            {t('feedback.saved')}
          </span>
        )}
      </button>
      <button
        className={`feedback-btn ${isThumbsDown ? 'feedback-btn-active-down' : ''}`}
        onClick={onThumbsDownClick}
        data-testid="feedback-thumbs-down"
        title={t('feedback.thumbsDown')}
        aria-pressed={isThumbsDown}
      >
        <ThumbsDown className="feedback-icon" />
      </button>
    </div>
  );
};
