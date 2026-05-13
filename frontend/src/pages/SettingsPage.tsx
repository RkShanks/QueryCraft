import React, { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminSettings, useUpdateAdminSettings } from '../hooks/useAdminSettings';
import './SettingsPage.css';

export const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const { data: settings, isLoading, error: loadError } = useAdminSettings();
  const updateMutation = useUpdateAdminSettings();

  const [contextCap, setContextCap] = useState<number>(3);
  const [inputError, setInputError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (settings?.llm_context_cap !== undefined) {
      setContextCap(settings.llm_context_cap);
    }
  }, [settings]);

  useEffect(() => {
    if (updateMutation.isSuccess) {
      setSuccessMsg(t('admin.settings.saved'));
      const timer = setTimeout(() => setSuccessMsg(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [updateMutation.isSuccess, t]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    if (isNaN(val) || e.target.value === '') {
      setInputError(null);
      setContextCap(NaN);
      return;
    }
    if (val < 0 || val > 10) {
      setInputError(t('admin.settings.contextCapHelp'));
    } else {
      setInputError(null);
    }
    setContextCap(val);
  }, [t]);

  const handleSave = useCallback(() => {
    if (isNaN(contextCap) || contextCap < 0 || contextCap > 10) {
      setInputError(t('admin.settings.contextCapHelp'));
      return;
    }
    setInputError(null);
    setSuccessMsg(null);
    updateMutation.mutate({ llm_context_cap: contextCap });
  }, [contextCap, updateMutation, t]);

  if (isLoading) {
    return (
      <div className="settings-page" data-testid="settings-page-loading">
        <div className="settings-spinner" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="settings-page" data-testid="settings-page-error">
        <p className="settings-error-text">{t('admin.settings.error')}</p>
      </div>
    );
  }

  return (
    <div className="settings-page" data-testid="settings-page">
      <h1 className="settings-title">{t('admin.settings.title')}</h1>

      <div className="settings-field">
        <label htmlFor="llm-context-cap" className="settings-label">
          {t('admin.settings.contextCap')}
        </label>
        <p className="settings-help">{t('admin.settings.contextCapHelp')}</p>
        <input
          id="llm-context-cap"
          className="settings-input"
          type="number"
          min={0}
          max={10}
          value={isNaN(contextCap) ? '' : contextCap}
          onChange={handleInputChange}
          data-testid="settings-llm-context-cap"
        />
        {inputError && (
          <p className="settings-field-error" data-testid="settings-input-error">
            {inputError}
          </p>
        )}
        {successMsg && (
          <p className="settings-success" data-testid="settings-success-msg">
            {successMsg}
          </p>
        )}
        {updateMutation.isError && (
          <p className="settings-error" data-testid="settings-error-msg">
            {t('admin.settings.error')}
          </p>
        )}
      </div>

      <button
        className="settings-save-btn"
        onClick={handleSave}
        disabled={updateMutation.isPending}
        data-testid="settings-save-btn"
      >
        {updateMutation.isPending ? t('admin.settings.save') + '...' : t('admin.settings.save')}
      </button>
    </div>
  );
};
