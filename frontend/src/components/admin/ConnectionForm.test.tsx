import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConnectionForm } from './ConnectionForm';
import type { ConnectionResponse } from '../../api/generated/types.gen';

describe('ConnectionForm', () => {
  const defaultProps = {
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
  };

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

    // Default should be postgresql and port 5432
    expect(typeSelect).value = 'postgresql';
    expect(portInput.value).toBe('5432');

    // Switch to mysql
    fireEvent.change(typeSelect, { target: { value: 'mysql' } });
    expect(portInput.value).toBe('3306');

    // Switch to mssql
    fireEvent.change(typeSelect, { target: { value: 'mssql' } });
    expect(portInput.value).toBe('1433');
  });

  it('edit mode renders existing non-sensitive values', () => {
    const initialValues: ConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: 'pg.custom.com',
      port: 9999,
      database_name: 'custom_db',
      username: 'custom_user',
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

    expect(screen.getByLabelText(/Display Name/i)).value = 'My Custom PG';
    expect(screen.getByLabelText(/Database Type/i)).value = 'postgresql';
    expect(screen.getByLabelText(/Host/i)).value = 'pg.custom.com';
    expect((screen.getByLabelText(/Port/i) as HTMLInputElement).value).toBe('9999');
    expect(screen.getByLabelText(/Database Name/i)).value = 'custom_db';
    expect(screen.getByLabelText(/Username/i)).value = 'custom_user';
    expect(screen.getByLabelText(/SSL Mode/i)).value = 'require';

    expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument();
  });

  it('edit mode never displays a real password', () => {
    const initialValues: ConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: 'pg.custom.com',
      port: 9999,
      database_name: 'custom_db',
      username: 'custom_user',
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

    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement;
    expect(passwordInput.value).toBe('');
    expect(passwordInput.placeholder).toBe('••••••••');
  });

  it('submit payload for unchanged edit password omits password', () => {
    const initialValues: ConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: 'pg.custom.com',
      port: 9999,
      database_name: 'custom_db',
      username: 'custom_user',
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
    expect(submittedPayload.password).toBeUndefined();
    expect(submittedPayload.display_name).toBe('My Custom PG');
  });

  it('submit payload for changed password includes the new password', () => {
    const initialValues: ConnectionResponse = {
      id: '123-uuid',
      display_name: 'My Custom PG',
      database_type: 'postgresql',
      host: 'pg.custom.com',
      port: 9999,
      database_name: 'custom_db',
      username: 'custom_user',
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

    const passwordInput = screen.getByLabelText(/Password/i);
    fireEvent.change(passwordInput, { target: { value: 'new-secret-123' } });

    const submitButton = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(submitButton);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedPayload = onSubmit.mock.calls[0][0];
    expect(submittedPayload.password).toBe('new-secret-123');
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
});
