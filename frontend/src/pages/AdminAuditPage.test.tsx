import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminAuditPage } from './AdminAuditPage';
import { createWrapper, renderWithClient } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse, delay } from 'msw';

const mockLanguageState = { language: 'en' };

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: unknown) => {
      const translations: Record<string, Record<string, string>> = {
        en: {
          'admin.audit.title': 'Tamper-Evident Audit Log Verification',
          'admin.audit.verifyButton': 'Verify Integrity',
          'admin.audit.verifying': 'Verifying...',
          'admin.audit.totalEntries': 'Total Log Entries',
          'admin.audit.lastVerification': 'Last Verification',
          'admin.audit.neverVerified': 'Never verified',
          'admin.audit.status.verified': 'Verified Intact',
          'admin.audit.status.broken': 'Chain Broken',
          'admin.audit.status.brokenDesc': 'A hash mismatch was detected in the audit log chain. The log may have been tampered with or corrupted.',
          'admin.audit.firstBreakAt': 'First break at sequence number',
          'admin.audit.entriesChecked': 'Entries checked',
          'admin.audit.verifiedAt': 'Verified at',
          'admin.audit.loadError': 'Failed to load audit status.',
          'admin.audit.verifySuccess': 'Audit chain integrity verified successfully',
          'admin.audit.verifyFailed': 'Audit chain verification failed',
          'admin.audit.securityWarningTitle': 'Security Warning:',
          'admin.audit.securityWarning': 'No auto-repair utility is provided to preserve evidence. Contact your system administrator to recover the database chain.',
          
          'audit.search.title': 'Search Audit Logs',
          'audit.search.date_from': 'Date From',
          'audit.search.date_to': 'Date To',
          'audit.search.action_type': 'Action Type',
          'audit.search.actor': 'Actor',
          'audit.search.outcome': 'Outcome',
          'audit.search.resource_type': 'Resource Type',
          'audit.search.submit': 'Search',
          'audit.search.reset': 'Reset',
          'audit.search.prev_page': 'Previous',
          'audit.search.next_page': 'Next',
          'audit.search.page_info': 'Page {{page}} of {{totalPages}}',
          'audit.search.all_outcomes': 'All Outcomes',
          'audit.search.outcome.success': 'Success',
          'audit.search.outcome.failure': 'Failure',
          'audit.export.csv': 'Export CSV',
          'audit.export.json': 'Export JSON',
          'audit.export.limit_exceeded': 'Export limit exceeded. Please apply more specific filters.',
          'audit.export.quota_exceeded': 'Daily export quota exceeded. Please try again tomorrow.',
        },
        ar: {
          'admin.audit.title': 'التحقق من سلامة سجل التدقيق المقاوم للتلاعب',
          'admin.audit.verifyButton': 'التحقق من السلامة',
          'admin.audit.verifying': 'جارٍ التحقق...',
          'admin.audit.totalEntries': 'إجمالي إدخالات السجل',
          'admin.audit.lastVerification': 'آخر تحقق',
          'admin.audit.neverVerified': 'لم يتم التحقق منه بعد',
          'admin.audit.status.verified': 'سليم وغير متلاعب به',
          'admin.audit.status.broken': 'سلسلة التدقيق مكسورة',
          'admin.audit.status.brokenDesc': 'تم اكتشاف عدم تطابق في تشفير سلسلة سجل التدقيق. قد يكون السجل قد تعرض للتلاعب أو التلف.',
          'admin.audit.firstBreakAt': 'أول كسر في السلسلة عند رقم الإدخال',
          'admin.audit.entriesChecked': 'الإدخالات التي تم فحصها',
          'admin.audit.verifiedAt': 'تم التحقق في',
          'admin.audit.loadError': 'فشل تحميل حالة سجل التدقيق.',
          'admin.audit.verifySuccess': 'تم التحقق من سلامة سلسلة التدقيق بنجاح',
          'admin.audit.verifyFailed': 'فشل التحقق من سلسلة سجل التدقيق',
          'admin.audit.securityWarningTitle': 'تنبيه أمني:',
          'admin.audit.securityWarning': 'لا تتوفر أداة إصلاح تلقائي للحفاظ على الأدلة. يرجى الاتصال بمسؤول النظام لاستعادة سلسلة قاعدة البيانات.',
          
          'audit.search.title': 'البحث في سجلات التدقيق',
          'audit.search.date_from': 'التاريخ من',
          'audit.search.date_to': 'التاريخ إلى',
          'audit.search.action_type': 'نوع الإجراء',
          'audit.search.actor': 'المنفّذ',
          'audit.search.outcome': 'النتيجة',
          'audit.search.resource_type': 'نوع المورد',
          'audit.search.submit': 'بحث',
          'audit.search.reset': 'إعادة ضبط',
          'audit.search.prev_page': 'السابق',
          'audit.search.next_page': 'التالي',
          'audit.search.page_info': 'الصفحة {{page}} من {{totalPages}}',
          'audit.search.all_outcomes': 'كل النتائج',
          'audit.search.outcome.success': 'نجاح',
          'audit.search.outcome.failure': 'فشل',
          'audit.export.csv': 'تصدير CSV',
          'audit.export.json': 'تصدير JSON',
          'audit.export.limit_exceeded': 'تم تجاوز حد التصدير. يرجى تطبيق عوامل تصفية أكثر تحديداً.',
          'audit.export.quota_exceeded': 'تم تجاوز حصة التصدير اليومية. يرجى المحاولة مرة أخرى غداً.',
        }
      };

      const lang = mockLanguageState.language;
      let val = translations[lang]?.[key] || key;
      const opts = options as Record<string, unknown> | undefined;
      if (opts) {
        val = val.replace(/\{\{(\w+)\}\}/g, (_, match) => String(opts[match] ?? `{{${match}}}`));
      }
      return val;
    },
    i18n: {
      changeLanguage: (lng: string) => {
        mockLanguageState.language = lng;
        return Promise.resolve();
      },
      language: mockLanguageState.language,
    },
  }),
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
}));

describe('AdminAuditPage', () => {
  beforeEach(() => {
    mockLanguageState.language = 'en';
    window.URL.createObjectURL = vi.fn().mockReturnValue('mock-url');
    window.URL.revokeObjectURL = vi.fn();
  });
  it('should display page title and handle empty/never-verified status', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 0,
          last_verification: null,
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    expect(screen.getByText('Tamper-Evident Audit Log Verification')).toBeInTheDocument();
    
    // Total entries display
    expect(await screen.findByText(/Total Log Entries/i)).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();

    // Never verified status
    expect(screen.getByText(/Never verified/i)).toBeInTheDocument();
  });

  it('should display verified intact status correctly', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 42,
          last_verification: {
            verified: true,
            entries_checked: 40,
            first_break_at: null,
            verified_at: '2026-06-07T10:30:00Z',
          },
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Verified Intact/i)).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText(/Entries checked/i)).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
  });

  it('should display chain broken status with warning and no repair options', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 100,
          last_verification: {
            verified: false,
            entries_checked: 85,
            first_break_at: 86,
            verified_at: '2026-06-07T12:00:00Z',
          },
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    // Wait for the status query to finish by checking for total entries value
    expect(await screen.findByText('100')).toBeInTheDocument();

    expect(screen.getAllByText(/Chain Broken/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/First break at sequence number/i)).toBeInTheDocument();

    expect(screen.getByText('86')).toBeInTheDocument();

    // Confirm warning description and no auto-repair warning are shown
    expect(screen.getByText(/A hash mismatch was detected/i)).toBeInTheDocument();
    expect(screen.getByText(/No auto-repair utility is provided/i)).toBeInTheDocument();

    // Ensure no dangerous actions like repair/delete/purge are offered
    expect(screen.queryByRole('button', { name: /repair/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /purge/i })).not.toBeInTheDocument();
  });

  it('should handle verification flow and disable button during mutation', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 15,
          last_verification: null,
        });
      })
    );

    let verifyCalled = false;
    server.use(
      http.post('/api/v1/admin/audit/verify', async () => {
        verifyCalled = true;
        await delay(50);
        return HttpResponse.json({
          verified: true,
          entries_checked: 15,
          first_break_at: null,
          verified_at: '2026-06-07T15:00:00Z',
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    // Wait for the status query to finish by checking for total entries value
    expect(await screen.findByText('15')).toBeInTheDocument();

    const verifyBtn = await screen.findByRole('button', { name: /Verify Integrity/i });
    expect(verifyBtn).not.toBeDisabled();

    fireEvent.click(verifyBtn);

    // During pending verification, button should be disabled and show loading state
    await waitFor(() => {
      expect(verifyBtn).toBeDisabled();
      expect(screen.getByText(/Verifying.../i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(verifyCalled).toBe(true);
    });

    await waitFor(() => {
      expect(verifyBtn).not.toBeDisabled();
      expect(screen.getByText(/Verify Integrity/i)).toBeInTheDocument();
    });
  });

  it('should display sanitized, generic localized error on failure', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 10,
          last_verification: null,
        });
      })
    );

    server.use(
      http.post('/api/v1/admin/audit/verify', async () => {
        await delay(50);
        return HttpResponse.json({
          detail: 'DATABASE ERROR: SELECT * FROM audit_log WHERE hash = $1; password=secret host=127.0.0.1 port=5432 failed',
        }, { status: 500 });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    // Wait for the status query to finish by checking for total entries value
    expect(await screen.findByText('10')).toBeInTheDocument();

    const verifyBtn = await screen.findByRole('button', { name: /Verify Integrity/i });
    expect(verifyBtn).not.toBeDisabled();
    fireEvent.click(verifyBtn);

    // Should display the localized generic error message
    expect(await screen.findByText(/Audit chain verification failed/i)).toBeInTheDocument();

    // Make sure no raw backend sql or connection details leaked
    expect(screen.queryByText(/DATABASE ERROR/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SELECT/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/127.0.0.1/i)).not.toBeInTheDocument();
  });

  describe('Audit Log Search UI', () => {
    beforeEach(() => {
      server.use(
        http.get('/api/v1/admin/audit/status', () => {
          return HttpResponse.json({
            total_entries: 10,
            last_verification: null,
          });
        }),
        http.get('/api/v1/admin/audit/entries', () => {
          return HttpResponse.json({
            entries: [
              {
                sequence_number: 1,
                timestamp: '2026-07-01T12:00:00Z',
                actor_identity: 'user@example.com',
                action_type: 'query.submit',
                resource_type: 'database',
                resource_id: 'db-1',
                outcome: 'success',
                context: { query: 'SELECT 1;' },
              },
            ],
            pagination: {
              page: 1,
              page_size: 1,
              total_entries: 1,
              total_pages: 1,
            },
          });
        })
      );
    });

    it('renders all search form filter fields and a persistent panel title', async () => {
      render(<AdminAuditPage />, { wrapper: createWrapper() });

      expect(await screen.findByText('Search Audit Logs')).toBeInTheDocument();

      expect(screen.getByLabelText('Date From')).toBeInTheDocument();
      expect(screen.getByLabelText('Date To')).toBeInTheDocument();
      expect(screen.getByLabelText('Action Type')).toBeInTheDocument();
      expect(screen.getByLabelText('Actor')).toBeInTheDocument();
      expect(screen.getByLabelText('Outcome')).toBeInTheDocument();
      expect(screen.getByLabelText('Resource Type')).toBeInTheDocument();

      expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Reset' })).toBeInTheDocument();
    });

    it('submits search filters correctly to GET /admin/audit/entries', async () => {
      const requestedParams: Record<string, string> = {};
      server.use(
        http.get('/api/v1/admin/audit/entries', ({ request }) => {
          const url = new URL(request.url);
          url.searchParams.forEach((value, key) => {
            requestedParams[key] = value;
          });
          return HttpResponse.json({
            entries: [],
            pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
          });
        })
      );

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      const dateFrom = await screen.findByLabelText('Date From');
      fireEvent.change(dateFrom, { target: { value: '2026-07-01' } });

      const dateTo = screen.getByLabelText('Date To');
      fireEvent.change(dateTo, { target: { value: '2026-07-02' } });

      const actionType = screen.getByLabelText('Action Type');
      fireEvent.change(actionType, { target: { value: 'query.submit' } });

      const actor = screen.getByLabelText('Actor');
      fireEvent.change(actor, { target: { value: 'user@example.com' } });

      const outcome = screen.getByLabelText('Outcome');
      fireEvent.change(outcome, { target: { value: 'success' } });

      const resourceType = screen.getByLabelText('Resource Type');
      fireEvent.change(resourceType, { target: { value: 'database' } });

      fireEvent.click(screen.getByRole('button', { name: 'Search' }));

      await waitFor(() => {
        expect(requestedParams.start_date).toContain('2026-07-01');
        expect(requestedParams.end_date).toContain('2026-07-02');
        expect(requestedParams.action_type).toBe('query.submit');
        expect(requestedParams.actor_identity).toBe('user@example.com');
        expect(requestedParams.outcome).toBe('success');
        expect(requestedParams.resource_type).toBe('database');
      });
    });

    it('renders audit entries table data correctly', async () => {
      render(<AdminAuditPage />, { wrapper: createWrapper() });

      expect(await screen.findByText('user@example.com')).toBeInTheDocument();
      expect(screen.getByText('query.submit')).toBeInTheDocument();
      expect(screen.getByText('success')).toBeInTheDocument();
      expect(screen.getByText('database')).toBeInTheDocument();
    });

    it('handles pagination next/prev buttons and info text', async () => {
      let pageRequested = '1';
      server.use(
        http.get('/api/v1/admin/audit/entries', ({ request }) => {
          const url = new URL(request.url);
          pageRequested = url.searchParams.get('page') || '1';
          return HttpResponse.json({
            entries: [
              {
                sequence_number: 1,
                timestamp: '2026-07-01T12:00:00Z',
                actor_identity: 'user@example.com',
                action_type: 'query.submit',
                resource_type: 'database',
                resource_id: 'db-1',
                outcome: 'success',
                context: { query: 'SELECT 1;' },
              },
            ],
            pagination: {
              page: Number(pageRequested),
              page_size: 5,
              total_entries: 15,
              total_pages: 3,
            },
          });
        })
      );

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      await screen.findByText('Page 1 of 3');

      const prevBtn = screen.getByRole('button', { name: 'Previous' });
      const nextBtn = screen.getByRole('button', { name: 'Next' });

      expect(prevBtn).toBeDisabled();
      expect(nextBtn).not.toBeDisabled();

      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(pageRequested).toBe('2');
      });

      await screen.findByText('Page 2 of 3');
      expect(prevBtn).not.toBeDisabled();
      expect(nextBtn).not.toBeDisabled();

      fireEvent.click(prevBtn);

      await waitFor(() => {
        expect(pageRequested).toBe('1');
      });
    });

    it('resets fields on Reset button click', async () => {
      server.use(
        http.get('/api/v1/admin/audit/entries', () => {
          return HttpResponse.json({
            entries: [],
            pagination: { page: 1, page_size: 5, total_entries: 0, total_pages: 1 },
          });
        })
      );

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      const actorInput = await screen.findByLabelText('Actor');
      fireEvent.change(actorInput, { target: { value: 'user@example.com' } });
      expect(actorInput).toHaveValue('user@example.com');

      fireEvent.click(screen.getByRole('button', { name: 'Reset' }));

      expect(actorInput).toHaveValue('');
    });

    it('renders Arabic locale with dir="rtl" and shows Arabic labels and logical CSS direction', async () => {
      mockLanguageState.language = 'ar';

      const { container } = renderWithClient(
        <div dir="rtl">
          <AdminAuditPage />
        </div>
      );

      expect(container.firstChild).toHaveAttribute('dir', 'rtl');

      expect(await screen.findByText('البحث في سجلات التدقيق')).toBeInTheDocument();
      expect(screen.getByLabelText('التاريخ من')).toBeInTheDocument();
      expect(screen.getByLabelText('التاريخ إلى')).toBeInTheDocument();
      expect(screen.getByLabelText('نوع الإجراء')).toBeInTheDocument();
      expect(screen.getByLabelText('المنفّذ')).toBeInTheDocument();
      expect(screen.getByLabelText('النتيجة')).toBeInTheDocument();
      expect(screen.getByLabelText('نوع المورد')).toBeInTheDocument();

      const tableHeaders = container.querySelectorAll('th');
      tableHeaders.forEach((th) => {
        expect(th).toHaveClass('text-start');
        expect(th).not.toHaveClass('text-left');
        expect(th).not.toHaveClass('text-right');
      });
    });
  });

  describe('Audit Log Export Controls', () => {
    beforeEach(() => {
      server.use(
        http.get('/api/v1/admin/audit/status', () => {
          return HttpResponse.json({
            total_entries: 10,
            last_verification: null,
          });
        }),
        http.get('/api/v1/admin/audit/entries', () => {
          return HttpResponse.json({
            entries: [],
            pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
          });
        })
      );
    });

    it('triggers CSV export with current search filters on Export CSV click', async () => {
      let exportBody: unknown = null;
      server.use(
        http.post('/api/v1/admin/audit/export', async ({ request }) => {
          exportBody = await request.json();
          return HttpResponse.text('col1,col2\nval1,val2', {
            status: 200,
            headers: {
              'Content-Type': 'text/csv',
              'Content-Disposition': 'attachment; filename="export.csv"',
            },
          });
        })
      );

      const appendSpy = vi.spyOn(document.body, 'appendChild');
      const removeSpy = vi.spyOn(document.body, 'removeChild');
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      const setAttributeSpy = vi.spyOn(HTMLAnchorElement.prototype, 'setAttribute');

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      // Change search filters
      const actorInput = await screen.findByLabelText('Actor');
      fireEvent.change(actorInput, { target: { value: 'export-actor@example.com' } });
      fireEvent.click(screen.getByRole('button', { name: 'Search' }));

      // Click CSV export
      const csvBtn = await screen.findByRole('button', { name: 'Export CSV' });
      fireEvent.click(csvBtn);

      await waitFor(() => {
        expect(exportBody).toEqual({
          format: 'csv',
          actor_identity: 'export-actor@example.com',
        });
      });

      expect(window.URL.createObjectURL).toHaveBeenCalled();
      expect(appendSpy).toHaveBeenCalled();
      expect(setAttributeSpy).toHaveBeenCalledWith('download', expect.stringMatching(/\.csv$/));
      expect(clickSpy).toHaveBeenCalled();
      expect(removeSpy).toHaveBeenCalled();
      expect(window.URL.revokeObjectURL).toHaveBeenCalled();

      appendSpy.mockRestore();
      removeSpy.mockRestore();
      clickSpy.mockRestore();
      setAttributeSpy.mockRestore();
    });

    it('triggers JSON export with current search filters on Export JSON click', async () => {
      let exportBody: unknown = null;
      server.use(
        http.post('/api/v1/admin/audit/export', async ({ request }) => {
          exportBody = await request.json();
          return HttpResponse.text('{}', {
            status: 200,
            headers: {
              'Content-Type': 'application/json',
              'Content-Disposition': 'attachment; filename="export.json"',
            },
          });
        })
      );

      const appendSpy = vi.spyOn(document.body, 'appendChild');
      const removeSpy = vi.spyOn(document.body, 'removeChild');
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      const setAttributeSpy = vi.spyOn(HTMLAnchorElement.prototype, 'setAttribute');

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      // Click JSON export
      const jsonBtn = await screen.findByRole('button', { name: 'Export JSON' });
      fireEvent.click(jsonBtn);

      await waitFor(() => {
        expect(exportBody).toEqual({
          format: 'json',
        });
      });

      expect(window.URL.createObjectURL).toHaveBeenCalled();
      expect(appendSpy).toHaveBeenCalled();
      expect(setAttributeSpy).toHaveBeenCalledWith('download', expect.stringMatching(/\.json$/));
      expect(clickSpy).toHaveBeenCalled();
      expect(removeSpy).toHaveBeenCalled();
      expect(window.URL.revokeObjectURL).toHaveBeenCalled();

      appendSpy.mockRestore();
      removeSpy.mockRestore();
      clickSpy.mockRestore();
      setAttributeSpy.mockRestore();
    });

    it('shows localized narrow filters message on 422 error', async () => {
      server.use(
        http.post('/api/v1/admin/audit/export', () => {
          return HttpResponse.json(
            { detail: { message_key: 'error.export_limit_exceeded' } },
            { status: 422 }
          );
        })
      );

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      const csvBtn = await screen.findByRole('button', { name: 'Export CSV' });
      fireEvent.click(csvBtn);

      expect(await screen.findByText('Export limit exceeded. Please apply more specific filters.')).toBeInTheDocument();
    });

    it('shows localized quota error on 429 quota exceeded error', async () => {
      server.use(
        http.post('/api/v1/admin/audit/export', () => {
          return HttpResponse.json(
            { detail: { message_key: 'error.quota_exceeded' } },
            { status: 429 }
          );
        })
      );

      render(<AdminAuditPage />, { wrapper: createWrapper() });

      const jsonBtn = await screen.findByRole('button', { name: 'Export JSON' });
      fireEvent.click(jsonBtn);

      expect(await screen.findByText('Daily export quota exceeded. Please try again tomorrow.')).toBeInTheDocument();
    });
  });
});
