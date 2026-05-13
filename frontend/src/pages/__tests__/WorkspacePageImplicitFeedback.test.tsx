import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';

// WorkspacePage uses hooks that are already mocked by MSW in setup.ts.
// Default state renders the empty state since activeSessionId starts null.
describe('WorkspacePage implicit feedback', () => {
  it('renders empty state by default', async () => {
    renderWithClient(<WorkspacePage />);
    expect(screen.getByText('Start a new conversation')).toBeInTheDocument();
  });
});
