# i18n Key Parity Audit (Wave 16.1 - i18n/Error Polish)

This document contains the detailed findings of the i18n key parity audit executed between the English translation file (`en.json`) and the Arabic translation file (`ar.json`).

## 1. Audit Scope & Method

The parity audit validates that every localization key defined in `en.json` exists in `ar.json` (and vice-versa), ensuring no missing translation strings exist on either surface. The audit checks:
- **Bi-directional Completeness:** Key set in `en.json` matches key set in `ar.json` exactly.
- **Empty Value Check:** Verified that no key contains an empty, whitespace-only, or null translation in either locale.
- **Key Nesting Format:** Checked flat dot-notation structures (e.g., `query.input.placeholder`).

## 2. Key Metrics

| Metric | value |
| --- | --- |
| **Total Keys in `en.json`** | 265 |
| **Total Keys in `ar.json`** | 265 |
| **Keys in English missing in Arabic** | 0 |
| **Keys in Arabic missing in English** | 0 |
| **Empty or Whitespace-Only Translations in `ar.json`** | 0 |
| **Key Parity Synchronisation** | **100% Match (zero gaps)** |

### Added Keys in Wave 16.1:
- `admin.connections.addSuccess`
- `admin.connections.addError`
- `admin.connections.updateSuccess`
- `admin.connections.updateError`

## 3. Local Validation & Test Coverage

Two distinct automated test suites in the frontend repository continuously enforce bi-directional key parity:

1. **`tests/lint/i18n-completeness.test.ts`**:
   - Asserts that all flattened `en.json` keys exist in `ar.json`.
   - Asserts that all flattened `ar.json` keys exist in `en.json`.
   - Status: **PASSED**

2. **`src/locales/localeCoverage.test.ts`**:
   - Flat-checks sorted key sets for strict equality (`expect(arKeys).toEqual(enKeys)`).
   - Validates existence of specific Wave 14 premium feature keys.
   - Status: **PASSED**

## 4. Key Parity Status Summary

The Wave 16.1 i18n key parity is **perfectly aligned** (265 out of 265 keys fully mapped in both English and Arabic). No keys are missing or extra. All translation targets are defined and verified.
