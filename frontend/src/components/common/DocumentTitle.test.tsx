import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { Link, MemoryRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import i18n from '../../i18n';
import { DocumentTitle } from './DocumentTitle';

const titleCases = [
  ['/sign-in', 'Sign In', 'تسجيل الدخول'],
  ['/', 'Workspace', 'مساحة العمل'],
  ['/ask', 'Ask a Question', 'اطرح سؤالاً'],
  ['/history', 'Query History', 'سجل الاستعلامات'],
  ['/settings', 'Settings', 'الإعدادات'],
  ['/admin/connections', 'Database Connections', 'اتصالات قواعد البيانات'],
  ['/admin/roles', 'Roles & Permissions', 'الأدوار والأذونات'],
  ['/admin/sso', 'Single Sign-On', 'تسجيل الدخول الموحّد'],
  ['/admin/audit', 'Audit Logs', 'سجلات التدقيق'],
  ['/admin/quotas', 'Role Quotas', 'حصص الأدوار'],
  ['/admin/detection', 'Hostile Input Detection', 'كشف المدخلات المعادية'],
  ['/access-denied', 'Access Denied', 'تم رفض الوصول'],
] as const;

const localizedTitleCases = titleCases.flatMap(([path, english, arabic]) => [
  [path, 'en', `${english} | QueryCraft`],
  [path, 'ar', `${arabic} | QueryCraft`],
] as const);

function NavigationProbe() {
  const navigate = useNavigate();

  return (
    <nav>
      <Link to="/">Workspace</Link>
      <Link to="/history">History</Link>
      <button type="button" onClick={() => navigate(-1)}>Back</button>
      <button type="button" onClick={() => navigate(1)}>Forward</button>
    </nav>
  );
}

describe('DocumentTitle', () => {
  beforeEach(async () => {
    document.title = 'Previous route title';
    await i18n.changeLanguage('en');
  });

  it.each(localizedTitleCases)(
    'brands %s in %s on direct load',
    async (path, language, expectedTitle) => {
      await i18n.changeLanguage(language);
      render(
        <MemoryRouter initialEntries={[path]}>
          <DocumentTitle />
        </MemoryRouter>
      );

      await waitFor(() => expect(document.title).toBe(expectedTitle));
      expect(document.title).not.toContain('documentTitle.');
    }
  );

  it('tracks links, back, forward, and active-locale changes without a stale title', async () => {
    render(
      <MemoryRouter initialEntries={['/sign-in']}>
        <DocumentTitle />
        <NavigationProbe />
      </MemoryRouter>
    );

    await waitFor(() => expect(document.title).toBe('Sign In | QueryCraft'));

    fireEvent.click(screen.getByRole('link', { name: 'Workspace' }));
    expect(document.title).toBe('Workspace | QueryCraft');

    fireEvent.click(screen.getByRole('link', { name: 'History' }));
    expect(document.title).toBe('Query History | QueryCraft');

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(document.title).toBe('Workspace | QueryCraft');

    fireEvent.click(screen.getByRole('button', { name: 'Forward' }));
    expect(document.title).toBe('Query History | QueryCraft');

    await i18n.changeLanguage('ar');
    await waitFor(() => expect(document.title).toBe('سجل الاستعلامات | QueryCraft'));
  });

  it('replaces an unknown-route title after a redirect', async () => {
    render(
      <MemoryRouter initialEntries={['/unknown']}>
        <DocumentTitle />
        <Routes>
          <Route path="/unknown" element={<Navigate to="/history" replace />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(document.title).toBe('Query History | QueryCraft'));
    expect(document.title).not.toBe('Previous route title');
  });
});
