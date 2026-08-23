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

// One shared construction attempt; a rejection is remembered so no mount can
// turn it into an unhandled rejection.
let highlighterReady: Promise<Awaited<ReturnType<typeof createHighlighter>>> | null = null;

function getHighlighter() {
  if (!highlighterReady) {
    highlighterReady = createHighlighter({
      themes: [querycraftTheme],
      langs: ['sql'],
    });
    highlighterReady.catch(() => {
      // Handled per-mount below; this guard only prevents global rejections.
    });
  }
  return highlighterReady;
}

interface ShikiHighlighterProps {
  code: string;
}

export function ShikiHighlighter({ code }: ShikiHighlighterProps) {
  const [html, setHtml] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getHighlighter()
      .then((highlighter) => {
        if (cancelled) return;
        setHtml(highlighter.codeToHtml(code, { lang: 'sql', theme: 'querycraft' }));
      })
      .catch(() => {
        // Local recovery: readable plain text instead of an empty island.
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (failed) {
    return (
      <div className="shiki-fallback" data-testid="shiki-fallback" dir="ltr">
        <pre className="bg-obsidian-950 p-4 rounded-xl border border-obsidian-800 overflow-x-auto text-obsidian-200">
          <code className="text-xs font-mono leading-relaxed font-light" dir="ltr">{code}</code>
        </pre>
      </div>
    );
  }

  return (
    <div
      className="shiki-highlighter"
      data-testid="shiki-highlighter"
      dir="ltr"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
