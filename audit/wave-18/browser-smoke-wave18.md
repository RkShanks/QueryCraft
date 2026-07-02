# Browser Smoke Report — Wave 18.4b

## Environment
- Date: 2026-07-02
- Viewports:
  - Desktop (1280x800)
  - Tablet (768x1024)
  - Mobile (375x812)
- Browser: Chromium (Headless via Playwright)
- Role: Platform Administrator (`admin`)

## Verification Summary Table

| Use Case | Description | English Pass | Arabic/RTL Pass | Mobile Pass | Screenshot Evidence | Notes |
|---|---|:---:|:---:|:---:|---|---|
| **UC-11** | Admin Quotas Page | PASS | PASS | PASS | [desktop-admin-quotas-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-admin-quotas-ar.png)<br>[mobile-375px-admin-quotas.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-375px-admin-quotas.png)<br>[mobile-768px-admin-quotas.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-768px-admin-quotas.png) | Fully localized, correct RTL grid layout, no overlap. |
| **UC-12** | Quota Exceeded Flow | PASS | PASS | N/A | [desktop-query-flow-quota-exceeded-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-query-flow-quota-exceeded-ar.png) | Localized error banner, sanitized msg without internal limits, reset time shown. |
| **UC-13** | Hostile Input Blocked | PASS | PASS | N/A | [desktop-query-flow-hostile-blocked-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-query-flow-hostile-blocked-ar.png) | Safe blocked message in Arabic, input is not echoed/leaked in UI. |
| **UC-14** | Detection Config | PASS | PASS | PASS | [desktop-admin-detection-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-admin-detection-ar.png)<br>[mobile-375px-admin-detection.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-375px-admin-detection.png)<br>[mobile-768px-admin-detection.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-768px-admin-detection.png) | Form labels in Arabic, inputs RTL aligned, mobile layout stacks nicely. |
| **UC-15** | Audit Search Page | PASS | PASS | PASS | [desktop-audit-search-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-audit-search-ar.png)<br>[mobile-375px-admin-audit.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-375px-admin-audit.png)<br>[mobile-768px-admin-audit.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-768px-admin-audit.png) | Filter labels in Arabic, table headers localized, responsive wrap on mobile. |
| **UC-16** | CSV Export Trigger | PASS | PASS | N/A | [desktop-audit-search-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-audit-search-ar.png) | Arabic export button rendered, functional. |
| **UC-17** | Retention Panel | PASS | PASS | PASS | [desktop-audit-search-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-audit-search-ar.png)<br>[mobile-375px-admin-audit.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-375px-admin-audit.png)<br>[mobile-768px-admin-audit.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-768px-admin-audit.png) | Rendered correctly inside AdminAuditPage, full RTL mirrored structure. |
| **UC-18** | Quota Status Panel | PASS | PASS | PASS | [desktop-admin-quotas-ar.png](file:///home/avril/QueryCraft/audit/wave-18/desktop-admin-quotas-ar.png)<br>[mobile-375px-admin-quotas.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-375px-admin-quotas.png)<br>[mobile-768px-admin-quotas.png](file:///home/avril/QueryCraft/audit/wave-18/mobile-768px-admin-quotas.png) | Rendered correctly, table values aligned, proper RTL/mirroring. |

## Detailed Verification Notes

### UC-11: Admin Quotas Page
- Verified no English fallbacks are present in Arabic locale (`lng=ar`).
- Quotas list and edit form inputs are mirrored correctly in RTL mode.
- Tested mobile viewport size at 375px and 768px. Verified that form columns stack vertically and table contents scroll horizontally without breaking layout containment or clipping text.

### UC-12: Quota Exceeded Flow
- Triggered by mock 429 response. The UI renders `QuotaExceededBanner` successfully.
- The error message in Arabic displays: "تم الوصول إلى الحد اليومي للاستعلامات. يرجى المحاولة مرة أخرى غداً."
- The reset time is parsed and rendered correctly (e.g. "إعادة التعيين في: 3/7/2026 12:00:00 م").
- No internal details (such as current usage counter or system limits) are exposed in the error text.

### UC-13: Hostile Input Blocked
- Triggered by mock 400 response with error code `hostile_input_blocked`.
- The UI renders `HostileInputBlockedBanner` successfully.
- Arabic message displays: "تم حظر هذا الطلب لأنه يحتوي على محتوى ينتهك سياسة الأمان."
- Verified that the blocked query input text is not echoed back to the screen as a result or in a code block.

### UC-14: Detection Config
- Verified page loads correctly in Arabic. Title shows "كشف المدخلات المعادية".
- Configuration values (block/flag thresholds) and help texts are fully translated.
- Viewports at 375px and 768px show correct margins and grid layouts.

### UC-15, UC-16, UC-17, UC-18: Audit Surfaces
- Audit verification and logs search page displays correctly in Arabic RTL.
- Search filters form and table headings mirror alignment in RTL.
- Retention panel ("حفظ سجلات التدقيق") properly shows translated months and purged count in Arabic.
- Quota status panel renders consumption details in RTL.
- Export buttons (CSV/JSON) are localized.
- Triggered CSV export by clicking the Arabic "تصدير CSV" button. Verified that the backend POST request contains `{ format: "csv" }` and that a file download is initiated ending with `.csv`.
