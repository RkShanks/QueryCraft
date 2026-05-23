import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SqlDisplay } from './SqlDisplay';
import { createWrapper } from '../../test/utils';

describe('SqlDisplay', () => {
  it('should render the SQL in a preformatted block', () => {
    render(<SqlDisplay sql="SELECT * FROM users;" />, { wrapper: createWrapper() });
    expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
  });

  it('should show the SQL heading via i18n', () => {
    render(<SqlDisplay sql="SELECT 1;" />, { wrapper: createWrapper() });
    expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
  });

  it('should render the SQL pre block with dir="ltr"', () => {
    render(<SqlDisplay sql="SELECT 1;" />, { wrapper: createWrapper() });
    const pre = screen.getByText('SELECT 1;');
    expect(pre).toHaveAttribute('dir', 'ltr');
  });
});
