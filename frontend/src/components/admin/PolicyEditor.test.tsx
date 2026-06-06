import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PolicyEditor } from './PolicyEditor';
import { useConnections } from '../../hooks/useConnections';
import { useConnectionSchema } from '../../hooks/useConnectionSchema';

// Mock the hooks
vi.mock('../../hooks/useConnections', () => ({
  useConnections: vi.fn(),
}));

vi.mock('../../hooks/useConnectionSchema', () => ({
  useConnectionSchema: vi.fn(),
}));

describe('PolicyEditor', () => {
  const mockOnChange = vi.fn();

  const mockConnections = [
    {
      id: 'conn-1',
      display_name: 'Main Database',
      database_type: 'postgresql',
      lifecycle_state: 'active',
      health_status: 'healthy',
      schema_introspection_status: 'success',
    },
  ];

  const mockSchema = {
    connection_id: 'conn-1',
    tables: [
      {
        table_name: 'users',
        column_count: 3,
        columns: [
          { column_name: 'id', data_type: 'integer', is_primary_key: true, foreign_key: null },
          { column_name: 'name', data_type: 'varchar', is_primary_key: false, foreign_key: null },
          { column_name: 'email', data_type: 'varchar', is_primary_key: false, foreign_key: null },
        ],
      },
    ],
    introspected_at: '2026-06-06T00:00:00Z',
  };

  const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

  beforeEach(() => {
    vi.clearAllMocks();
    alertSpy.mockClear();

    vi.mocked(useConnections).mockReturnValue({
      listQuery: {
        data: mockConnections,
        isLoading: false,
        isError: false,
      },
    } as unknown as ReturnType<typeof useConnections>);

    vi.mocked(useConnectionSchema).mockReturnValue({
      data: mockSchema,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useConnectionSchema>);
  });

  it('renders title and empty state when policies are empty', () => {
    render(<PolicyEditor policies={[]} onChange={mockOnChange} />);
    expect(screen.getByText('Connection Policies')).toBeInTheDocument();
    expect(screen.getByText('No connection policies configured.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add Connection Policy/i })).toBeInTheDocument();
  });

  it('can open add policy dialog and select connection', () => {
    render(<PolicyEditor policies={[]} onChange={mockOnChange} />);

    const addButton = screen.getByRole('button', { name: /Add Connection Policy/i });
    fireEvent.click(addButton);

    const select = screen.getByLabelText(/Select Connection/i) as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(select.value).toBe('');

    fireEvent.change(select, { target: { value: 'conn-1' } });
    expect(select.value).toBe('conn-1');
  });

  it('displays loading schema state', () => {
    vi.mocked(useConnectionSchema).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useConnectionSchema>);

    render(<PolicyEditor policies={[]} onChange={mockOnChange} />);

    const addButton = screen.getByRole('button', { name: /Add Connection Policy/i });
    fireEvent.click(addButton);

    const select = screen.getByLabelText(/Select Connection/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'conn-1' } });

    expect(screen.getByText('Loading database schema...')).toBeInTheDocument();
  });

  it('can configure allowed tables and columns, and submits onChange', () => {
    render(<PolicyEditor policies={[]} onChange={mockOnChange} />);

    const addButton = screen.getByRole('button', { name: /Add Connection Policy/i });
    fireEvent.click(addButton);

    const select = screen.getByLabelText(/Select Connection/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'conn-1' } });

    const tableCheckbox = screen.getByTestId('table-checkbox-users') as HTMLInputElement;
    expect(tableCheckbox).toBeInTheDocument();
    expect(tableCheckbox.checked).toBe(false);

    fireEvent.click(tableCheckbox);
    expect(tableCheckbox.checked).toBe(true);

    const idCol = screen.getByTestId('column-checkbox-users-id') as HTMLInputElement;
    const nameCol = screen.getByTestId('column-checkbox-users-name') as HTMLInputElement;
    const emailCol = screen.getByTestId('column-checkbox-users-email') as HTMLInputElement;

    expect(idCol.checked).toBe(true);
    expect(nameCol.checked).toBe(true);
    expect(emailCol.checked).toBe(true);

    fireEvent.click(nameCol);
    expect(nameCol.checked).toBe(false);

    const saveButton = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveButton);

    expect(mockOnChange).toHaveBeenCalledWith([
      {
        connection_id: 'conn-1',
        allowed_tables: [
          {
            table: 'users',
            columns: ['id', 'email'],
          },
        ],
        row_filters: [],
        column_masks: [],
      },
    ]);
  });

  it('validates filter expressions and displays validation feedback', () => {
    render(<PolicyEditor policies={[]} onChange={mockOnChange} />);

    const addButton = screen.getByRole('button', { name: /Add Connection Policy/i });
    fireEvent.click(addButton);

    const select = screen.getByLabelText(/Select Connection/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'conn-1' } });

    const tableCheckbox = screen.getByTestId('table-checkbox-users');
    fireEvent.click(tableCheckbox);

    const addFilterButton = screen.getByRole('button', { name: /Add Row Filter/i });
    fireEvent.click(addFilterButton);

    const tableSelects = screen.getAllByRole('combobox');
    const filterTableSelect = tableSelects[1] as HTMLSelectElement;
    const filterInput = screen.getByPlaceholderText(/e.g. department_id = {user.role}/i) as HTMLInputElement;

    expect(filterTableSelect.value).toBe('');
    fireEvent.change(filterTableSelect, { target: { value: 'users' } });
    expect(filterTableSelect.value).toBe('users');

    fireEvent.change(filterInput, { target: { value: 'SELECT * FROM users' } });
    expect(screen.getByText('Invalid filter expression. Subqueries, JOINs, UNIONs, comments, and functions are not allowed.')).toBeInTheDocument();

    fireEvent.change(filterInput, { target: { value: 'email = {user.invalid_prop}' } });
    expect(screen.getByText('Only {user.email}, {user.subject_id}, and {user.role} placeholders are allowed.')).toBeInTheDocument();

    const nameCol = screen.getByTestId('column-checkbox-users-name');
    fireEvent.click(nameCol);
    fireEvent.change(filterInput, { target: { value: "name = 'test'" } });
    expect(screen.getByText("Column 'name' not found in table 'users'.")).toBeInTheDocument();

    fireEvent.change(filterInput, { target: { value: 'id = 1' } });
    expect(screen.queryByText("Column 'name' not found in table 'users'.")).not.toBeInTheDocument();

    fireEvent.change(filterInput, { target: { value: ' ' } });
    expect(screen.getByText('Filter expression cannot be empty.')).toBeInTheDocument();

    const saveButton = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveButton);
    expect(alertSpy).toHaveBeenCalledWith('Please fix validation errors before saving.');
  });

  it('can configure column masks', () => {
    render(<PolicyEditor policies={[]} onChange={mockOnChange} />);

    const addButton = screen.getByRole('button', { name: /Add Connection Policy/i });
    fireEvent.click(addButton);

    const select = screen.getByLabelText(/Select Connection/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'conn-1' } });

    const tableCheckbox = screen.getByTestId('table-checkbox-users');
    fireEvent.click(tableCheckbox);

    const addMaskButton = screen.getByRole('button', { name: /Add Column Mask/i });
    fireEvent.click(addMaskButton);

    const tableSelects = screen.getAllByRole('combobox');
    const maskTableSelect = tableSelects[1] as HTMLSelectElement;
    expect(maskTableSelect).toBeInTheDocument();

    fireEvent.change(maskTableSelect, { target: { value: 'users' } });

    const maskColumnSelect = screen.getByTestId('mask-column-select-users') as HTMLSelectElement;
    expect(maskColumnSelect).toBeInTheDocument();
    expect(maskColumnSelect.value).toBe('');

    fireEvent.change(maskColumnSelect, { target: { value: 'email' } });
    expect(maskColumnSelect.value).toBe('email');

    const saveButton = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveButton);

    expect(mockOnChange).toHaveBeenCalledWith([
      {
        connection_id: 'conn-1',
        allowed_tables: [
          {
            table: 'users',
            columns: ['id', 'name', 'email'],
          },
        ],
        row_filters: [],
        column_masks: [
          {
            table: 'users',
            columns: ['email'],
          },
        ],
      },
    ]);
  });
});
