'use strict';

const USER_FACING_ATTRS = new Set([
  'title',
  'placeholder',
  'aria-label',
  'aria-description',
  'alt',
  'label',
]);

// Strings consisting purely of digits, whitespace, or punctuation are allowed.
const TECHNICAL_ONLY = /^[\d\s\p{P}\p{S}]+$/u;

// Allow short ASCII-only strings that look like CSS classes, ids, hex colors, urls.
const TECHNICAL_LIKE = /^(#[0-9a-fA-F]{3,8}|https?:\/\/|\/[\w/-]+)$/;

function isInsideTCall(node) {
  let parent = node.parent;
  while (parent) {
    if (
      parent.type === 'CallExpression' &&
      parent.callee &&
      ((parent.callee.type === 'Identifier' && parent.callee.name === 't') ||
       (parent.callee.type === 'MemberExpression' &&
        parent.callee.property &&
        parent.callee.property.name === 't'))
    ) {
      return true;
    }
    parent = parent.parent;
  }
  return false;
}

module.exports = {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Disallow inline user-facing string literals; require i18next t() calls so all user-facing copy is translatable.',
    },
    schema: [],
    messages: {
      jsxText:
        'Inline user-facing string in JSX. Wrap with i18n t("key") so it can be translated.',
      jsxAttr:
        'Inline user-facing string on attribute "{{attr}}". Use i18n t("key") for translatable values.',
    },
  },
  create(context) {
    return {
      JSXText(node) {
        const text = node.value.trim();
        if (text.length === 0) return;
        if (TECHNICAL_ONLY.test(text)) return;
        if (TECHNICAL_LIKE.test(text)) return;
        context.report({ node, messageId: 'jsxText' });
      },
      Literal(node) {
        if (node.parent.type !== 'JSXAttribute') return;
        const attrName = node.parent.name.name;
        if (!USER_FACING_ATTRS.has(attrName)) return;
        if (typeof node.value !== 'string') return;
        const text = node.value.trim();
        if (text.length === 0) return;
        if (TECHNICAL_ONLY.test(text)) return;
        if (TECHNICAL_LIKE.test(text)) return;
        if (isInsideTCall(node)) return;
        context.report({
          node,
          messageId: 'jsxAttr',
          data: { attr: attrName },
        });
      },
    };
  },
};
