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

  it.each([
    ['en', 'Retry'],
    ['ar', 'إعادة المحاولة'],
  ])('exposes an explicit localized Retry action that re-attempts sign-out in %s', async (language, retryLabel) => {
    let signOutRequests = 0;
    server.use(
      http.post('/api/v1/auth/sign-out', () => {
        signOutRequests += 1;
        if (signOutRequests === 1) {
          return HttpResponse.json({ error: 'unavailable' }, { status: 503 });
        }
        return new HttpResponse(null, { status: 204 });
      })
    );
    await appI18n.changeLanguage(language);
    render(<AccessDeniedPage />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByRole('button', { name: language === 'ar' ? 'تسجيل الخروج' : 'Sign Out' }));
    await screen.findByRole('alert');

    fireEvent.click(screen.getByRole('button', { name: retryLabel }));

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(signOutRequests).toBe(2);
  });
});
