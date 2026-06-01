import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AdminSsoPage } from './AdminSsoPage.tsx';
import { useAdminSso } from '../hooks/useAdminSso.ts';

vi.mock('../hooks/useAdminSso', () => ({
  useAdminSso: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));

const mockMutations = {
  createMutation: { mutate: vi.fn(), isPending: false },
  updateMutation: { mutate: vi.fn(), isPending: false },
  deleteMutation: { mutate: vi.fn(), isPending: false },
};

const mockEmptyProviders = {
  listQuery: {
    data: { providers: [] },
    isLoading: false,
    isError: false,
  },
  ...mockMutations,
};

const mockOidcProvider = {
  id: 'oidc-123',
  protocol: 'oidc',
  display_name: 'Corporate SSO',
  issuer_url: 'https://idp.example.com',
  client_id: 'app-client-id',
  client_secret_masked: '●●●●●●●●',
  scopes: 'openid email profile groups',
  redirect_uri: 'https://app.example.com/api/v1/auth/sso/oidc/callback',
  group_claim_name: 'groups',
  is_active: true,
};

const mockSamlProvider = {
  id: 'saml-456',
  protocol: 'saml',
  display_name: 'SAML Provider',
  saml_entity_id: 'saml-entity',
  saml_metadata_url: 'https://idp.example.com/metadata',
  saml_metadata_xml_masked: '●●●●●●●●',
  saml_certificate_masked: '●●●●●●●●',
  group_claim_name: 'roles',
  is_active: true,
};

const mockPopulatedProviders = {
  listQuery: {
    data: {
      providers: [mockOidcProvider, mockSamlProvider],
    },
    isLoading: false,
    isError: false,
  },
  ...mockMutations,
};

describe('AdminSsoPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders title and empty state when no providers exist', () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    expect(screen.getByText('admin.sso.title')).toBeInTheDocument();
    expect(screen.getByText('admin.sso.emptyState')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    vi.mocked(useAdminSso).mockReturnValue({
      listQuery: { isLoading: true, data: undefined, isError: false },
      ...mockMutations,
    } as unknown as ReturnType<typeof useAdminSso>);

    render(<AdminSsoPage />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('renders error state', () => {
    vi.mocked(useAdminSso).mockReturnValue({
      listQuery: { isLoading: false, data: undefined, isError: true },
      ...mockMutations,
    } as unknown as ReturnType<typeof useAdminSso>);

    render(<AdminSsoPage />);
    expect(screen.getByText('admin.sso.loadError')).toBeInTheDocument();
  });

  it('renders configured providers and masks secrets', () => {
    vi.mocked(useAdminSso).mockReturnValue(mockPopulatedProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    // Check OIDC Provider details
    expect(screen.getByText('Corporate SSO')).toBeInTheDocument();
    expect(screen.getByText('https://idp.example.com')).toBeInTheDocument();
    expect(screen.getByText('app-client-id')).toBeInTheDocument();
    expect(screen.getAllByText('●●●●●●●●')).toHaveLength(3); // 1 for client secret, 2 for SAML metadata/cert

    // Check SAML Provider details
    expect(screen.getByText('SAML Provider')).toBeInTheDocument();
    expect(screen.getByText('saml-entity')).toBeInTheDocument();
    expect(screen.getByText('https://idp.example.com/metadata')).toBeInTheDocument();
  });

  it('shows OIDC creation form when adding an OIDC provider', () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    const addOidcButton = screen.getByRole('button', { name: 'admin.sso.addOidc' });
    fireEvent.click(addOidcButton);

    expect(screen.getByText('admin.sso.form.addOidcTitle')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.displayName')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.issuerUrl')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.clientId')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.clientSecret')).toBeInTheDocument();
  });

  it('shows SAML creation form when adding a SAML provider', () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    const addSamlButton = screen.getByRole('button', { name: 'admin.sso.addSaml' });
    fireEvent.click(addSamlButton);

    expect(screen.getByText('admin.sso.form.addSamlTitle')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.displayName')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.samlEntityId')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.samlMetadataUrl')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.sso.form.samlCertificate')).toBeInTheDocument();
  });

  it('performs OIDC creation and calls mutate with form data', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.sso.addOidc' }));

    fireEvent.change(screen.getByLabelText('admin.sso.form.displayName'), { target: { value: 'My OIDC' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.issuerUrl'), { target: { value: 'https://issuer.com' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.clientId'), { target: { value: 'client-1' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.clientSecret'), { target: { value: 'secret-1' } });

    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(mockMutations.createMutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
        protocol: 'oidc',
        display_name: 'My OIDC',
        issuer_url: 'https://issuer.com',
        client_id: 'client-1',
        client_secret: 'secret-1',
      }));
    });
  });

  it('shows validation errors for missing required OIDC fields', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.sso.addOidc' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(screen.getByText('error.validation.oidcRequiredFields')).toBeInTheDocument();
    });
    expect(mockMutations.createMutation.mutate).not.toHaveBeenCalled();
  });

  it('shows validation errors for missing required SAML fields', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.sso.addSaml' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(screen.getByText('error.validation.samlRequiredFields')).toBeInTheDocument();
    });
    expect(mockMutations.createMutation.mutate).not.toHaveBeenCalled();
  });

  it('allows updating a provider and calls update mutation', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockPopulatedProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    const editButtons = screen.getAllByRole('button', { name: 'common.edit' });
    fireEvent.click(editButtons[0]); // Edit OIDC

    expect(screen.getByText('admin.sso.form.editOidcTitle')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Corporate SSO')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('admin.sso.form.displayName'), { target: { value: 'Updated OIDC Name' } });
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(mockMutations.updateMutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
        id: 'oidc-123',
        data: expect.objectContaining({
          display_name: 'Updated OIDC Name',
        }),
      }));
    });
  });

  it('allows deleting a provider and calls delete mutation', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockPopulatedProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    const deleteButtons = screen.getAllByRole('button', { name: 'common.delete' });
    fireEvent.click(deleteButtons[0]); // Delete OIDC

    await waitFor(() => {
      expect(mockMutations.deleteMutation.mutate).toHaveBeenCalledWith('oidc-123');
    });
  });

  it('SAML create without certificate shows validation error and does not mutate', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.sso.addSaml' }));

    fireEvent.change(screen.getByLabelText('admin.sso.form.displayName'), { target: { value: 'My SAML' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.samlEntityId'), { target: { value: 'saml-entity-id' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.samlMetadataUrl'), { target: { value: 'https://metadata.com' } });
    // Left Certificate blank!

    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(screen.getByText('error.validation.samlRequiredFields')).toBeInTheDocument();
    });
    expect(mockMutations.createMutation.mutate).not.toHaveBeenCalled();
  });

  it('SAML create with certificate calls create mutation with saml_certificate', async () => {
    vi.mocked(useAdminSso).mockReturnValue(mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>);
    render(<AdminSsoPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.sso.addSaml' }));

    fireEvent.change(screen.getByLabelText('admin.sso.form.displayName'), { target: { value: 'My SAML' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.samlEntityId'), { target: { value: 'saml-entity-id' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.samlMetadataUrl'), { target: { value: 'https://metadata.com' } });
    fireEvent.change(screen.getByLabelText('admin.sso.form.samlCertificate'), { target: { value: 'BEGIN CERTIFICATE...' } });

    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(mockMutations.createMutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
        protocol: 'saml',
        display_name: 'My SAML',
        saml_entity_id: 'saml-entity-id',
        saml_metadata_url: 'https://metadata.com',
        saml_certificate: 'BEGIN CERTIFICATE...',
      }));
    });
  });

  it('sanitizes hostile create error containing raw secret and renders localized fallback instead', async () => {
    let capturedOnCreateError: ((err: unknown) => void) | undefined;

    vi.mocked(useAdminSso).mockImplementation((opts: unknown) => {
      const options = opts as { onCreateError?: (err: unknown) => void };
      capturedOnCreateError = options.onCreateError;
      return mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>;
    });

    render(<AdminSsoPage />);
    expect(capturedOnCreateError).toBeDefined();

    // Trigger error callback with hostile raw message containing sensitive leaked info
    const hostileError = {
      message: 'Database query failed: User table not found on internal-db-host-99.internal.corp (traceback uuid-1234-abcd-5678-secret-xyz)',
      body: {
        detail: 'Stack trace: at line 45 cert = secret-key-data'
      }
    };

    act(() => {
      capturedOnCreateError!(hostileError);
    });

    // Verify toast shows localized fallback key and DOES NOT leak internal host/uuid/trace/secret info
    expect(screen.getByText('admin.sso.addError')).toBeInTheDocument();
    expect(screen.queryByText(/internal-db-host-99/)).toBeNull();
    expect(screen.queryByText(/uuid-1234/i)).toBeNull();
    expect(screen.queryByText(/secret-key-data/i)).toBeNull();
  });

  it('renders translated text for allowed backend error keys in update/delete', async () => {
    let capturedOnUpdateError: ((err: unknown) => void) | undefined;
    let capturedOnDeleteError: ((err: unknown) => void) | undefined;

    vi.mocked(useAdminSso).mockImplementation((opts: unknown) => {
      const options = opts as {
        onUpdateError?: (err: unknown) => void;
        onDeleteError?: (err: unknown) => void;
      };
      capturedOnUpdateError = options.onUpdateError;
      capturedOnDeleteError = options.onDeleteError;
      return mockEmptyProviders as unknown as ReturnType<typeof useAdminSso>;
    });

    render(<AdminSsoPage />);

    // 1. Allowed backend error key on update (e.g. duplicateProtocol)
    act(() => {
      capturedOnUpdateError!({
        body: {
          message_key: 'error.conflict.duplicateProtocol'
        }
      });
    });
    expect(screen.getByText('error.conflict.duplicateProtocol')).toBeInTheDocument();

    // 2. Hostile delete error is sanitized and falls back to delete error label
    act(() => {
      capturedOnDeleteError!({
        detail: {
          error: 'Hostile database stack trace: uuid-123-unauthorized-internal'
        }
      });
    });
    expect(screen.getByText('admin.sso.deleteError')).toBeInTheDocument();
    expect(screen.queryByText(/Hostile database/i)).toBeNull();
  });
});
