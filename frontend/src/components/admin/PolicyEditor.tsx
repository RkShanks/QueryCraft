import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, Edit2, X, Shield, AlertTriangle, Info, Database } from 'lucide-react';
import { useConnections } from '../../hooks/useConnections';
import { useConnectionSchema } from '../../hooks/useConnectionSchema';
import type { ConnectionPolicyItem } from '../../hooks/useAdminRoles';

interface ConnectionListItem {
  id: string;
  display_name: string;
  database_type: string;
}

interface PolicyEditorProps {
  policies: ConnectionPolicyItem[];
  onChange: (policies: ConnectionPolicyItem[]) => void;
}

export const PolicyEditor: React.FC<PolicyEditorProps> = ({ policies, onChange }) => {
  const { t } = useTranslation();
  const { listQuery } = useConnections();
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  // Active policy being configured
  const [activePolicy, setActivePolicy] = useState<ConnectionPolicyItem | null>(null);

  // Connections list helper
  const connections = (
    Array.isArray(listQuery.data)
      ? listQuery.data
      : (listQuery.data as unknown as { connections?: unknown[] })?.connections || []
  ) as unknown as ConnectionListItem[];

  // Active connection schema
  const { data: schema, isLoading: isLoadingSchema, isError: isErrorSchema } = useConnectionSchema(
    activePolicy?.connection_id || null
  );

  // Compute real-time validation on activePolicy row_filters change dynamically (no state/useEffect to avoid cascading renders)
  const getValidationErrors = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (!activePolicy || !schema) return errors;

    activePolicy.row_filters.forEach((rf, idx) => {
      if (!rf.table) {
        errors[`filter-table-${idx}`] = t('admin.roles.form.invalidTableName');
        return;
      }
      if (!rf.filter.trim()) {
        errors[`filter-val-${idx}`] = t('admin.roles.form.filterEmpty');
        return;
      }

      // Check comments
      if (rf.filter.includes('--') || rf.filter.includes('/*') || rf.filter.includes('*/')) {
        errors[`filter-val-${idx}`] = t('admin.roles.form.filterValidationFailed');
        return;
      }

      // Check forbidden SQL constructs
      const normalized = rf.filter.toLowerCase();
      const dangerousKeywords = [
        'select', 'union', 'join', 'update', 'delete', 'insert', 'truncate',
        'drop', 'alter', 'create', 'grant', 'revoke', 'into', 'from'
      ];
      for (const keyword of dangerousKeywords) {
        const regex = new RegExp(`\\b${keyword}\\b`, 'i');
        if (regex.test(normalized)) {
          errors[`filter-val-${idx}`] = t('admin.roles.form.filterValidationFailed');
          return;
        }
      }

      // Check user placeholders
      const placeholderRegex = /\{user\.([^}]+)\}/g;
      let match;
      const validPlaceholders = ['email', 'subject_id', 'role'];
      while ((match = placeholderRegex.exec(rf.filter)) !== null) {
        const key = match[1];
        if (!validPlaceholders.includes(key)) {
          errors[`filter-val-${idx}`] = t('admin.roles.form.filterPlaceholderError');
          return;
        }
      }

      // Check column existence
      const targetTableSchema = schema.tables.find(t => t.table_name === rf.table);
      const allowedCols = activePolicy.allowed_tables.find(t => t.table === rf.table)?.columns || [];
      if (targetTableSchema) {
        const cleanSql = rf.filter
          .replace(/'[^']*'/g, '') // remove string literals
          .replace(/\{user\.[^}]+\}/g, '') // remove placeholders
          .replace(/[(),.=+<>!\-*/]/g, ' '); // replace operators with spaces

        const words = cleanSql
          .split(/\s+/)
          .map(w => w.trim().toLowerCase())
          .filter(w => w.length > 0 && /^[a-z_][a-z0-9_]*$/.test(w));

        const sqlReservedWords = new Set([
          'and', 'or', 'not', 'in', 'is', 'null', 'like', 'between', 'exists',
          'true', 'false', 'any', 'all', 'some', 'current_date', 'current_time', 'now'
        ]);

        for (const word of words) {
          if (sqlReservedWords.has(word)) continue;
          if (!isNaN(Number(word))) continue;

          const hasColumn = allowedCols.some(c => c.toLowerCase() === word);
          if (!hasColumn) {
            errors[`filter-val-${idx}`] = t('admin.roles.form.columnNotFound', {
              column: word,
              table: rf.table,
            });
            return;
          }
        }
      }
    });

    return errors;
  };

  const validationErrors = getValidationErrors();

  const handleAddClick = () => {
    setActivePolicy({
      connection_id: '',
      allowed_tables: [],
      row_filters: [],
      column_masks: [],
    });
    setEditingIndex(null);
    setIsAdding(true);
  };

  const handleEditClick = (index: number) => {
    setActivePolicy(JSON.parse(JSON.stringify(policies[index])));
    setEditingIndex(index);
    setIsAdding(true);
  };

  const handleDeleteClick = (index: number) => {
    const next = [...policies];
    next.splice(index, 1);
    onChange(next);
  };

  const handleConnectionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (!activePolicy) return;
    setActivePolicy({
      ...activePolicy,
      connection_id: e.target.value,
      allowed_tables: [],
      row_filters: [],
      column_masks: [],
    });
  };

  // Toggle allowed table
  const handleTableToggle = (tableName: string, allColumns: string[]) => {
    if (!activePolicy) return;
    const existingIndex = activePolicy.allowed_tables.findIndex(t => t.table === tableName);

    const nextAllowed = [...activePolicy.allowed_tables];
    if (existingIndex > -1) {
      nextAllowed.splice(existingIndex, 1);
      // Clean up row filters and column masks for this table
      const nextFilters = activePolicy.row_filters.filter(rf => rf.table !== tableName);
      const nextMasks = activePolicy.column_masks.filter(cm => cm.table !== tableName);
      setActivePolicy({
        ...activePolicy,
        allowed_tables: nextAllowed,
        row_filters: nextFilters,
        column_masks: nextMasks,
      });
    } else {
      nextAllowed.push({ table: tableName, columns: [...allColumns] });
      setActivePolicy({
        ...activePolicy,
        allowed_tables: nextAllowed,
      });
    }
  };

  // Toggle allowed column within table
  const handleColumnToggle = (tableName: string, columnName: string) => {
    if (!activePolicy) return;
    const nextAllowed = activePolicy.allowed_tables.map(t => {
      if (t.table !== tableName) return t;
      const hasCol = t.columns.includes(columnName);
      const nextCols = hasCol
        ? t.columns.filter(c => c !== columnName)
        : [...t.columns, columnName];
      return { ...t, columns: nextCols };
    });

    // Clean up column masks that are no longer allowed columns
    const nextMasks = activePolicy.column_masks.map(m => {
      if (m.table !== tableName) return m;
      return {
        ...m,
        columns: m.columns.filter(c => {
          const tableConfig = nextAllowed.find(t => t.table === tableName);
          return tableConfig?.columns.includes(c);
        })
      };
    }).filter(m => m.columns.length > 0);

    setActivePolicy({
      ...activePolicy,
      allowed_tables: nextAllowed,
      column_masks: nextMasks,
    });
  };

  // Add Row Filter entry
  const handleAddRowFilter = () => {
    if (!activePolicy) return;
    setActivePolicy({
      ...activePolicy,
      row_filters: [...activePolicy.row_filters, { table: '', filter: '' }],
    });
  };

  // Update Row Filter entry
  const handleUpdateRowFilter = (index: number, key: 'table' | 'filter', value: string) => {
    if (!activePolicy) return;
    const nextFilters = [...activePolicy.row_filters];
    nextFilters[index] = { ...nextFilters[index], [key]: value };
    setActivePolicy({ ...activePolicy, row_filters: nextFilters });
  };

  // Remove Row Filter entry
  const handleRemoveRowFilter = (index: number) => {
    if (!activePolicy) return;
    const nextFilters = [...activePolicy.row_filters];
    nextFilters.splice(index, 1);
    setActivePolicy({ ...activePolicy, row_filters: nextFilters });
  };

  // Add Column Mask entry
  const handleAddColumnMask = () => {
    if (!activePolicy) return;
    setActivePolicy({
      ...activePolicy,
      column_masks: [...activePolicy.column_masks, { table: '', columns: [] }],
    });
  };

  // Update Column Mask entry table
  const handleUpdateColumnMaskTable = (index: number, tableName: string) => {
    if (!activePolicy) return;
    const nextMasks = [...activePolicy.column_masks];
    nextMasks[index] = { table: tableName, columns: [] };
    setActivePolicy({ ...activePolicy, column_masks: nextMasks });
  };

  // Toggle column within Column Mask
  const handleToggleColumnMask = (index: number, columnName: string) => {
    if (!activePolicy) return;
    const nextMasks = [...activePolicy.column_masks];
    const mask = nextMasks[index];
    const hasCol = mask.columns.includes(columnName);
    const nextCols = hasCol
      ? mask.columns.filter(c => c !== columnName)
      : [...mask.columns, columnName];

    nextMasks[index] = { ...mask, columns: nextCols };
    setActivePolicy({ ...activePolicy, column_masks: nextMasks });
  };

  // Remove Column Mask entry
  const handleRemoveColumnMask = (index: number) => {
    if (!activePolicy) return;
    const nextMasks = [...activePolicy.column_masks];
    nextMasks.splice(index, 1);
    setActivePolicy({ ...activePolicy, column_masks: nextMasks });
  };

  // Save the active policy configuration
  const handleSaveActive = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activePolicy) return;

    // Validation
    if (!activePolicy.connection_id) {
      alert(t('admin.roles.form.connectionRequired'));
      return;
    }

    // Check duplicate connection policy (unless editing same index)
    const duplicateIndex = policies.findIndex(
      (p, idx) => p.connection_id === activePolicy.connection_id && idx !== editingIndex
    );
    if (duplicateIndex > -1) {
      alert(t('admin.roles.form.duplicateConnectionPolicy'));
      return;
    }

    if (activePolicy.allowed_tables.length === 0) {
      alert(t('admin.roles.form.noAllowedTables'));
      return;
    }

    const emptyTable = activePolicy.allowed_tables.find(t => t.columns.length === 0);
    if (emptyTable) {
      alert(t('admin.roles.form.noAllowedColumns'));
      return;
    }

    if (Object.keys(validationErrors).length > 0) {
      alert(t('admin.roles.form.validationError'));
      return;
    }

    // Clean up empty column masks
    const cleanedMasks = activePolicy.column_masks.filter(cm => cm.table && cm.columns.length > 0);
    const policyToSave = { ...activePolicy, column_masks: cleanedMasks };

    const nextPolicies = [...policies];
    if (editingIndex !== null) {
      nextPolicies[editingIndex] = policyToSave;
    } else {
      nextPolicies.push(policyToSave);
    }

    onChange(nextPolicies);
    setIsAdding(false);
    setActivePolicy(null);
  };

  const handleCancelActive = () => {
    setIsAdding(false);
    setActivePolicy(null);
  };

  // Resolve connection display name
  const getConnectionName = (connId: string) => {
    const conn = connections.find((c: ConnectionListItem) => c.id === connId);
    return conn ? conn.display_name : connId;
  };

  if (isAdding && activePolicy) {
    const availableConnections = connections.filter((c: ConnectionListItem) => {
      // Allow current connection or connections not yet configured
      return c.id === activePolicy.connection_id || !policies.some(p => p.connection_id === c.id);
    });

    return (
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-6 animate-in fade-in duration-300">
        <div className="flex justify-between items-center border-b border-gray-800 pb-3">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-neon-cyan" />
            {editingIndex !== null ? t('admin.roles.form.editPolicy') : t('admin.roles.form.addPolicy')}
          </h3>
          <button
            type="button"
            onClick={handleCancelActive}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Connection Selector */}
          <div>
            <label htmlFor="policyConnection" className="block text-sm font-medium text-gray-400 mb-1">
              {t('admin.roles.form.selectConnection')}
            </label>
            <select
              id="policyConnection"
              value={activePolicy.connection_id}
              onChange={handleConnectionChange}
              disabled={editingIndex !== null}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors disabled:opacity-50"
            >
              <option value="">-- {t('admin.roles.form.selectConnection')} --</option>
              {availableConnections.map((c: ConnectionListItem) => (
                <option key={c.id} value={c.id}>
                  {c.display_name} ({c.database_type})
                </option>
              ))}
            </select>
          </div>

          {activePolicy.connection_id && (
            <>
              {isLoadingSchema && (
                <div className="text-center py-6 text-gray-400 flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-neon-cyan border-t-transparent rounded-full animate-spin"></span>
                  {t('admin.roles.form.loadingSchema')}
                </div>
              )}

              {isErrorSchema && (
                <div className="text-center py-6 text-red-400 flex items-center justify-center gap-2">
                  <AlertTriangle className="w-5 h-5" />
                  {t('admin.roles.form.schemaLoadFailed')}
                </div>
              )}

              {schema && (
                <div className="space-y-6">
                  {/* Schema Browser / Table column allow-list */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-gray-300 border-b border-gray-900 pb-1 flex items-center gap-2">
                      <Database className="w-4 h-4 text-neon-cyan" />
                      {t('admin.roles.form.allowedTables')}
                    </h4>
                    {schema.tables.length === 0 ? (
                      <p className="text-sm text-gray-500 italic">{t('admin.roles.form.emptySchema')}</p>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {schema.tables.map(table => {
                          const tableConfig = activePolicy.allowed_tables.find(t => t.table === table.table_name);
                          const isTableAllowed = !!tableConfig;

                          return (
                            <div key={table.table_name} className="bg-gray-900 border border-gray-850 rounded-lg p-3 space-y-2">
                              <label className="flex items-center gap-2 font-semibold text-white cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={isTableAllowed}
                                  data-testid={`table-checkbox-${table.table_name}`}
                                  onChange={() => handleTableToggle(table.table_name, table.columns.map(c => c.column_name))}
                                  className="accent-neon-cyan rounded"
                                />
                                <span>{table.table_name}</span>
                              </label>

                              {isTableAllowed && tableConfig && (
                                <div className="ps-6 pt-1 grid grid-cols-2 gap-2 border-t border-gray-800">
                                  {table.columns.map(col => {
                                    const isColAllowed = tableConfig.columns.includes(col.column_name);

                                    return (
                                      <label key={col.column_name} className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer select-none">
                                        <input
                                          type="checkbox"
                                          checked={isColAllowed}
                                          data-testid={`column-checkbox-${table.table_name}-${col.column_name}`}
                                          onChange={() => handleColumnToggle(table.table_name, col.column_name)}
                                          className="accent-neon-cyan rounded"
                                        />
                                        <span className={isColAllowed ? "text-gray-200 font-medium" : ""}>
                                          {col.column_name}
                                        </span>
                                      </label>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Row-Level Filters */}
                  {activePolicy.allowed_tables.length > 0 && (
                    <div className="space-y-3 border-t border-gray-800 pt-4">
                      <div className="flex justify-between items-center">
                        <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                          <Info className="w-4 h-4 text-neon-cyan" />
                          {t('admin.roles.form.rowFilters')}
                        </h4>
                        <button
                          type="button"
                          onClick={handleAddRowFilter}
                          className="text-xs bg-gray-900 border border-gray-800 text-neon-cyan px-2 py-1 rounded hover:bg-gray-850 transition-colors flex items-center gap-1"
                        >
                          <Plus className="w-3 h-3" />
                          {t('admin.roles.form.addFilter')}
                        </button>
                      </div>

                      {activePolicy.row_filters.length === 0 ? (
                        <p className="text-xs text-gray-500 italic">{t('admin.roles.form.noRowFilters')}</p>
                      ) : (
                        <div className="space-y-3">
                          {activePolicy.row_filters.map((rf, idx) => (
                            <div key={idx} className="flex flex-col gap-2 p-3 bg-gray-900 border border-gray-850 rounded-lg">
                              <div className="flex gap-2 items-center">
                                <select
                                  value={rf.table}
                                  onChange={e => handleUpdateRowFilter(idx, 'table', e.target.value)}
                                  className="bg-gray-950 border border-gray-800 rounded px-2 py-1 text-sm text-white"
                                >
                                  <option value="">-- {t('admin.roles.form.table')} --</option>
                                  {activePolicy.allowed_tables.map(t => (
                                    <option key={t.table} value={t.table}>{t.table}</option>
                                  ))}
                                </select>
                                <input
                                  type="text"
                                  value={rf.filter}
                                  onChange={e => handleUpdateRowFilter(idx, 'filter', e.target.value)}
                                  placeholder={t('admin.roles.form.filterPlaceholder')}
                                  aria-invalid={!!validationErrors[`filter-val-${idx}`]}
                                  className={`flex-1 bg-gray-950 border rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-neon-cyan ${
                                    validationErrors[`filter-val-${idx}`] ? 'border-red-500' : 'border-gray-800'
                                  }`}
                                />
                                <button
                                  type="button"
                                  onClick={() => handleRemoveRowFilter(idx)}
                                  className="text-gray-500 hover:text-red-400 p-1 rounded transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                              {validationErrors[`filter-val-${idx}`] && (
                                <p className="text-xs text-red-400 mt-1">
                                  {validationErrors[`filter-val-${idx}`]}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Column Masks */}
                  {activePolicy.allowed_tables.length > 0 && (
                    <div className="space-y-3 border-t border-gray-800 pt-4">
                      <div className="flex justify-between items-center">
                        <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                          <Shield className="w-4 h-4 text-neon-cyan" />
                          {t('admin.roles.form.columnMasks')}
                        </h4>
                        <button
                          type="button"
                          onClick={handleAddColumnMask}
                          className="text-xs bg-gray-900 border border-gray-800 text-neon-cyan px-2 py-1 rounded hover:bg-gray-850 transition-colors flex items-center gap-1"
                        >
                          <Plus className="w-3 h-3" />
                          {t('admin.roles.form.addMask')}
                        </button>
                      </div>

                      {activePolicy.column_masks.length === 0 ? (
                        <p className="text-xs text-gray-500 italic">{t('admin.roles.form.noColumnMasks')}</p>
                      ) : (
                        <div className="space-y-3">
                          {activePolicy.column_masks.map((cm, idx) => (
                            <div key={idx} className="flex gap-2 items-center p-3 bg-gray-900 border border-gray-850 rounded-lg">
                              <select
                                value={cm.table}
                                onChange={e => handleUpdateColumnMaskTable(idx, e.target.value)}
                                className="bg-gray-950 border border-gray-800 rounded px-2 py-1 text-sm text-white"
                              >
                                <option value="">-- {t('admin.roles.form.table')} --</option>
                                {activePolicy.allowed_tables.map(t => (
                                  <option key={t.table} value={t.table}>{t.table}</option>
                                ))}
                              </select>

                              {cm.table && (
                                <select
                                  value={cm.columns[0] || ''}
                                  data-testid={`mask-column-select-${cm.table}`}
                                  onChange={e => handleToggleColumnMask(idx, e.target.value)}
                                  className="flex-1 bg-gray-950 border border-gray-800 rounded px-2 py-1 text-sm text-white"
                                >
                                  <option value="">-- {t('admin.roles.form.columns')} --</option>
                                  {(activePolicy.allowed_tables.find(t => t.table === cm.table)?.columns || []).map(col => (
                                    <option key={col} value={col}>{col}</option>
                                  ))}
                                </select>
                              )}

                              <button
                                type="button"
                                onClick={() => handleRemoveColumnMask(idx)}
                                className="text-gray-500 hover:text-red-400 p-1 rounded transition-colors"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-850">
          <button
            type="button"
            onClick={handleCancelActive}
            className="px-4 py-2 border border-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={handleSaveActive}
            className="px-4 py-2 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors"
          >
            {t('common.save')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="policy-editor">
      <div className="flex justify-between items-center border-b border-gray-850 pb-2">
        <div>
          <h3 className="text-md font-semibold text-white">{t('admin.roles.form.policies')}</h3>
          <p className="text-xs text-gray-500">{t('admin.roles.form.policiesDesc')}</p>
        </div>
        <button
          type="button"
          onClick={handleAddClick}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 border border-gray-800 text-neon-cyan hover:bg-gray-850 rounded-lg text-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          {t('admin.roles.form.addPolicy')}
        </button>
      </div>

      {policies.length === 0 ? (
        <div className="text-center py-6 text-sm text-gray-500 italic bg-gray-950 border border-gray-900 rounded-xl">
          {t('admin.roles.form.noPolicies')}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {policies.map((policy, idx) => (
            <div
              key={policy.connection_id}
              className="bg-gray-900 border border-gray-850 rounded-xl p-4 flex justify-between items-start hover:border-gray-800 transition-colors"
            >
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-neon-cyan" />
                  <span className="font-semibold text-white">{getConnectionName(policy.connection_id)}</span>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                  <span>
                    <strong>{t('admin.roles.form.tablesLabel')}</strong> {policy.allowed_tables.length}
                  </span>
                  {policy.row_filters.length > 0 && (
                    <span>
                      <strong>{t('admin.roles.form.rowFiltersLabel')}</strong> {policy.row_filters.length}
                    </span>
                  )}
                  {policy.column_masks.length > 0 && (
                    <span>
                      <strong>{t('admin.roles.form.columnMasksLabel')}</strong> {policy.column_masks.length}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleEditClick(idx)}
                  className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-white transition-colors"
                  title={t('common.edit')}
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteClick(idx)}
                  className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-red-500 transition-colors"
                  title={t('common.delete')}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
