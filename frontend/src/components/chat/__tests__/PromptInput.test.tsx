import { describe, it, expect, vi } from 'vitest';
import { act, render, screen, fireEvent } from '@testing-library/react';
import { PromptInput } from '../PromptInput';
import i18n from '../../../i18n';

const defaultProps = {
  connections: [
    { id: 'conn-1', display_name: 'PostgreSQL DB', database_type: 'postgresql' as const }
  ],
  selectedConnectionId: 'conn-1',
  onSelectConnection: vi.fn(),
  questionLimit: { status: 'ready' as const, maxQuestionLength: 20 },
};

describe('PromptInput', () => {
  it.each([
    ['en', 'Ask a question'],
    ['ar', 'اطرح سؤالاً'],
  ])('provides a localized accessible name in %s', async (language, accessibleName) => {
    await i18n.changeLanguage(language);
    try {
      render(<PromptInput onSubmit={vi.fn()} {...defaultProps} />);

      expect(screen.getByRole('textbox', { name: accessibleName })).toBeInTheDocument();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('renders textarea with placeholder', () => {
    render(<PromptInput onSubmit={vi.fn()} {...defaultProps} />);
    expect(screen.getByPlaceholderText('Ask a question about your data...')).toBeInTheDocument();
  });

  it('submits on Enter key', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} {...defaultProps} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSubmit).toHaveBeenCalledWith('Hello');
  });

  it("does not submit on Shift+Enter", () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} {...defaultProps} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    const preservesNewline = fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(preservesNewline).toBe(true);
  });

  it('does not submit while an IME composition is active', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} {...defaultProps} />);
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'Hello' } });

    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits on Send button click', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} {...defaultProps} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByTestId('prompt-send'));
    expect(onSubmit).toHaveBeenCalledWith('Hello');
  });

  it('has Send button positioned with logical end property', () => {
    render(<PromptInput onSubmit={vi.fn()} {...defaultProps} />);
    const sendBtn = screen.getByTestId('prompt-send');
    expect(sendBtn).toBeInTheDocument();
    expect(sendBtn.className).toContain('prompt-input-send');
  });

  it('disables send button when empty', () => {
    render(<PromptInput onSubmit={vi.fn()} {...defaultProps} />);
    expect(screen.getByTestId('prompt-send')).toBeDisabled();
  });

  it('enables send button when text is entered', () => {
    render(<PromptInput onSubmit={vi.fn()} {...defaultProps} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    expect(screen.getByTestId('prompt-send')).not.toBeDisabled();
  });

  it('clears textarea after submit', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} {...defaultProps} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByTestId('prompt-send'));
    expect(textarea.value).toBe('');
  });

  it('respects disabled prop', () => {
    render(<PromptInput onSubmit={vi.fn()} disabled {...defaultProps} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    expect(textarea).toBeDisabled();
    expect(screen.getByTestId('prompt-send')).toBeDisabled();
  });

  it.each([
    ['limit minus one', 'x'.repeat(3), '3 / 4', false],
    ['limit', 'x'.repeat(4), '4 / 4', false],
    ['limit plus one', 'x'.repeat(5), '5 / 4', true],
    ['surrounding whitespace', ` \t${'x'.repeat(4)}\n`, '4 / 4', false],
    ['Python edge whitespace', `\u001c${'x'.repeat(4)}\u001c`, '4 / 4', false],
    ['non-Python whitespace', `\ufeff${'x'.repeat(3)}`, '4 / 4', false],
    ['Arabic', 'س'.repeat(4), '4 / 4', false],
    ['non-BMP', '😀'.repeat(4), '4 / 4', false],
    ['non-BMP over limit', '😀'.repeat(5), '5 / 4', true],
  ])('counts canonical Unicode code points for %s input', (_caseName, input, counter, isOverLimit) => {
    render(
      <PromptInput
        onSubmit={vi.fn()}
        {...defaultProps}
        questionLimit={{ status: 'ready', maxQuestionLength: 4 }}
      />
    );
    const textarea = screen.getByRole('textbox');

    fireEvent.change(textarea, { target: { value: input } });

    expect(screen.getByTestId('prompt-character-count')).toHaveTextContent(counter);
    expect(screen.getByTestId('prompt-send')).toHaveProperty('disabled', isOverLimit);
    expect(textarea).toHaveAttribute('aria-invalid', String(isOverLimit));
  });

  it.each(['button click', 'Enter'])(
    'keeps over-limit pasted text available and blocks %s',
    (submitAction) => {
    const onSubmit = vi.fn();
    render(
      <PromptInput
        onSubmit={onSubmit}
        {...defaultProps}
        questionLimit={{ status: 'ready', maxQuestionLength: 4 }}
      />
    );
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    const pastedText = 'x'.repeat(5);
    fireEvent.change(textarea, { target: { value: pastedText } });

    if (submitAction === 'button click') {
      fireEvent.click(screen.getByTestId('prompt-send'));
    } else {
      fireEvent.keyDown(textarea, { key: 'Enter' });
    }

    expect(onSubmit).not.toHaveBeenCalled();
    expect(textarea).toHaveValue(pastedText);
    }
  );

  it('associates the counter and localized over-limit error with the textarea', () => {
    render(
      <PromptInput
        onSubmit={vi.fn()}
        {...defaultProps}
        questionLimit={{ status: 'ready', maxQuestionLength: 4 }}
      />
    );
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'x'.repeat(5) } });

    const error = screen.getByRole('alert');
    expect(error).toHaveTextContent('Question must be at most 4 characters.');
    const describedBy = textarea.getAttribute('aria-describedby');
    expect(describedBy).toContain('prompt-character-count');
    expect(describedBy).toContain(error.id);
  });

  it('fails closed while the configured limit is loading', () => {
    render(
      <PromptInput
        onSubmit={vi.fn()}
        {...defaultProps}
        questionLimit={{ status: 'loading' }}
      />
    );

    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByTestId('prompt-send')).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Loading question limit…');
    expect(screen.queryByTestId('prompt-character-count')).not.toBeInTheDocument();
  });

  it('shows a sanitized localized limit error and retries without submitting', () => {
    const onRetry = vi.fn();
    const onSubmit = vi.fn();
    render(
      <PromptInput
        onSubmit={onSubmit}
        {...defaultProps}
        questionLimit={{ status: 'error', onRetry }}
      />
    );

    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to load the question limit.');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('recovers from limit failure and accepts corrected text', () => {
    const onSubmit = vi.fn();
    const { rerender } = render(
      <PromptInput
        onSubmit={onSubmit}
        {...defaultProps}
        questionLimit={{ status: 'error', onRetry: vi.fn() }}
      />
    );
    rerender(
      <PromptInput
        onSubmit={onSubmit}
        {...defaultProps}
        questionLimit={{ status: 'ready', maxQuestionLength: 4 }}
      />
    );
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'x'.repeat(5) } });
    expect(screen.getByRole('alert')).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: 'x'.repeat(4) } });
    fireEvent.click(screen.getByTestId('prompt-send'));

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit).toHaveBeenCalledWith('x'.repeat(4));
  });

  it('allows only one rapid submission at the configured limit', async () => {
    let finishSubmission: (() => void) | undefined;
    const submission = new Promise<void>((resolve) => {
      finishSubmission = resolve;
    });
    const onSubmit = vi.fn(() => submission);
    render(
      <PromptInput
        onSubmit={onSubmit}
        {...defaultProps}
        questionLimit={{ status: 'ready', maxQuestionLength: 4 }}
      />
    );
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'x'.repeat(4) } });

    fireEvent.click(screen.getByTestId('prompt-send'));
    fireEvent.click(screen.getByTestId('prompt-send'));

    expect(onSubmit).toHaveBeenCalledOnce();
    await act(async () => finishSubmission?.());
  });
});
