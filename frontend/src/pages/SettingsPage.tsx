import React from 'react';
import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminSettings, useUpdateAdminSettings } from '../hooks/useAdminSettings';
import './SettingsPage.css';

const SettingsForm: React.FC<{
  initialCap: number;
  initialMaxRegen: number;
  updateMutation: ReturnType<typeof useUpdateAdminSettings>;
}> = ({ initialCap, initialMaxRegen, updateMutation }) => {
  const { t } = useTranslation();
  const [contextCap, setContextCap] = useState<number>(initialCap);
  const [maxRegen, setMaxRegen] = useState<number>(initialMaxRegen);
  const [contextCapError, setContextCapError] = useState<string | null>(null);
  const [maxRegenError, setMaxRegenError] = useState<string | null>(null);

  const handleContextCapChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    if (isNaN(val) || e.target.value === '') {
      setContextCapError(null);
      setContextCap(NaN);
      return;
    }
    if (val < 0 || val > 10) {
      setContextCapError(t('admin.settings.contextCapHelp'));
    } else {
      setContextCapError(null);
    }
    setContextCap(val);
  }, [t]);

  const handleMaxRegenChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    if (isNaN(val) || e.target.value === '') {
      setMaxRegenError(null);
      setMaxRegen(NaN);
      return;
    }
    if (val < 1 || val > 10) {
      setMaxRegenError(t('admin.settings.maxRegenerateAttemptsHelp'));
    } else {
      setMaxRegenError(null);
    }
    setMaxRegen(val);
  }, [t]);

  const handleSave = useCallback(() => {
    let valid = true;
    if (isNaN(contextCap) || contextCap < 0 || contextCap > 10) {
      setContextCapError(t('admin.settings.contextCapHelp'));
      valid = false;
    } else {
      setContextCapError(null);
    }
    if (isNaN(maxRegen) || maxRegen < 1 || maxRegen > 10) {
      setMaxRegenError(t('admin.settings.maxRegenerateAttemptsHelp'));
      valid = false;
    } else {
      setMaxRegenError(null);
    }
    if (!valid) return;
    updateMutation.mutate({ llm_context_cap: contextCap, max_regenerate_attempts: maxRegen });
  }, [contextCap, maxRegen, updateMutation, t]);

  React.useEffect(() => {
    if (updateMutation.isSuccess || updateMutation.isError) {
      const timer = setTimeout(() => {
        updateMutation.reset();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [updateMutation]);

  const showSuccess = updateMutation.isSuccess;

  return (
    <>
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
          onChange={handleContextCapChange}
          data-testid="settings-llm-context-cap"
        />
        {contextCapError && (
          <p className="settings-field-error" data-testid="settings-context-cap-error">
            {contextCapError}
          </p>
        )}
      </div>

      <div className="settings-field">
        <label htmlFor="max-regenerate-attempts" className="settings-label">
          {t('admin.settings.maxRegenerateAttempts')}
        </label>
        <p className="settings-help">{t('admin.settings.maxRegenerateAttemptsHelp')}</p>
        <input
          id="max-regenerate-attempts"
          className="settings-input"
          type="number"
          min={1}
          max={10}
          value={isNaN(maxRegen) ? '' : maxRegen}
          onChange={handleMaxRegenChange}
          data-testid="settings-max-regenerate-attempts"
        />
        {maxRegenError && (
          <p className="settings-field-error" data-testid="settings-max-regen-error">
            {maxRegenError}
          </p>
        )}
      </div>

      {showSuccess && (
        <p className="settings-success" data-testid="settings-success-msg">
          {t('admin.settings.saved')}
        </p>
      )}
      {updateMutation.isError && (
        <p className="settings-error" data-testid="settings-error-msg">
          {t('admin.settings.error')}
        </p>
      )}

      <button
        className="settings-save-btn"
        onClick={handleSave}
        disabled={updateMutation.isPending}
        data-testid="settings-save-btn"
      >
        {updateMutation.isPending ? t('admin.settings.save') + '...' : t('admin.settings.save')}
      </button>
    </>
  );
};

export const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const { data: settings, isLoading, error: loadError } = useAdminSettings();
  const updateMutation = useUpdateAdminSettings();

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
      <SettingsForm
        key={`cap-${settings?.llm_context_cap ?? 3}-regen-${settings?.max_regenerate_attempts ?? 3}`}
        initialCap={settings?.llm_context_cap ?? 3}
        initialMaxRegen={settings?.max_regenerate_attempts ?? 3}
        updateMutation={updateMutation}
      />
    </div>
  );
};
