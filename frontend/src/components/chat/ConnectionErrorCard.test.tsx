import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import { ConnectionErrorCard } from './ConnectionErrorCard';
import type { ConnectionErrorKind } from './ConnectionErrorCard';

const connectionManagementKinds = [
  'noConnections',
  'disabled',
  'unhealthy',
  'noSchema',
] as const;

const retryKinds = ['queryExecutionFailed', 'timeout'] as const;

afterEach(async () => {
  await i18n.changeLanguage('en');
});

describe('ConnectionErrorCard recovery actions', () => {
  it.each(connectionManagementKinds)(
    'renders localized non-interactive guidance for %s without management permission',
    (kind) => {
      render(<ConnectionErrorCard kind={kind} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(screen.getByText('Ask a connection administrator to review this connection.')).toBeInTheDocument();
    }
  );

  it.each(connectionManagementKinds)(
    'wires %s to the supplied connections-management navigation',
    (kind) => {
      const onManageConnections = vi.fn();
      render(
        <ConnectionErrorCard
          kind={kind}
          onManageConnections={onManageConnections}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Manage connections' }));
      expect(onManageConnections).toHaveBeenCalledOnce();
    }
  );

  it.each(retryKinds)(
    'renders immutable-context guidance for %s when retry is unavailable',
    (kind) => {
      render(<ConnectionErrorCard kind={kind} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(
        screen.getByText(
          'Retry is unavailable because the original query context is no longer active.'
        )
      ).toBeInTheDocument();
    }
  );

  it.each(retryKinds)('wires %s to the supplied immutable-context retry', (kind) => {
    const onRetry = vi.fn();
    render(<ConnectionErrorCard kind={kind} onRetry={onRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('announces pending retry feedback and suppresses another click', () => {
    const onRetry = vi.fn();
    render(
      <ConnectionErrorCard
        kind="timeout"
        onRetry={onRetry}
        isRetrying
      />
    );

    expect(screen.getByRole('status')).toHaveTextContent('Retrying the original question…');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeDisabled();
  });

  it('localizes guidance and action names in Arabic RTL', async () => {
    await i18n.changeLanguage('ar');
    const { rerender } = render(<ConnectionErrorCard kind="disabled" />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText('اطلب من مسؤول الاتصالات مراجعة هذا الاتصال.')).toBeInTheDocument();

    rerender(<ConnectionErrorCard kind="timeout" onRetry={() => {}} />);
    expect(screen.getByRole('button', { name: 'إعادة المحاولة' })).toBeInTheDocument();
  });

  it('falls back to a generic sanitized message for an unknown kind', () => {
    render(<ConnectionErrorCard kind={'unknown_kind' as ConnectionErrorKind} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Error');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('never renders raw backend details', () => {
    const { container } = render(<ConnectionErrorCard kind="unhealthy" />);
    expect(container).not.toHaveTextContent(/127\.0\.0\.1|password|host:|port:/i);
  });
});
