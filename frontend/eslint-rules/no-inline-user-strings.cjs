'use strict';

const USER_FACING_ATTRS = new Set([
  'title',
  'placeholder',
  'aria-label',
  'aria-description',
  'alt',
  'label',
]);

const NON_USER_FACING_ATTRS = new Set([
  'data-testid',
  'className',
  'key',
  'id',
  'role',
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

function isNonUserFacingAttr(node) {
  if (node.type !== 'JSXAttribute') return false;
  const attrName = node.name.name;
  if (NON_USER_FACING_ATTRS.has(attrName)) return true;
  if (attrName.startsWith('data-') || attrName.startsWith('dataset.')) return true;
  return false;
}

function shouldFlagString(text) {
  if (text.length === 0) return false;
  if (TECHNICAL_ONLY.test(text)) return false;
  if (TECHNICAL_LIKE.test(text)) return false;
  return true;
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
    function reportLiteral(node, messageId, data) {
      context.report({ node, messageId, data });
    }

    function checkLiteral(node) {
      if (typeof node.value !== 'string') return;
      const text = node.value.trim();
      if (!shouldFlagString(text)) return;
      if (isInsideTCall(node)) return;
      reportLiteral(node, 'jsxText');
    }

    function checkTemplateLiteral(node) {
      const raw = node.quasis.map((q) => q.value.raw).join('');
      const text = raw.trim();
      if (!shouldFlagString(text)) return;
      if (isInsideTCall(node)) return;
      reportLiteral(node, 'jsxText');
    }

    return {
      JSXText(node) {
        const text = node.value.trim();
        if (!shouldFlagString(text)) return;
        reportLiteral(node, 'jsxText');
      },
      Literal(node) {
        // Only handle Literal directly inside JSXAttribute value.
        // Literals inside JSXExpressionContainer are handled by the
        // JSXExpressionContainer visitor so we don't descend into
        // nested function bodies (e.g. event handlers).
        if (node.parent.type !== 'JSXAttribute') return;
        const attrName = node.parent.name.name;
        if (!USER_FACING_ATTRS.has(attrName)) return;
        if (typeof node.value !== 'string') return;
        const text = node.value.trim();
        if (!shouldFlagString(text)) return;
        if (isInsideTCall(node)) return;
        reportLiteral(node, 'jsxAttr', { attr: attrName });
      },
      JSXExpressionContainer(node) {
        const expr = node.expression;
        if (!expr) return;

        // If this JSXExpressionContainer is the value of a JSXAttribute,
        // let the JSXAttribute visitor handle it so we get the correct messageId.
        const isInsideAttr = node.parent && node.parent.type === 'JSXAttribute';
        const attrName = isInsideAttr ? node.parent.name.name : null;
        if (isInsideAttr && attrName && !USER_FACING_ATTRS.has(attrName)) return;
        if (isInsideAttr && attrName && isNonUserFacingAttr(node.parent)) return;

        if (expr.type === 'Literal' && typeof expr.value === 'string') {
          if (isInsideAttr) {
            reportLiteral(expr, 'jsxAttr', { attr: attrName });
          } else {
            checkLiteral(expr);
          }
          return;
        }

        if (expr.type === 'TemplateLiteral') {
          if (isInsideAttr) {
            reportLiteral(expr, 'jsxAttr', { attr: attrName });
          } else {
            checkTemplateLiteral(expr);
          }
          return;
        }

        if (expr.type === 'ConditionalExpression') {
          for (const branch of [expr.consequent, expr.alternate]) {
            if (branch.type === 'Literal' && typeof branch.value === 'string') {
              if (isInsideAttr) {
                reportLiteral(branch, 'jsxAttr', { attr: attrName });
              } else {
                checkLiteral(branch);
              }
            } else if (branch.type === 'TemplateLiteral') {
              if (isInsideAttr) {
                reportLiteral(branch, 'jsxAttr', { attr: attrName });
              } else {
                checkTemplateLiteral(branch);
              }
            }
          }
          return;
        }
      },

    };
  },
};
