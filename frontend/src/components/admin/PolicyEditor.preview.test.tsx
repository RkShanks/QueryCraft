import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useConnectionSchema } from '../../hooks/useConnectionSchema';
import { useConnections } from '../../hooks/useConnections';
import { useDraftRolePolicyPreview } from '../../hooks/useAdminRoles';
import { PolicyEditor } from './PolicyEditor';

vi.mock('../../hooks/useConnections', () => ({ useConnections: vi.fn() }));
vi.mock('../../hooks/useConnectionSchema', () => ({ useConnectionSchema: vi.fn() }));
vi.mock('../../hooks/useAdminRoles', () => ({ useDraftRolePolicyPreview: vi.fn() }));

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const CORPUS = JSON.parse(
  readFileSync(resolve(REPOSITORY_ROOT, 'contracts/row-filter-validation-corpus.json'), 'utf8')
) as {
  cases: Array<{
    id: string;
    category: string;
    dialect: string;
    table: string;
    filter: string;
    valid: boolean;
  }>;
};
const VALID_FILTERS = CORPUS.cases.filter((entry) => entry.valid);
const INVALID_UI_FILTERS = CORPUS.cases.filter((entry) => !entry.valid && entry.table === 'users');

const CONNECTIONS = [{ id: 'conn-1', display_name: 'Main Database', database_type: 'postgresql' }];
const SCHEMA = {
  connection_id: 'conn-1',
  tables: [{
    table_name: 'users',
    column_count: 5,
    columns: ['id', 'name', 'email', 'status', 'subject_id'].map((column_name) => ({
      column_name,
      data_type: 'text',
      is_primary_key: column_name === 'id',
      foreign_key: null,
    })),
  }],
  introspected_at: '2026-08-13T00:00:00Z',
};
const ALLOWED_PREVIEW = {
  accessible_tables: ['users'],
  accessible_columns: { users: ['id', 'name', 'email'] },
  blocked_tables: ['audit_log'],
  applicable_row_filters: [{ table: 'users', filter: "name = 'draft'" }],
  masked_columns: { users: ['email'] },
  would_be_allowed: true,
  message_key: null,
};

describe('PolicyEditor draft preview', () => {
  const onChange = vi.fn();
  const previewMutate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    previewMutate.mockReset();
    vi.mocked(useConnections).mockReturnValue({
      listQuery: { data: CONNECTIONS, isLoading: false, isError: false },
    } as unknown as ReturnType<typeof useConnections>);
    vi.mocked(useConnectionSchema).mockReturnValue({
      data: SCHEMA,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useConnectionSchema>);
    vi.mocked(useDraftRolePolicyPreview).mockReturnValue({
      mutate: previewMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useDraftRolePolicyPreview>);
  });

  function openDraft(filter = "name = 'draft'") {
    render(<PolicyEditor policies={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Connection Policy' }));
    fireEvent.change(screen.getByLabelText('Select Connection'), { target: { value: 'conn-1' } });
    fireEvent.click(screen.getByTestId('table-checkbox-users'));
    fireEvent.click(screen.getByRole('button', { name: 'Add Row Filter' }));
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'users' } });
    const filterInput = screen.getByPlaceholderText(/department_id = {user.role}/i);
    fireEvent.change(filterInput, { target: { value: filter } });
    return filterInput;
  }

  function submitPreview(question = 'Show draft users') {
    fireEvent.change(screen.getByLabelText('Sample question'), { target: { value: question } });
    fireEvent.click(screen.getByRole('button', { name: 'Test draft policy' }));
  }

  it('tests unsaved new-role values without a role id or policy mutation', async () => {
    previewMutate.mockImplementation((_request, callbacks) => callbacks?.onSuccess?.(ALLOWED_PREVIEW));
    openDraft();
    fireEvent.change(screen.getByLabelText('Optional sample SQL'), {
      target: { value: 'SELECT id, name FROM users' },
    });
    submitPreview();

    expect(previewMutate).toHaveBeenCalledWith(
      {
        question: 'Show draft users',
        sample_sql: 'SELECT id, name FROM users',
        connection_policy: {
          connection_id: 'conn-1',
          allowed_tables: [{ table: 'users', columns: ['id', 'name', 'email', 'status', 'subject_id'] }],
          row_filters: [{ table: 'users', filter: "name = 'draft'" }],
          column_masks: [],
        },
      },
      expect.any(Object)
    );
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText('Draft policy allows the sample.')).toBeInTheDocument();
    expect(screen.getByText('No AI model or source query is run.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('policy-preview-status')).toHaveFocus());
  });

  it.each([
    ['allowed', { response: ALLOWED_PREVIEW }, 'Draft policy allows the sample.'],
    ['blocked', { response: { ...ALLOWED_PREVIEW, would_be_allowed: false, message_key: 'error.queryBlockedPolicy' } }, 'Draft policy blocks the sample.'],
    ['invalid', { error: { status: 422, body: { message_key: 'error.filterValidationFailed' } } }, 'The draft policy is invalid.'],
    ['retry', { error: { status: 500, body: { message_key: 'error.internal', detail: 'private detail' } } }, 'Policy preview is temporarily unavailable.'],
    ['permission-denied', { error: { message_key: 'error.forbidden', detail: 'private detail' } }, 'You do not have permission to preview role policies.'],
  ])('renders the %s preview state with sanitized localized feedback', (state, outcome, message) => {
    previewMutate.mockImplementation((_request, callbacks) => {
      if ('response' in outcome) callbacks?.onSuccess?.(outcome.response);
      else callbacks?.onError?.(outcome.error);
    });
    openDraft();
    submitPreview();

    expect(screen.getByTestId('policy-preview-status')).toHaveAttribute('data-state', state);
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByText('private detail')).not.toBeInTheDocument();
  });

  it('shows accessible and blocked policy metadata without execution claims', () => {
    previewMutate.mockImplementation((_request, callbacks) => callbacks?.onSuccess?.(ALLOWED_PREVIEW));
    openDraft();
    submitPreview();

    const status = screen.getByTestId('policy-preview-status');
    expect(within(status).getByText('audit_log')).toHaveAttribute('dir', 'ltr');
    expect(within(status).getByText('users')).toHaveAttribute('dir', 'ltr');
    expect(within(status).getByText(/users: id, name, email/)).toHaveAttribute('dir', 'ltr');
    expect(within(status).getByText("name = 'draft'")).toHaveAttribute('dir', 'ltr');
    expect(within(status).getByText(/users: email/)).toHaveAttribute('dir', 'ltr');
  });

  it('marks a completed preview stale when a relevant draft input changes', () => {
    previewMutate.mockImplementation((_request, callbacks) => callbacks?.onSuccess?.(ALLOWED_PREVIEW));
    const filterInput = openDraft();
    submitPreview();
    expect(screen.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'allowed');

    fireEvent.change(filterInput, { target: { value: "name = 'changed'" } });

    expect(screen.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'stale');
    expect(screen.getByText('Draft changed. Test again for current results.')).toBeInTheDocument();
  });

  it('shows empty then loading states and deduplicates repeated preview clicks', () => {
    openDraft();
    expect(screen.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'empty');
    fireEvent.change(screen.getByLabelText('Sample question'), { target: { value: 'Show draft users' } });

    const previewButton = screen.getByRole('button', { name: 'Test draft policy' });
    fireEvent.click(previewButton);
    fireEvent.click(previewButton);

    expect(previewMutate).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'loading');
  });

  it('retries a dependency failure with the current draft', () => {
    previewMutate.mockImplementation((_request, callbacks) => callbacks?.onError?.({ status: 500 }));
    openDraft();
    submitPreview();
    fireEvent.click(screen.getByRole('button', { name: 'Retry policy preview' }));
    expect(previewMutate).toHaveBeenCalledTimes(2);
  });

  it.each(VALID_FILTERS)('does not reject backend-valid corpus filter $id locally', (entry) => {
    previewMutate.mockImplementation((_request, callbacks) => callbacks?.onSuccess?.(ALLOWED_PREVIEW));
    openDraft(entry.filter);
    submitPreview();

    expect(previewMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        connection_policy: expect.objectContaining({
          row_filters: [{ table: 'users', filter: entry.filter }],
        }),
      }),
      expect.any(Object)
    );
    expect(screen.queryByText(/Invalid filter expression/)).not.toBeInTheDocument();
  });

  it.each(INVALID_UI_FILTERS)(
    'sends backend-invalid corpus filter $id and renders only localized authoritative feedback',
    (entry) => {
      previewMutate.mockImplementation((_request, callbacks) => callbacks?.onError?.({
        status: 422,
        body: {
          message_key: 'error.filterValidationFailed',
          detail: 'sqlglot internal schema detail',
        },
      }));
      openDraft(entry.filter);
      submitPreview();

      expect(previewMutate).toHaveBeenCalled();
      expect(screen.getByText('The draft policy is invalid.')).toBeInTheDocument();
      expect(screen.queryByText(/sqlglot|internal schema detail/i)).not.toBeInTheDocument();
    }
  );
});
