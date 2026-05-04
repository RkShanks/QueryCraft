import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'
import noInlineUserStrings from './eslint-rules/no-inline-user-strings.cjs'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: {
      local: { rules: { 'no-inline-user-strings': noInlineUserStrings } },
    },
    rules: {
      'local/no-inline-user-strings': 'error',
    },
    languageOptions: {
      globals: globals.browser,
    },
  },
])
