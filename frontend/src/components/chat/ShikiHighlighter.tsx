import { useEffect, useState } from 'react';
import { createHighlighter } from 'shiki';

const querycraftTheme = {
  name: 'querycraft',
  type: 'dark' as const,
  colors: {
    'editor.background': '#0f172a',
    'editor.foreground': '#e2e8f0',
  },
  tokenColors: [
    { scope: ['keyword', 'storage.type'], settings: { foreground: '#06b6d4' } },
    { scope: ['string', 'string.quoted'], settings: { foreground: '#8b5cf6' } },
    { scope: ['keyword.operator', 'operator'], settings: { foreground: '#d946ef' } },
    { scope: ['comment'], settings: { foreground: '#64748b', fontStyle: 'italic' } },
    { scope: ['entity.name.function'], settings: { foreground: '#22d3ee' } },
    { scope: ['constant.numeric'], settings: { foreground: '#f472b6' } },
    { scope: ['support.class'], settings: { foreground: '#a78bfa' } },
  ],
};

const highlighterPromise = createHighlighter({
  themes: [querycraftTheme],
  langs: ['sql'],
});

interface ShikiHighlighterProps {
  code: string;
}

export function ShikiHighlighter({ code }: ShikiHighlighterProps) {
  const [html, setHtml] = useState('');

  useEffect(() => {
    let cancelled = false;
    highlighterPromise.then((highlighter) => {
      if (cancelled) return;
      const h = highlighter.codeToHtml(code, {
        lang: 'sql',
        theme: 'querycraft',
      });
      setHtml(h);
    });
    return () => {
      cancelled = true;
    };
  }, [code]);

  return (
    <div
      className="shiki-highlighter"
      data-testid="shiki-highlighter"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
