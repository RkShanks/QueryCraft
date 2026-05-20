import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../hooks/useConnections';
import { Database, Plus, RefreshCw, Server, Power, PowerOff, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { ConnectionForm } from '../components/admin/ConnectionForm';
import { ConnectionTestButton } from '../components/admin/ConnectionTestButton';
import { RefreshSchemaButton } from '../components/admin/RefreshSchemaButton';
import { ConnectionActions } from '../components/admin/ConnectionActions';
import type { ConnectionResponse, ConnectionCreate, ConnectionUpdate } from '../api/generated/types.gen';

export const AdminConnectionsPage: React.FC = () => {
  const { t } = useTranslation();
  const { listQuery, createMutation, updateMutation } = useConnections();
  const [isAdding, setIsAdding] = useState(false);
  const [editingConnection, setEditingConnection] = useState<ConnectionResponse | undefined>(undefined);

  if (listQuery.isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="animate-spin text-accent-cyan" data-testid="loading-spinner" />
      </div>
    );
  }

  if (listQuery.isError) {
    return (
      <div className="flex justify-center items-center h-64 text-red-500">
        {t('admin.connections.loadError')}
      </div>
    );
  }

  if (isAdding) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <ConnectionForm
          onSubmit={(data) => {
            createMutation.mutate(data as ConnectionCreate, {
              onSuccess: () => {
                setIsAdding(false);
              },
            });
          }}
          onCancel={() => setIsAdding(false)}
          isSubmitting={createMutation.isPending}
        />
      </div>
    );
  }

  if (editingConnection) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <ConnectionForm
          initialValues={editingConnection}
          onSubmit={(data) => {
            updateMutation.mutate(
              { id: editingConnection.id, data: data as ConnectionUpdate },
              {
                onSuccess: () => {
                  setEditingConnection(undefined);
                },
              }
            );
          }}
          onCancel={() => setEditingConnection(undefined)}
          isSubmitting={updateMutation.isPending}
        />
      </div>
    );
  }

  const connections = listQuery.data?.connections || [];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary flex items-center gap-2">
            <Database className="w-6 h-6 text-accent-cyan" />
            {t('admin.connections.title')}
          </h1>
        </div>
        <button
          onClick={() => setIsAdding(true)}
          className="flex items-center gap-2 px-4 py-2 bg-accent-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors font-medium"
        >
          <Plus className="w-4 h-4" />
          {t('admin.connections.add')}
        </button>
      </div>

      {connections.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center border border-border bg-bg-card rounded-lg shadow-sm">
          <Database className="w-12 h-12 text-text-muted mb-4 opacity-50" />
          <p className="text-text-secondary text-lg mb-4">{t('admin.connections.empty')}</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-bg-card shadow-sm">
          <table className="w-full text-start text-sm text-text-secondary">
            <thead className="text-xs text-text-primary uppercase bg-bg-elevated border-b border-border">
              <tr>
                <th className="px-6 py-4 font-medium text-start">{t('admin.connections.column.name')}</th>
                <th className="px-6 py-4 font-medium text-start">{t('admin.connections.column.type')}</th>
                <th className="px-6 py-4 font-medium text-start">{t('admin.connections.column.status')}</th>
                <th className="px-6 py-4 font-medium text-start">{t('admin.connections.column.schema')}</th>
                <th className="px-6 py-4 font-medium text-end">{t('admin.connections.column.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {connections.map((conn) => (
                <tr key={conn.id} className="hover:bg-bg-elevated/50 transition-colors">
                  <td className="px-6 py-4 font-medium text-text-primary">
                    {conn.display_name}
                  </td>
                  <td className="px-6 py-4">
                    <span className="flex items-center gap-2">
                      <Server className="w-4 h-4 text-text-muted" />
                      {t(`admin.connections.type.${conn.database_type}`)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-1.5">
                        {conn.lifecycle_state === 'active' ? (
                          <Power className="w-3.5 h-3.5 text-green-500" />
                        ) : (
                          <PowerOff className="w-3.5 h-3.5 text-text-muted" />
                        )}
                        <span className={conn.lifecycle_state === 'active' ? 'text-green-500' : 'text-text-muted'}>
                          {t(`admin.connections.lifecycle.${conn.lifecycle_state}`)}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs">
                        {conn.health_status === 'healthy' ? (
                          <CheckCircle2 className="w-3 h-3 text-green-500" />
                        ) : conn.health_status === 'unhealthy' ? (
                          <XCircle className="w-3 h-3 text-red-500" />
                        ) : (
                          <HelpCircle className="w-3 h-3 text-yellow-500" />
                        )}
                        <span className={
                          conn.health_status === 'healthy' ? 'text-green-500' :
                          conn.health_status === 'unhealthy' ? 'text-red-500' : 'text-yellow-500'
                        }>
                          {t(`admin.connections.status.${conn.health_status}`)}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1 text-xs">
                      <span className={
                        conn.schema_introspection_status === 'success' ? 'text-green-500' :
                        conn.schema_introspection_status === 'failed' ? 'text-red-500' :
                        conn.schema_introspection_status === 'stale' ? 'text-yellow-500' : 'text-text-muted'
                      }>
                        {t(`admin.connections.schema.${conn.schema_introspection_status}`)}
                      </span>
                      {conn.schema_last_refreshed_at ? (
                        <span className="text-text-muted">
                          {t('admin.connections.schema.refreshed', { time: new Date(conn.schema_last_refreshed_at).toLocaleDateString() })}
                        </span>
                      ) : (
                        <span className="text-text-muted">
                          {t('admin.connections.schema.neverRefreshed')}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-end">
                    <div className="flex items-center justify-end gap-3 flex-wrap">
                      <button
                        onClick={() => setEditingConnection(conn)}
                        className="inline-flex items-center justify-center px-3 py-1.5 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 select-none"
                      >
                        {t('common.edit')}
                      </button>
                      <ConnectionTestButton connectionId={conn.id} />
                      <RefreshSchemaButton
                        connectionId={conn.id}
                        schemaLastRefreshedAt={conn.schema_last_refreshed_at}
                      />
                      <ConnectionActions
                        connectionId={conn.id}
                        lifecycleState={conn.lifecycle_state as 'active' | 'disabled'}
                      />
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
