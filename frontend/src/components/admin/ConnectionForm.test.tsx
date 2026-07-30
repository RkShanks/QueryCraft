import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConnectionForm } from './ConnectionForm';
import type { ConnectionResponse } from '../../api/generated/types.gen';

type LegacyConnectionResponse = ConnectionResponse & {
  host: string;
  username: string;
};

describe('ConnectionForm', () => {
  const defaultProps = {
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
  };

  it.each([
    ['create', undefined],
    [
      'edit',
      {
        id: 'direction-check',
        display_name: 'قاعدة التحليلات',
        database_type: 'postgresql',
        port: 5432,
        database_name: 'analytics_db',
        ssl_mode: 'require',
        lifecycle_state: 'active',
        health_status: 'healthy',
        last_health_check_at: null,
        health_error_category: null,
        schema_introspection_status: 'success',
        schema_last_refreshed_at: null,
        created_at: '',
        updated_at: '',
      } satisfies ConnectionResponse,
    ],
  ])('keeps %s technical values LTR without overriding the RTL display name', (_mode, initialValues) => {
    render(
      <div dir="rtl">
        <ConnectionForm {...defaultProps} initialValues={initialValues} />
      </div>
    );

    [
      /Database Type/i,
      /Host/i,
      /Port/i,
      /Database Name/i,
      /Username/i,
      /Password/i,
      /SSL Mode/i,
    ].forEach((label) => {
      expect(screen.getByLabelText(label)).toHaveAttribute('dir', 'ltr');
    });
    expect(screen.getByLabelText(/Display Name/i)).not.toHaveAttribute('dir');
  });

  it('renders create-mode fields', () => {
    render(<ConnectionForm {...defaultProps} />);

    expect(screen.getByLabelText(/Display Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Database Type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Host/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Port/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Database Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/SSL Mode/i)).toBeInTheDocument();

    expect(screen.getByRole('button', { name: /Create Connection/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
  });

  it('database type switch auto-fills the expected port', () => {
    render(<ConnectionForm {...defaultProps} />);

    const typeSelect = screen.getByLabelText(/Database Type/i);
    const portInput = screen.getByLabelText(/Port/i) as HTMLInputElement;

    expect((typeSelect as HTMLSelectElement).value).toBe('postgresql');
    expect(portInput.value).toBe('5432');

    // Switch to mysql
    fireEvent.change(typeSelect, { target: { value: 'mysql' } });
    expect(portInput.value).toBe('3306');

    // Switch to mssql
    fireEvent.change(typeSelect, { target: { value: 'mssql' } });
    expect(portInput.value).toBe('1433');
  });

  it('edit mode renders non-sensitive values but never redisplays legacy write-only fields', () => {
    const legacyHost = crypto.randomUUID();
    const legacyUsername = crypto.randomUUID();
    const initialValues: LegacyConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: legacyHost,
      port: 9999,
      database_name: 'custom_db',
      username: legacyUsername,
      ssl_mode: 'require',
      lifecycle_state: 'active',
      health_status: 'healthy',
      last_health_check_at: null,
      health_error_category: null,
      schema_introspection_status: 'success',
      schema_last_refreshed_at: null,
      created_at: '',
      updated_at: '',
    };

    render(<ConnectionForm {...defaultProps} initialValues={initialValues} />);

    expect((screen.getByLabelText(/Display Name/i) as HTMLInputElement).value).toBe('My Custom PG');
    expect((screen.getByLabelText(/Database Type/i) as HTMLSelectElement).value).toBe('postgresql');
    expect((screen.getByLabelText(/Port/i) as HTMLInputElement).value).toBe('9999');
    expect((screen.getByLabelText(/Database Name/i) as HTMLInputElement).value).toBe('custom_db');
    expect((screen.getByLabelText(/SSL Mode/i) as HTMLInputElement).value).toBe('require');

    const hostInput = screen.getByLabelText(/Host/i) as HTMLInputElement;
    const usernameInput = screen.getByLabelText(/Username/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement;

    expect(hostInput.value.length).toBe(0);
    expect(usernameInput.value.length).toBe(0);
    expect(passwordInput.value).toBe('');
    expect(hostInput.value === legacyHost).toBe(false);
    expect(usernameInput.value === legacyUsername).toBe(false);
    expect(hostInput.placeholder).toBe('Leave blank to preserve existing value');
    expect(usernameInput.placeholder).toBe('Leave blank to preserve existing value');
    expect(passwordInput.placeholder).toBe('Leave blank to preserve existing value');
    expect(screen.getAllByText('Leave blank to preserve existing value')).toHaveLength(3);
    expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument();
  });

  it('unchanged edit submission omits every blank write-only field', () => {
    const initialValues: LegacyConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: crypto.randomUUID(),
      port: 9999,
      database_name: 'custom_db',
      username: crypto.randomUUID(),
      ssl_mode: 'require',
      lifecycle_state: 'active',
      health_status: 'healthy',
      last_health_check_at: null,
      health_error_category: null,
      schema_introspection_status: 'success',
      schema_last_refreshed_at: null,
      created_at: '',
      updated_at: '',
    };

    const onSubmit = vi.fn();
    render(<ConnectionForm {...defaultProps} initialValues={initialValues} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(submitButton);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedPayload = onSubmit.mock.calls[0][0];
    expect(Object.hasOwn(submittedPayload, 'host')).toBe(false);
    expect(Object.hasOwn(submittedPayload, 'username')).toBe(false);
    expect(Object.hasOwn(submittedPayload, 'password')).toBe(false);
    expect(submittedPayload.display_name).toBe('My Custom PG');
  });

  it('edit submission includes only replacements typed into write-only fields', () => {
    const initialValues: LegacyConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: crypto.randomUUID(),
      port: 9999,
      database_name: 'custom_db',
      username: crypto.randomUUID(),
      ssl_mode: 'require',
      lifecycle_state: 'active',
      health_status: 'healthy',
      last_health_check_at: null,
      health_error_category: null,
      schema_introspection_status: 'success',
      schema_last_refreshed_at: null,
      created_at: '',
      updated_at: '',
    };

    const onSubmit = vi.fn();
    render(<ConnectionForm {...defaultProps} initialValues={initialValues} onSubmit={onSubmit} />);

    const replacements = Array.from({ length: 3 }, () => crypto.randomUUID());
    fireEvent.change(screen.getByLabelText(/Host/i), { target: { value: replacements[0] } });
    fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: replacements[1] } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: replacements[2] } });

    const submitButton = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(submitButton);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedPayload = onSubmit.mock.calls[0][0];
    expect(submittedPayload.host === replacements[0]).toBe(true);
    expect(submittedPayload.username === replacements[1]).toBe(true);
    expect(submittedPayload.password === replacements[2]).toBe(true);
  });

  it('basic validation prevents submit when required fields are empty', () => {
    const onSubmit = vi.fn();
    render(<ConnectionForm {...defaultProps} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /Create Connection/i });
    fireEvent.click(submitButton);

    // Should not trigger submit since required fields are empty (display_name, host, database_name, username, password on create)
    expect(onSubmit).not.toHaveBeenCalled();

    expect(screen.queryAllByText(/This field is required/i).length).toBeGreaterThan(0);
  });

  it('clears typed write-only replacements when the mode or edit target changes', () => {
    const runtimeProbes = Array.from({ length: 10 }, () => crypto.randomUUID());
    const connectionValues = (
      id: string,
      legacyHost: string,
      legacyUsername: string
    ): LegacyConnectionResponse => ({
      id,
      display_name: 'Existing Db',
      database_type: 'postgresql',
      host: legacyHost,
      port: 5432,
      database_name: 'test_db',
      username: legacyUsername,
      ssl_mode: 'prefer',
      lifecycle_state: 'active',
      health_status: 'healthy',
      last_health_check_at: null,
      health_error_category: null,
      schema_introspection_status: 'success',
      schema_last_refreshed_at: null,
      created_at: '',
      updated_at: '',
    });
    const { rerender } = render(<ConnectionForm {...defaultProps} />);
    const writeOnlyInputs = [
      screen.getByLabelText(/Host/i),
      screen.getByLabelText(/Username/i),
      screen.getByLabelText(/Password/i),
    ] as HTMLInputElement[];

    writeOnlyInputs.forEach((input, index) => {
      fireEvent.change(input, { target: { value: runtimeProbes[index] } });
    });
    rerender(
      <ConnectionForm
        {...defaultProps}
        initialValues={connectionValues('first', runtimeProbes[3], runtimeProbes[4])}
      />
    );
    expect(writeOnlyInputs.every((input) => input.value.length === 0)).toBe(true);

    writeOnlyInputs.forEach((input, index) => {
      fireEvent.change(input, { target: { value: runtimeProbes[index + 5] } });
    });
    rerender(
      <ConnectionForm
        {...defaultProps}
        initialValues={connectionValues('second', runtimeProbes[8], runtimeProbes[9])}
      />
    );
    expect(writeOnlyInputs.every((input) => input.value.length === 0)).toBe(true);
  });
});
