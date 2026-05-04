import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryInput } from './QueryInput';
import { createWrapper } from '../../test/utils';

describe('QueryInput', () => {
  it('should render textarea with i18n placeholder', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument();
  });

  it('should show live character counter and enforce limit', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    
    expect(screen.getByText(/0 \/ 2000/i)).toBeInTheDocument();
    
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    
    expect(screen.getByText(/15 \/ 2000/i)).toBeInTheDocument();
  });

  it('should disable submit on empty or whitespace', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });
    
    const submitBtn = screen.getByRole('button', { name: /submit/i });
    expect(submitBtn).toBeDisabled();
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: '   ' } });
    
    expect(submitBtn).toBeDisabled();
  });

  it('should disable submit while processing', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={true} />, { wrapper: createWrapper() });
    
    const submitBtn = screen.getByRole('button', { name: /submitting/i });
    expect(submitBtn).toBeDisabled();
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    expect(textarea).toBeDisabled();
  });

  it('should call onSubmit on click or Enter key', () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} isSubmitting={false} />, { wrapper: createWrapper() });
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    const submitBtn = screen.getByRole('button', { name: /submit/i });
    
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    expect(submitBtn).not.toBeDisabled();
    
    fireEvent.click(submitBtn);
    expect(onSubmit).toHaveBeenCalledWith('How many users?');
    
    onSubmit.mockClear();
    
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });
    expect(onSubmit).toHaveBeenCalledWith('How many users?');
  });
});
