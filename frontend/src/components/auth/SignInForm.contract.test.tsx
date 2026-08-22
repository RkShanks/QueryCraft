import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { SignInForm } from './SignInForm';
import { createWrapper } from '../../test/utils';
import { server } from '../../test/server';

const SECRET = 'correct-horse-battery';

const fill = (username: string, password: string) => {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: username } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } });
};

describe('SignInForm form contract (IS-GAP-039)', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders authoritative blank initial values', () => {
    render(<SignInForm />, { wrapper: createWrapper() });

    const username = screen.getByLabelText(/username/i) as HTMLInputElement;
    const password = screen.getByLabelText(/password/i) as HTMLInputElement;
    expect(username.value).toBe('');
    expect(password.value).toBe('');
    expect(username).not.toHaveAttribute('aria-invalid');
    expect(password).not.toHaveAttribute('aria-invalid');
  });

  it('rejects null/empty boundaries client-side and focuses the first invalid field', async () => {
    const signInSpy = vi.fn();
    server.use(
      http.post('/api/v1/auth/sign-in', async ({ request }) => {
        signInSpy(await request.clone().json());
        return HttpResponse.json({ error: 'unauthorized' }, { status: 401 });
      })
    );

    render(<SignInForm />, { wrapper: createWrapper() });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Username cannot be empty.'
      );
    });
    expect(signInSpy).not.toHaveBeenCalled();

    const username = screen.getByLabelText(/username/i);
    expect(username).toHaveFocus();
    expect(username).toHaveAttribute('aria-invalid', 'true');
    expect(passwordDescribedBy(username)).toContain('cannot be empty');
  });

  it('associates aria-invalid fields with their localized messages via aria-describedby', async () => {
    render(<SignInForm />, { wrapper: createWrapper() });

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'admin' } });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Password cannot be empty.'
      );
    });
    const password = screen.getByLabelText(/password/i);
    expect(password).toHaveAttribute('aria-invalid', 'true');
    const describedId = password.getAttribute('aria-describedby');
    expect(describedId).toBeTruthy();
    expect(document.getElementById(describedId!)).toHaveTextContent(
      'Password cannot be empty.'
    );
    expect(screen.getByLabelText(/username/i)).not.toHaveAttribute('aria-invalid');
  });

  it('clears a field error when the field is edited and returns to pristine after reset', async () => {
    render(<SignInForm />, { wrapper: createWrapper() });

    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/username/i)).toHaveAttribute('aria-invalid', 'true');

    const username = screen.getByLabelText(/username/i);
    fireEvent.change(username, { target: { value: 'admin' } });
    expect(username).not.toHaveAttribute('aria-invalid');

    fireEvent.change(username, { target: { value: '' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: '' } });
    expect((username as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText(/password/i) as HTMLInputElement).value).toBe('');
  });

  it('suppresses duplicate click and Enter submission while pending', async () => {
    let resolveSignIn: ((user: Record<string, unknown>) => void) | undefined;
    const signInCalls = vi.fn();
    server.use(
      http.post('/api/v1/auth/sign-in', async () => {
        signInCalls();
        await new Promise<void>((resolve) => {
          resolveSignIn = () => resolve();
        });
        return HttpResponse.json({
          id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
          username: 'admin',
          display_name: 'Admin User',
          role: 'admin',
          permissions: [],
          auth_provider: 'local',
        });
      })
    );

    render(<SignInForm />, { wrapper: createWrapper() });
    fill('admin', SECRET);
    const button = screen.getByRole('button', { name: /sign in/i });

    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.keyDown(screen.getByLabelText(/password/i), { key: 'Enter' });

    expect(await screen.findByRole('button', { name: /signing in/i })).toBeDisabled();

    await act(async () => {
      resolveSignIn?.();
    });
    await waitFor(() => {
      expect(signInCalls).toHaveBeenCalledTimes(1);
    });
  });

  it('announces safe server rejection without leaking the secret and allows retry', async () => {
    let reject = true;
    server.use(
      http.post('/api/v1/auth/sign-in', async () => {
        if (reject) {
          return HttpResponse.json({ error: 'unauthorized' }, { status: 401 });
        }
        return HttpResponse.json({
          id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
          username: 'admin',
          display_name: 'Admin User',
          role: 'admin',
          permissions: [],
          auth_provider: 'local',
        });
      })
    );

    const { container } = render(<SignInForm />, { wrapper: createWrapper() });
    fill('admin', SECRET);
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Invalid username or password'
      );
    });
    expect(container.innerHTML).not.toContain(SECRET);
    expect((screen.getByLabelText(/username/i) as HTMLInputElement).value).toBe('admin');

    reject = false;
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
    expect(screen.getByRole('status')).toHaveTextContent('Signed in successfully.');
  });

  it('submits once through keyboard activation of a text input', async () => {
    const signInSpy = vi.fn();
    server.use(
      http.post('/api/v1/auth/sign-in', async ({ request }) => {
        signInSpy(await request.clone().json());
        return HttpResponse.json({
          id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
          username: 'admin',
          display_name: 'Admin User',
          role: 'admin',
          permissions: [],
          auth_provider: 'local',
        });
      })
    );

    render(<SignInForm />, { wrapper: createWrapper() });
    fill('admin', SECRET);

    fireEvent.submit(screen.getByLabelText(/password/i).closest('form')!);

    await waitFor(() => {
      expect(signInSpy).toHaveBeenCalledWith({ username: 'admin', password: SECRET });
    });
    expect(signInSpy).toHaveBeenCalledTimes(1);
  });

  it('leaves no stale settlement after unmount during a pending attempt', async () => {
    let resolveSignIn: (() => void) | undefined;
    server.use(
      http.post('/api/v1/auth/sign-in', async () => {
        await new Promise<void>((resolve) => {
          resolveSignIn = resolve;
        });
        return HttpResponse.json({ error: 'unauthorized' }, { status: 401 });
      })
    );

    const { unmount } = render(<SignInForm />, { wrapper: createWrapper() });
    fill('admin', SECRET);
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    unmount();
    await act(async () => {
      resolveSignIn?.();
    });

    expect(document.querySelector('[role="alert"]')).toBeNull();
    expect(document.body.textContent).not.toContain(SECRET);
  });
});

function passwordDescribedBy(field: HTMLElement): string {
  const describedId = field.getAttribute('aria-describedby');
  if (!describedId) return '';
  return document.getElementById(describedId)?.textContent ?? '';
}
