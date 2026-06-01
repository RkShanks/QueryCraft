import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminSso } from '../hooks/useAdminSso';
import { Shield, Plus, RefreshCw, Key, Settings, Trash2, Edit2, CheckCircle2, XCircle, X } from 'lucide-react';
import type { SsoProviderResponse, SsoProviderCreate, SsoProviderUpdate } from '../api/generated/types.gen';

interface Toast {
  id: string;
  type: 'success' | 'error';
  message: string;
}

const ALLOWED_ERROR_KEYS = new Set([
  'error.validation.oidcRequiredFields',
  'error.validation.samlRequiredFields',
  'error.conflict.duplicateProtocol',
  'error.forbidden',
  'error.unauthorized'
]);

function extractErrorKey(err: unknown): string | null {
  if (!err || typeof err !== 'object') {
    return null;
  }
  const obj = err as Record<string, unknown>;

  // 1. Direct message_key or error
  if (typeof obj.message_key === 'string' && obj.message_key) return obj.message_key;
  if (typeof obj.error === 'string' && obj.error) return obj.error;

  // 2. Direct detail (can be object or string)
  if (obj.detail) {
    if (typeof obj.detail === 'string' && obj.detail.startsWith('error.')) {
      return obj.detail;
    } else if (typeof obj.detail === 'object') {
      const key = extractErrorKey(obj.detail);
      if (key) return key;
    }
  }

  // 3. Direct body
  if (obj.body && typeof obj.body === 'object') {
    const key = extractErrorKey(obj.body);
    if (key) return key;
  }

  return null;
}

export const AdminSsoPage: React.FC = () => {
  const { t } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = (type: 'success' | 'error', message: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const getErrorMessage = (err: unknown, fallbackKey: string): string => {
    const key = extractErrorKey(err);
    if (key && ALLOWED_ERROR_KEYS.has(key)) {
      return t(key);
    }
    return t(fallbackKey);
  };

  const { listQuery, createMutation, updateMutation, deleteMutation } = useAdminSso({
    onCreateSuccess: () => {
      addToast('success', t('admin.sso.addSuccess') || 'SSO provider configured successfully');
      handleCancel();
    },
    onCreateError: (err: unknown) => {
      addToast('error', getErrorMessage(err, 'admin.sso.addError'));
    },
    onUpdateSuccess: () => {
      addToast('success', t('admin.sso.updateSuccess') || 'SSO provider updated successfully');
      handleCancel();
    },
    onUpdateError: (err: unknown) => {
      addToast('error', getErrorMessage(err, 'admin.sso.updateError'));
    },
    onDeleteSuccess: () => {
      addToast('success', t('admin.sso.deleteSuccess') || 'SSO provider deleted successfully');
    },
    onDeleteError: (err: unknown) => {
      addToast('error', getErrorMessage(err, 'admin.sso.deleteError'));
    },
  });

  const [isAddingOidc, setIsAddingOidc] = useState(false);
  const [isAddingSaml, setIsAddingSaml] = useState(false);
  const [editingProvider, setEditingProvider] = useState<SsoProviderResponse | undefined>(undefined);

  // Form State
  const [displayName, setDisplayName] = useState('');
  const [issuerUrl, setIssuerUrl] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [scopes, setScopes] = useState('openid email profile');
  const [redirectUri, setRedirectUri] = useState('');
  const [groupClaimName, setGroupClaimName] = useState('groups');

  const [samlEntityId, setSamlEntityId] = useState('');
  const [samlMetadataUrl, setSamlMetadataUrl] = useState('');
  const [samlMetadataXml, setSamlMetadataXml] = useState('');
  const [samlCertificate, setSamlCertificate] = useState('');

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleEdit = (provider: SsoProviderResponse) => {
    setEditingProvider(provider);
    setValidationError(null);
    setDisplayName(provider.display_name || '');
    setGroupClaimName(provider.group_claim_name || '');
    if (provider.protocol === 'oidc') {
      setIssuerUrl(provider.issuer_url || '');
      setClientId(provider.client_id || '');
      setClientSecret(provider.client_secret_masked || '●●●●●●●●');
      setScopes(provider.scopes || 'openid email profile');
      setRedirectUri(provider.redirect_uri || '');
    } else {
      setSamlEntityId(provider.saml_entity_id || '');
      setSamlMetadataUrl(provider.saml_metadata_url || '');
      setSamlMetadataXml(provider.saml_metadata_xml_masked || '●●●●●●●●');
      setSamlCertificate(provider.saml_certificate_masked || '●●●●●●●●');
    }
  };

  const handleCancel = () => {
    setIsAddingOidc(false);
    setIsAddingSaml(false);
    setEditingProvider(undefined);
    setValidationError(null);
    resetForm();
  };

  const resetForm = () => {
    setDisplayName('');
    setIssuerUrl('');
    setClientId('');
    setClientSecret('');
    setScopes('openid email profile');
    setRedirectUri('');
    setGroupClaimName('groups');
    setSamlEntityId('');
    setSamlMetadataUrl('');
    setSamlMetadataXml('');
    setSamlCertificate('');
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const isOidc = isAddingOidc || (editingProvider && editingProvider.protocol === 'oidc');

    if (isOidc) {
      if (!displayName || !issuerUrl || !clientId || !clientSecret) {
        setValidationError('error.validation.oidcRequiredFields');
        return;
      }
    } else {
      if (!displayName || !samlEntityId || (!samlMetadataUrl && !samlMetadataXml) || !samlCertificate) {
        setValidationError('error.validation.samlRequiredFields');
        return;
      }
    }

    if (editingProvider) {
      // Update
      const updateData: SsoProviderUpdate = {
        display_name: displayName,
        group_claim_name: groupClaimName,
      };

      if (isOidc) {
        updateData.issuer_url = issuerUrl;
        updateData.client_id = clientId;
        if (clientSecret !== '●●●●●●●●') {
          updateData.client_secret = clientSecret;
        }
        updateData.scopes = scopes;
        updateData.redirect_uri = redirectUri || undefined;
      } else {
        updateData.saml_entity_id = samlEntityId;
        updateData.saml_metadata_url = samlMetadataUrl || undefined;
        if (samlMetadataXml !== '●●●●●●●●') {
          updateData.saml_metadata_xml = samlMetadataXml || undefined;
        }
        if (samlCertificate !== '●●●●●●●●') {
          updateData.saml_certificate = samlCertificate || undefined;
        }
      }

      updateMutation.mutate({ id: editingProvider.id, data: updateData });
    } else {
      // Create
      const createData: SsoProviderCreate = {
        protocol: isOidc ? 'oidc' : 'saml',
        display_name: displayName,
        group_claim_name: groupClaimName,
      };

      if (isOidc) {
        createData.issuer_url = issuerUrl;
        createData.client_id = clientId;
        createData.client_secret = clientSecret;
        createData.scopes = scopes;
        createData.redirect_uri = redirectUri || undefined;
      } else {
        createData.saml_entity_id = samlEntityId;
        createData.saml_metadata_url = samlMetadataUrl || undefined;
        createData.saml_metadata_xml = samlMetadataXml || undefined;
        createData.saml_certificate = samlCertificate || undefined;
      }

      createMutation.mutate(createData);
    }
  };

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id);
  };

  if (listQuery.isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="animate-spin text-neon-cyan w-8 h-8" data-testid="loading-spinner" />
      </div>
    );
  }

  if (listQuery.isError) {
    return (
      <div className="flex justify-center items-center h-64 text-red-500 font-medium">
        {t('admin.sso.loadError')}
      </div>
    );
  }

  const providers: SsoProviderResponse[] = listQuery.data?.providers || [];

  if (isAddingOidc || isAddingSaml || editingProvider) {
    const isOidc = isAddingOidc || (editingProvider && editingProvider.protocol === 'oidc');
    const formTitle = editingProvider
      ? isOidc
        ? 'admin.sso.form.editOidcTitle'
        : 'admin.sso.form.editSamlTitle'
      : isOidc
      ? 'admin.sso.form.addOidcTitle'
      : 'admin.sso.form.addSamlTitle';

    return (
      <div className="p-6 max-w-4xl mx-auto bg-gray-900 border border-gray-800 rounded-xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex justify-between items-center border-b border-gray-800 pb-4">
          <h2 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Settings className="w-5 h-5 text-neon-cyan" />
            {t(formTitle)}
          </h2>
          <button onClick={handleCancel} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {validationError && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm font-medium flex items-center gap-2">
            <XCircle className="w-4 h-4 shrink-0" />
            {t(validationError)}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="displayName" className="block text-sm font-medium text-gray-400 mb-1">
                {t('admin.sso.form.displayName')}
              </label>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
              />
            </div>
            <div>
              <label htmlFor="groupClaimName" className="block text-sm font-medium text-gray-400 mb-1">
                {t('admin.sso.form.groupClaimName')}
              </label>
              <input
                id="groupClaimName"
                type="text"
                value={groupClaimName}
                onChange={(e) => setGroupClaimName(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
              />
            </div>
          </div>

          {isOidc ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="issuerUrl" className="block text-sm font-medium text-gray-400 mb-1">
                    {t('admin.sso.form.issuerUrl')}
                  </label>
                  <input
                    id="issuerUrl"
                    type="url"
                    value={issuerUrl}
                    onChange={(e) => setIssuerUrl(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="clientId" className="block text-sm font-medium text-gray-400 mb-1">
                    {t('admin.sso.form.clientId')}
                  </label>
                  <input
                    id="clientId"
                    type="text"
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="clientSecret" className="block text-sm font-medium text-gray-400 mb-1">
                    {t('admin.sso.form.clientSecret')}
                  </label>
                  <input
                    id="clientSecret"
                    type="password"
                    value={clientSecret}
                    onChange={(e) => setClientSecret(e.target.value)}
                    placeholder={editingProvider ? t('admin.sso.form.clientSecretPlaceholder') : undefined}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="scopes" className="block text-sm font-medium text-gray-400 mb-1">
                    {t('admin.sso.form.scopes')}
                  </label>
                  <input
                    id="scopes"
                    type="text"
                    value={scopes}
                    onChange={(e) => setScopes(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="redirectUri" className="block text-sm font-medium text-gray-400 mb-1">
                  {t('admin.sso.form.redirectUri')}
                </label>
                <input
                  id="redirectUri"
                  type="url"
                  value={redirectUri}
                  onChange={(e) => setRedirectUri(e.target.value)}
                  placeholder={t('admin.sso.form.redirectUriPlaceholder')}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="samlEntityId" className="block text-sm font-medium text-gray-400 mb-1">
                    {t('admin.sso.form.samlEntityId')}
                  </label>
                  <input
                    id="samlEntityId"
                    type="text"
                    value={samlEntityId}
                    onChange={(e) => setSamlEntityId(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="samlMetadataUrl" className="block text-sm font-medium text-gray-400 mb-1">
                    {t('admin.sso.form.samlMetadataUrl')}
                  </label>
                  <input
                    id="samlMetadataUrl"
                    type="url"
                    value={samlMetadataUrl}
                    onChange={(e) => setSamlMetadataUrl(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="samlMetadataXml" className="block text-sm font-medium text-gray-400 mb-1">
                  {t('admin.sso.form.samlMetadataXml')}
                </label>
                <textarea
                  id="samlMetadataXml"
                  value={samlMetadataXml}
                  onChange={(e) => setSamlMetadataXml(e.target.value)}
                  rows={4}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors font-mono text-xs"
                />
              </div>

              <div>
                <label htmlFor="samlCertificate" className="block text-sm font-medium text-gray-400 mb-1">
                  {t('admin.sso.form.samlCertificate')}
                </label>
                <textarea
                  id="samlCertificate"
                  value={samlCertificate}
                  onChange={(e) => setSamlCertificate(e.target.value)}
                  rows={4}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors font-mono text-xs"
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-800">
            <button
              type="button"
              onClick={handleCancel}
              className="px-4 py-2 border border-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50"
            >
              {t('common.save')}
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
      {/* Global Toast Container */}
      <div className="fixed top-6 end-6 z-50 flex flex-col gap-3 max-w-sm w-full select-none pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl backdrop-blur-md animate-fade-in transition-all ${
              t.type === 'success'
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {t.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" />
              )}
            </div>
            <div className="flex-1 text-sm font-medium leading-relaxed">{t.message}</div>
            <button
              onClick={() => setToasts((prev) => prev.filter((item) => item.id !== t.id))}
              className="shrink-0 text-gray-400 hover:text-white p-0.5 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary flex items-center gap-2">
            <Shield className="w-6 h-6 text-neon-cyan" />
            {t('admin.sso.title')}
          </h1>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setIsAddingOidc(true)}
            className="flex items-center gap-2 px-4 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors font-medium cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            {t('admin.sso.addOidc')}
          </button>
          <button
            onClick={() => setIsAddingSaml(true)}
            className="flex items-center gap-2 px-4 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors font-medium cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            {t('admin.sso.addSaml')}
          </button>
        </div>
      </div>

      {providers.length === 0 ? (
        <div className="p-12 border border-dashed border-gray-800 rounded-xl text-center text-gray-400">
          <Key className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="font-medium text-white mb-1">{t('admin.sso.emptyState')}</p>
          <p className="text-sm">{t('admin.sso.emptyStateDesc') || 'Configure an OIDC or SAML SSO provider to secure your enterprise workspace.'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-4 hover:border-gray-700 transition-colors flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-white text-lg">{provider.display_name}</h3>
                    <span className="inline-block mt-1 px-2 py-0.5 text-xs font-mono uppercase bg-gray-800 text-neon-cyan rounded">
                      {provider.protocol}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(provider)}
                      className="p-1.5 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
                      title={t('common.edit') || 'Edit'}
                      aria-label={t('common.edit')}
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(provider.id)}
                      className="p-1.5 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-red-500 transition-colors"
                      title={t('common.delete') || 'Delete'}
                      aria-label={t('common.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="border-t border-gray-800 pt-3 space-y-2 text-sm text-gray-400">
                  {provider.protocol === 'oidc' ? (
                    <>
                      <div className="flex justify-between">
                        <span>{t('admin.sso.form.issuerUrl') || 'Issuer URL'}:</span>
                        <span className="font-mono text-xs truncate max-w-xs">{provider.issuer_url}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>{t('admin.sso.form.clientId') || 'Client ID'}:</span>
                        <span className="font-mono text-xs truncate max-w-xs">{provider.client_id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>{t('admin.sso.form.clientSecret') || 'Client Secret'}:</span>
                        <span className="font-mono text-xs">{provider.client_secret_masked || '●●●●●●●●'}</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flex justify-between">
                        <span>{t('admin.sso.form.samlEntityId') || 'Entity ID'}:</span>
                        <span className="font-mono text-xs truncate max-w-xs">{provider.saml_entity_id}</span>
                      </div>
                      {provider.saml_metadata_url && (
                        <div className="flex justify-between">
                          <span>{t('admin.sso.form.samlMetadataUrl') || 'Metadata URL'}:</span>
                          <span className="font-mono text-xs truncate max-w-xs">{provider.saml_metadata_url}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span>{t('admin.sso.form.samlMetadataXml') || 'Metadata XML'}:</span>
                        <span className="font-mono text-xs">{provider.saml_metadata_xml_masked || '●●●●●●●●'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>{t('admin.sso.form.samlCertificate') || 'Certificate'}:</span>
                        <span className="font-mono text-xs">{provider.saml_certificate_masked || '●●●●●●●●'}</span>
                      </div>
                    </>
                  )}
                  <div className="flex justify-between border-t border-gray-800/50 pt-2">
                    <span>{t('admin.sso.form.groupClaimName') || 'Group Claim Name'}:</span>
                    <span className="font-mono text-xs">{provider.group_claim_name || 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
