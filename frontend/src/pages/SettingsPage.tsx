import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminSettings, useUpdateAdminSettings } from '../hooks/useAdminSettings';
import './SettingsPage.css';

const SettingsForm: React.FC<{
  initialCap: number;
  updateMutation: ReturnType<typeof useUpdateAdminSettings>;
}> = ({ initialCap, updateMutation }) => {
  const { t } = useTranslation();
  const [contextCap, setContextCap] = useState<number>(initialCap);
  const [inputError, setInputError] = useState<string | null>(null);

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
    updateMutation.mutate({ llm_context_cap: contextCap });
  }, [contextCap, updateMutation, t]);

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
          onChange={handleInputChange}
          data-testid="settings-llm-context-cap"
        />
        {inputError && (
          <p className="settings-field-error" data-testid="settings-input-error">
            {inputError}
          </p>
        )}
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
      </div>

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
        key={`cap-${settings?.llm_context_cap ?? 3}`}
        initialCap={settings?.llm_context_cap ?? 3}
        updateMutation={updateMutation}
      />
    </div>
  );
};
