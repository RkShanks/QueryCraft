import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import type {
  ConnectionResponse,
  ConnectionCreate,
  ConnectionUpdate,
  DatabaseType,
} from '../../api/generated/types.gen';

export interface ConnectionFormProps {
  initialValues?: ConnectionResponse;
  onSubmit: (data: any) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export const ConnectionForm: React.FC<ConnectionFormProps> = ({
  initialValues,
  onSubmit,
  onCancel,
  isSubmitting = false,
}) => {
  const { t } = useTranslation();
  const isEdit = !!initialValues;

  const [displayName, setDisplayName] = useState('');
  const [databaseType, setDatabaseType] = useState<DatabaseType>('postgresql');
  const [host, setHost] = useState('');
  const [port, setPort] = useState<number>(5432);
  const [databaseName, setDatabaseName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [sslMode, setSslMode] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});

  // Initialize form values from initialValues if in edit mode
  useEffect(() => {
    if (initialValues) {
      setDisplayName(initialValues.display_name || '');
      setDatabaseType(initialValues.database_type || 'postgresql');
      setHost(initialValues.host || '');
      setPort(initialValues.port ?? 5432);
      setDatabaseName(initialValues.database_name || '');
      setUsername(initialValues.username || '');
      setSslMode(initialValues.ssl_mode || '');
      setPassword(''); // Password never populated for editing
    }
  }, [initialValues]);

  // Handle port auto-fill when database type changes
  const handleDatabaseTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextType = e.target.value as DatabaseType;
    setDatabaseType(nextType);

    // Auto-fill ports based on dialect
    if (nextType === 'postgresql') {
      setPort(5432);
    } else if (nextType === 'mysql') {
      setPort(3306);
    } else if (nextType === 'mssql') {
      setPort(1433);
    }
  };

  const handleValidation = (): boolean => {
    const nextErrors: Record<string, string> = {};

    if (!displayName.trim()) {
      nextErrors.displayName = t('admin.connections.form.required');
    }
    if (!host.trim()) {
      nextErrors.host = t('admin.connections.form.required');
    }
    if (!username.trim()) {
      nextErrors.username = t('admin.connections.form.required');
    }
    if (!databaseName.trim()) {
      nextErrors.databaseName = t('admin.connections.form.required');
    }

    // Port validation
    if (!port || isNaN(port) || port < 1 || port > 65535) {
      nextErrors.port = t('admin.connections.form.invalidPort');
    }

    // Password validation is only required in create mode
    if (!isEdit && !password) {
      nextErrors.password = t('admin.connections.form.required');
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!handleValidation()) {
      return;
    }

    if (isEdit) {
      const updatePayload: ConnectionUpdate = {
        display_name: displayName,
        database_type: databaseType,
        host: host,
        port: port,
        database_name: databaseName,
        username: username,
        ssl_mode: sslMode || null,
      };

      // Only include password if the user typed a new one
      if (password) {
        updatePayload.password = password;
      }

      onSubmit(updatePayload);
    } else {
      const createPayload: ConnectionCreate = {
        display_name: displayName,
        database_type: databaseType,
        host: host,
        port: port,
        database_name: databaseName,
        username: username,
        password: password,
        ssl_mode: sslMode || undefined,
      };

      onSubmit(createPayload);
    }
  };

  return (
    <div className="bg-bg-card border border-border rounded-lg shadow-lg p-6 max-w-2xl mx-auto space-y-6 text-start">
      <div>
        <h2 className="text-xl font-semibold text-text-primary">
          {isEdit ? t('admin.connections.form.editTitle') : t('admin.connections.form.createTitle')}
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="displayName" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.displayName')}
            </label>
            <input
              id="displayName"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
            {errors.displayName && <p className="text-xs text-red-500 mt-1">{errors.displayName}</p>}
          </div>

          <div>
            <label htmlFor="databaseType" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.databaseType')}
            </label>
            <select
              id="databaseType"
              value={databaseType}
              onChange={handleDatabaseTypeChange}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            >
              <option value="postgresql">{t('admin.connections.type.postgresql')}</option>
              <option value="mysql">{t('admin.connections.type.mysql')}</option>
              <option value="mssql">{t('admin.connections.type.mssql')}</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2">
            <label htmlFor="host" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.host')}
            </label>
            <input
              id="host"
              type="text"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
            {errors.host && <p className="text-xs text-red-500 mt-1">{errors.host}</p>}
          </div>

          <div>
            <label htmlFor="port" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.port')}
            </label>
            <input
              id="port"
              type="number"
              value={port || ''}
              onChange={(e) => setPort(parseInt(e.target.value, 10))}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
            {errors.port && <p className="text-xs text-red-500 mt-1">{errors.port}</p>}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="databaseName" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.databaseName')}
            </label>
            <input
              id="databaseName"
              type="text"
              value={databaseName}
              onChange={(e) => setDatabaseName(e.target.value)}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
            {errors.databaseName && <p className="text-xs text-red-500 mt-1">{errors.databaseName}</p>}
          </div>

          <div>
            <label htmlFor="username" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.username')}
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
            {errors.username && <p className="text-xs text-red-500 mt-1">{errors.username}</p>}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="password" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.password')}
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isEdit ? '••••••••' : ''}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
            {isEdit && (
              <span className="block text-[11px] text-text-muted mt-1 select-none">
                {t('admin.connections.form.passwordHelpEdit')}
              </span>
            )}
            {errors.password && <p className="text-xs text-red-500 mt-1">{errors.password}</p>}
          </div>

          <div>
            <label htmlFor="sslMode" className="block text-xs font-semibold text-text-secondary mb-1.5 select-none">
              {t('admin.connections.form.sslMode')}
            </label>
            <input
              id="sslMode"
              type="text"
              value={sslMode}
              onChange={(e) => setSslMode(e.target.value)}
              className="w-full px-3 py-2.5 bg-bg-elevated border border-border rounded-md text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 bg-transparent hover:bg-bg-elevated border border-border text-text-primary rounded-md text-sm transition-all font-medium select-none"
          >
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-4 py-2 bg-accent-cyan text-gray-900 hover:bg-opacity-90 rounded-md text-sm transition-all font-medium disabled:opacity-50 disabled:cursor-not-allowed select-none"
          >
            {isSubmitting
              ? t('query.input.submitting')
              : isEdit
                ? t('admin.connections.form.submit.edit')
                : t('admin.connections.form.submit.create')}
          </button>
        </div>
      </form>
    </div>
  );
};
