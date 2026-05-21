import { describe, it, expect } from 'vitest';
import en from './en.json';
import ar from './ar.json';

describe('Wave 14 i18n key coverage', () => {
  const requiredKeys = [
    // DatabaseSelector
    'databaseSelector.selectDatabase',
    'databaseSelector.empty',
    // PromptInput
    'query.input.placeholderNoConnections',
    'query.input.placeholderNoSelection',
    'query.input.warningNoConnections',
    'query.input.warningNoSelection',
    // ConnectionErrorCard
    'error.noConnections.title',
    'error.noConnections.body',
    'error.noConnections.action',
    'error.disabled.title',
    'error.disabled.body',
    'error.disabled.action',
    'error.unhealthy.title',
    'error.unhealthy.body',
    'error.unhealthy.action',
    'error.noSchema.title',
    'error.noSchema.body',
    'error.noSchema.action',
    'error.queryExecutionFailed.title',
    'error.queryExecutionFailed.body',
    'error.queryExecutionFailed.action',
    // AssistantResponseCard database type labels
    'query.result.databaseType.postgresql',
    'query.result.databaseType.mysql',
    'query.result.databaseType.mssql',
    // History metadata
    'history.detail.databaseConnection',
    'history.column.connection',
    // Workspace empty state
    'workspace.emptyState',
    'workspace.placeholder',
    // Query status
    'query.status.processing',
    'query.evaluator.rejected',
    'query.refine.message',
    // Actions
    'query.actions.deleteResult',
    'common.send',
    'common.close',
    // Result headings
    'query.result.sqlHeading',
    'query.result.tableHeading',
    // Error fallback
    'error.unknown.title',
    'error.unknown.message',
  ];

  it.each(requiredKeys)('has %s in en.json', (key) => {
    expect(en).toHaveProperty(key);
    expect(en[key as keyof typeof en]).toBeTruthy();
  });

  it.each(requiredKeys)('has %s in ar.json', (key) => {
    expect(ar).toHaveProperty(key);
    expect(ar[key as keyof typeof ar]).toBeTruthy();
  });

  it('en.json and ar.json have identical key sets', () => {
    const enKeys = Object.keys(en).sort();
    const arKeys = Object.keys(ar).sort();
    expect(arKeys).toEqual(enKeys);
  });
});
