import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminRoles } from '../hooks/useAdminRoles';
import { GroupMappingEditor } from '../components/admin/GroupMappingEditor';
import { Shield, Plus, RefreshCw, Trash2, Edit2, CheckCircle2, XCircle, X, ShieldAlert } from 'lucide-react';
import type { Role, RoleCreateData, RoleUpdateData } from '../hooks/useAdminRoles';

interface Toast {
  id: string;
  type: 'success' | 'error';
  message: string;
}

const ALLOWED_ERROR_KEYS = new Set([
  'error.validation.roleRequiredFields',
  'error.conflict.duplicateRoleName',
  'error.conflict.duplicateRolePriority',
  'error.conflict.duplicateGroupMapping',
  'error.forbidden',
  'error.unauthorized',
  'error.builtinRoleProtected'
]);

const AVAILABLE_PERMISSIONS = [
  'query.submit',
  'query.history.view',
  'admin.connections.manage',
  'admin.roles.manage',
  'admin.sso.manage',
  'admin.audit.verify',
];

function extractErrorKey(err: unknown): string | null {
  if (!err || typeof err !== 'object') {
    return null;
  }
  const obj = err as Record<string, unknown>;

  if (typeof obj.message_key === 'string' && obj.message_key) return obj.message_key;
  if (typeof obj.error === 'string' && obj.error) return obj.error;

  if (obj.detail) {
    if (typeof obj.detail === 'string' && obj.detail.startsWith('error.')) {
      return obj.detail;
    } else if (typeof obj.detail === 'object') {
      const key = extractErrorKey(obj.detail);
      if (key) return key;
    }
  }

  if (obj.body && typeof obj.body === 'object') {
    const key = extractErrorKey(obj.body);
    if (key) return key;
  }

  return null;
}

export const AdminRolesPage: React.FC = () => {
  const { t } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isAdding, setIsAdding] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | undefined>(undefined);

  // Form states
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<number | ''>('');
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [mappedGroups, setMappedGroups] = useState<string[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

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

  const { listQuery, createMutation, updateMutation, deleteMutation } = useAdminRoles({
    onCreateSuccess: () => {
      addToast('success', t('admin.roles.addSuccess') || 'Role created successfully');
      handleCancel();
    },
    onCreateError: (err: unknown) => {
      addToast('error', getErrorMessage(err, 'admin.roles.addError'));
    },
    onUpdateSuccess: () => {
      addToast('success', t('admin.roles.updateSuccess') || 'Role updated successfully');
      handleCancel();
    },
    onUpdateError: (err: unknown) => {
      addToast('error', getErrorMessage(err, 'admin.roles.updateError'));
    },
    onDeleteSuccess: () => {
      addToast('success', t('admin.roles.deleteSuccess') || 'Role deleted successfully');
    },
    onDeleteError: (err: unknown) => {
      addToast('error', getErrorMessage(err, 'admin.roles.deleteError'));
    },
  });

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    setValidationError(null);
    setName(role.name);
    setDescription(role.description || '');
    setPriority(role.priority);
    setSelectedPermissions(role.permissions);
    setMappedGroups(role.group_mappings.map((gm) => gm.sso_group_value));
  };

  const handleCancel = () => {
    setIsAdding(false);
    setEditingRole(undefined);
    setValidationError(null);
    resetForm();
  };

  const resetForm = () => {
    setName('');
    setDescription('');
    setPriority('');
    setSelectedPermissions([]);
    setMappedGroups([]);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!name.trim() || priority === '') {
      setValidationError('error.validation.roleRequiredFields');
      return;
    }

    const priorityVal = typeof priority === 'string' ? parseInt(priority, 10) : priority;
    if (isNaN(priorityVal) || priorityVal < 0) {
      setValidationError('error.validation.roleRequiredFields');
      return;
    }

    if (editingRole) {
      const updateData: RoleUpdateData = {
        name,
        description: description || undefined,
        priority: priorityVal,
        permissions: selectedPermissions,
        group_mappings: mappedGroups,
      };
      updateMutation.mutate({ id: editingRole.id, data: updateData });
    } else {
      const createData: RoleCreateData = {
        name,
        description: description || undefined,
        priority: priorityVal,
        permissions: selectedPermissions,
        group_mappings: mappedGroups,
      };
      createMutation.mutate(createData);
    }
  };

  const handleDelete = (role: Role) => {
    if (role.is_builtin) {
      addToast('error', t('error.builtinRoleProtected') || 'Cannot delete built-in role');
      return;
    }
    if (window.confirm(t('admin.roles.deleteConfirm') || 'Are you sure you want to delete this role?')) {
      deleteMutation.mutate(role.id);
    }
  };

  const handlePermissionToggle = (permission: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permission)
        ? prev.filter((p) => p !== permission)
        : [...prev, permission]
    );
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
        {t('admin.roles.loadError')}
      </div>
    );
  }

  const roles: Role[] = listQuery.data?.roles || [];

  if (isAdding || editingRole) {
    const formTitle = editingRole ? 'admin.roles.form.editRoleTitle' : 'admin.roles.form.addRoleTitle';

    return (
      <div className="p-6 max-w-4xl mx-auto bg-gray-900 border border-gray-800 rounded-xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex justify-between items-center border-b border-gray-800 pb-4">
          <h2 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Shield className="w-5 h-5 text-neon-cyan" />
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

        <form onSubmit={handleSave} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="roleName" className="block text-sm font-medium text-gray-400 mb-1">
                {t('admin.roles.form.name')}
              </label>
              <input
                id="roleName"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={editingRole?.is_builtin}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors disabled:opacity-50"
              />
            </div>
            <div>
              <label htmlFor="rolePriority" className="block text-sm font-medium text-gray-400 mb-1">
                {t('admin.roles.form.priority')}
              </label>
              <input
                id="rolePriority"
                type="number"
                min="0"
                value={priority}
                onChange={(e) => setPriority(e.target.value === '' ? '' : Number(e.target.value))}
                disabled={editingRole?.is_builtin}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors disabled:opacity-50"
              />
            </div>
          </div>

          <div>
            <label htmlFor="roleDescription" className="block text-sm font-medium text-gray-400 mb-1">
              {t('admin.roles.form.description')}
            </label>
            <textarea
              id="roleDescription"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-3">
              {t('admin.roles.form.permissions') || 'Permissions'}
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {AVAILABLE_PERMISSIONS.map((perm) => (
                <label
                  key={perm}
                  htmlFor={`perm-${perm}`}
                  className="flex items-start gap-3 p-3 bg-gray-950 border border-gray-850 rounded-lg cursor-pointer hover:border-gray-800 transition-colors"
                >
                  <input
                    id={`perm-${perm}`}
                    type="checkbox"
                    checked={selectedPermissions.includes(perm)}
                    onChange={() => handlePermissionToggle(perm)}
                    disabled={editingRole?.is_builtin}
                    className="mt-1 accent-neon-cyan rounded"
                  />
                  <div>
                    <span className="text-sm font-semibold text-white block">
                      {t(`admin.roles.permissions.${perm}`)}
                    </span>
                    <span className="text-xs text-gray-500">
                      {t(`admin.roles.permissions.${perm}.desc`) || `Allows permission: ${perm}`}
                    </span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="border-t border-gray-800 pt-6">
            <GroupMappingEditor groups={mappedGroups} onChange={setMappedGroups} />
          </div>

          {editingRole?.is_builtin && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-sm flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 shrink-0" />
              <span>{t('admin.roles.builtinEditNote') || 'Built-in role name, priority, and permissions are protected and cannot be changed.'}</span>
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
            {t('admin.roles.title')}
          </h1>
        </div>
        <div>
          <button
            onClick={() => setIsAdding(true)}
            className="flex items-center gap-2 px-4 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors font-medium cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            {t('admin.roles.addRole')}
          </button>
        </div>
      </div>

      {roles.length === 0 ? (
        <div className="p-12 border border-dashed border-gray-800 rounded-xl text-center text-gray-400">
          <Shield className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="font-medium text-white mb-1">{t('admin.roles.emptyState')}</p>
          <p className="text-sm">{t('admin.roles.emptyStateDesc') || 'Create a custom role to configure connection policies and SSO mappings.'}</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
          <table className="w-full text-start border-collapse">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs font-semibold uppercase tracking-wider bg-gray-950">
                <th className="py-3 px-4 text-start">{t('admin.roles.table.name') || 'Name'}</th>
                <th className="py-3 px-4 text-start">{t('admin.roles.table.description') || 'Description'}</th>
                <th className="py-3 px-4 text-start">{t('admin.roles.table.priority') || 'Priority'}</th>
                <th className="py-3 px-4 text-start">{t('admin.roles.table.permissions') || 'Permissions'}</th>
                <th className="py-3 px-4 text-start">{t('admin.roles.table.mappings') || 'Group Mappings'}</th>
                <th className="py-3 px-4 text-end">{t('admin.roles.table.actions') || 'Actions'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50 text-sm text-gray-300">
              {roles.map((role) => (
                <tr key={role.id} className="hover:bg-gray-850/30 transition-colors">
                  <td className="py-3 px-4 font-semibold text-white">
                    <div className="flex items-center gap-2">
                      {role.name}
                      {role.is_builtin && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          {t('admin.roles.builtinProtected')}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-gray-400 max-w-xs truncate">{role.description || '-'}</td>
                  <td className="py-3 px-4 font-mono text-xs">{role.priority}</td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1 max-w-sm">
                      {role.permissions.map((p) => (
                        <span
                          key={p}
                          className="px-1.5 py-0.5 rounded text-xs font-mono bg-gray-800 text-gray-400 border border-gray-700/50"
                        >
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {role.group_mappings.length === 0 ? (
                        <span className="text-gray-500 text-xs italic">{t('admin.roles.table.noMappings') || 'None'}</span>
                      ) : (
                        role.group_mappings.map((gm) => (
                          <span
                            key={gm.id}
                            className="px-1.5 py-0.5 rounded text-xs bg-gray-900 border border-gray-850 text-neon-cyan font-medium"
                          >
                            {gm.sso_group_value}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-end">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleEdit(role)}
                        className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-white transition-colors"
                        title={t('common.edit')}
                        data-testid={`edit-role-${role.id}`}
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      {!role.is_builtin && (
                        <button
                          onClick={() => handleDelete(role)}
                          className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-red-500 transition-colors"
                          title={t('common.delete')}
                          data-testid={`delete-role-${role.id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
