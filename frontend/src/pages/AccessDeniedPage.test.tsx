import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import appI18n from '../i18n';
import { server } from '../test/server';
import { createWrapper } from '../test/utils';
import { AccessDeniedPage } from './AccessDeniedPage';

describe('AccessDeniedPage', () => {
  afterEach(async () => {
    await appI18n.changeLanguage('en');
  });

  it.each([
    ['en', 'Access denied', 'Your account does not have permission to use this area.', 'Sign Out'],
    ['ar', 'تم رفض الوصول', 'لا يملك حسابك الإذن لاستخدام هذه المنطقة.', 'تسجيل الخروج'],
  ])('renders localized accessible controls in %s', async (language, title, description, signOut) => {
    await appI18n.changeLanguage(language);
    render(<AccessDeniedPage />, { wrapper: createWrapper() });

    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    expect(screen.getByText(description)).toBeInTheDocument();
    const button = screen.getByRole('button', { name: signOut });
    button.focus();
    expect(button).toHaveFocus();
  });

  it('keeps the server session truthful and retryable after failed sign-out', async () => {
    server.use(
      http.post('/api/v1/auth/sign-out', () =>
        HttpResponse.json({ error: 'unavailable' }, { status: 503 })
      )
    );
    render(<AccessDeniedPage />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByRole('button', { name: 'Sign Out' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Sign out failed. Your server session is still active. Please try again.'
    );
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign Out' })).toBeEnabled());
  });
});
