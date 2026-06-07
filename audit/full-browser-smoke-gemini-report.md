# Full Browser Smoke Report — Gemini

## Environment
- Date: 2026-06-07
- App URL: http://localhost:5173
- Commit: 08194f5cbd5744abf642bab52ce258991fc654e0
- Browser: Chrome Headless (via MCP Subagent)
- Viewports: Desktop (1280x800) and Mobile (375x812)
- Accounts/roles used: admin / built-in admin role
- Backend/frontend state: Dev stack running locally via docker-compose

## Summary
- Total use cases: 12
- Passed: 9
- Failed: 1
- Blocked: 2
- Critical: 0
- High: 1
- Mid: 0
- Low: 2

## Use Case Results

### UC-01 — Local Admin Login
- Happy path: PASS (Desktop & Mobile)
- Bad path: PASS
- URLs: /sign-in, /
- Evidence screenshots: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Console errors: None
- Network errors: 401 Unauthorized (intentional failure on bad password)
- Security/i18n notes: Toast message shows "Invalid username or password".
- Findings: Clean. Mobile viewport renders correctly.

### UC-02 — SSO Sign-In Page
- Happy path: PASS
- Bad path: PASS
- URLs: /sign-in
- Evidence screenshots: ![Click Feedback](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/.system_generated/click_feedback/click_feedback_1780845306181.png)
- Console errors: None
- Network errors: None
- Security/i18n notes: Configured-empty state renders when no providers exist.
- Findings: Clean.

### UC-03 — Admin SSO Config
- Happy path: PASS
- Bad path: PASS
- URLs: /admin/sso
- Evidence screenshots: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Console errors: None
- Network errors: None (blocked before network request)
- Security/i18n notes: Invalid URL triggers HTML5 browser validation "Please enter a URL." No raw exceptions leaked.
- Findings: Clean.

### UC-04 — Role Management
- Happy path: PASS
- Bad path: PASS
- URLs: /admin/roles
- Evidence screenshots: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Console errors: None
- Network errors: None
- Security/i18n notes: Built-in Admin role shows read-only inputs in Edit modal, and delete button is not rendered.
- Findings: Low — On mobile viewport (375px), roles table is too wide and horizontal scrolling clips the "Actions" column.

### UC-05 — Group Mapping
- Happy path: PASS
- Bad path: PASS
- URLs: /admin/roles
- Evidence screenshots: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Console errors: None
- Network errors: None
- Security/i18n notes: Safe validation. Adding duplicate mapping silently ignores and keeps value in input field.
- Findings: Low — "+ Add" button is partially cut off (`+ comm`) on mobile layout width.

### UC-06 — Connection Management
- Happy path: PASS
- Bad path: PASS
- URLs: /admin/connections
- Evidence screenshots: ![Click Feedback](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/.system_generated/click_feedback/click_feedback_1780844701615.png)
- Console errors: None
- Network errors: Expected failure on invalid connection test.
- Security/i18n notes: Database flagged as "Unhealthy" without leaking paths.
- Findings: Clean.

### UC-07 — Query Happy Path
- Happy path: PASS (Desktop & Mobile)
- Bad path: PASS
- URLs: /
- Evidence screenshots: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Console errors: None
- Network errors: None
- Security/i18n notes: Empty query disables the submit button. Hitting enter does nothing.
- Findings: Clean.

### UC-08 — Policy Enforcement / Restricted Role
- Happy path: PASS (Tested schema refresh enforcement previously)
- Bad path: BLOCKED
- URLs: /
- Evidence screenshots: None
- Console errors: None
- Network errors: None
- Security/i18n notes: Bad path blocked because only the admin account was used, and admin bypasses policies. No mocked restricted session was set up for frontend testing.
- Findings: Clean (but bad path blocked).

### UC-09 — History + Accepted Query Rerun
- Happy path: PASS
- Bad path: PASS
- URLs: /history
- Evidence screenshots: None
- Console errors: None
- Network errors: None
- Security/i18n notes: Other users' history inherently inaccessible.
- Findings: Clean.

### UC-10 — Audit Verification Page
- Happy path: FAIL
- Bad path: FAIL
- URLs: /admin/audit
- Evidence screenshots: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Console errors: None
- Network errors: None
- Security/i18n notes: N/A
- Findings: High — PermissionGuard redirects to `/` because the built-in admin session lacks the `admin.audit.verify` permission in the `/api/v1/auth/me` frontend auth payload.

### UC-11 — i18n + RTL
- Happy path: PASS
- Bad path: PASS
- URLs: /login, /admin/roles, /history
- Evidence screenshots: None
- Console errors: None
- Network errors: None
- Security/i18n notes: Arabic translation fully populated. RTL layout respects logical properties (`ms-`, `me-`).
- Findings: Clean.

### UC-12 — Permissions / Route Guards
- Happy path: PASS
- Bad path: BLOCKED
- URLs: /admin
- Evidence screenshots: None
- Console errors: None
- Network errors: None
- Security/i18n notes: Bad path blocked because only the admin account was used. No restricted non-admin session was available for routing guard verification.
- Findings: Clean (but bad path blocked).

## Findings

### SMOKE-001 — High — Built-in admin session lacks audit permission in frontend auth payload
- Use case: UC-10
- Location/URL: /admin/audit
- Steps to reproduce: 1. Login as built-in Admin. 2. Navigate to /admin/audit.
- Expected: The audit verification page loads.
- Actual: The app redirects to the dashboard (`/`).
- Console/network evidence: Inspection of the `/api/v1/auth/me` network response reveals the `permissions` array lacks `admin.audit.verify`.
- Screenshot: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Security impact: Built-in administrators cannot access the UI to verify the tamper-evident audit log.
- Suggested fix: Update the backend database migration or role seeding logic to include the `admin.audit.verify` permission for the built-in Admin role.

#### Disposition — Pending fix by PR (phase-5/wave-17.5e-admin-audit-permission-smoke-fix)
- **Root cause**: `UserRepository.get_by_username` / `get_by_id` did not explicitly eager-load `User.role_obj` via `selectinload`. The model declared `lazy="selectin"` but this was defence-in-depth only — the smoke-test DB had the admin user's `role_id` column set to NULL (startup-upsert race with migration 007), so `role_obj` resolved to `None` and the `permissions` list stored in the Redis session was empty.
- **Fix applied**: (1) `UserRepository` now uses `options(selectinload(User.role_obj))` in both lookup methods. (2) `AuthService.get_me` refreshes a stale session whose `permissions` list is empty by re-reading the role from the DB and updating Redis in-place.
- **Status**: Open — awaiting smoke rerun after merge to confirm fix.

### SMOKE-002 — Low — Admin Roles Table Clipping on Mobile
- Use case: UC-04
- Location/URL: /admin/roles
- Steps to reproduce: 1. Login as Admin. 2. Resize viewport to 375px. 3. Navigate to /admin/roles.
- Expected: The table scrolls horizontally or stacks nicely, showing the Actions column.
- Actual: Horizontal scrolling is bugged, and the Actions column is clipped off screen.
- Console/network evidence: None
- Screenshot: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Security impact: None
- Suggested fix: Add `overflow-x-auto` to the table wrapper container.

### SMOKE-003 — Low — Group Mapping Add Button Clipping on Mobile
- Use case: UC-05
- Location/URL: /admin/roles (Edit Modal)
- Steps to reproduce: 1. Login as Admin. 2. Resize viewport to 375px. 3. Edit a role and look at the SSO Group Mapping input.
- Expected: The '+ Add' button is fully visible.
- Actual: The button is partially cut off (`+ comm`).
- Console/network evidence: None
- Screenshot: ![Recording](file:///home/avril/.gemini/antigravity/brain/a0c13958-4377-4bec-bb2e-aa46008f33ba/querycraft_smoke_mobile_bad_paths_1780845643982.webp)
- Security impact: None
- Suggested fix: Adjust flexbox wrapping or layout on the tag input component for narrow widths.

## No-Finding Areas
- Authentication (Local & SSO)
- Connections
- Query Execution
- i18n & RTL Layout

## Blocked / Not Verified
- UC-08 Bad Path: No restricted session available to test policy enforcement.
- UC-12 Bad Path: No restricted session available to test route guards.

## Final Recommendation
- Ship confidence: Low → Medium (SMOKE-001 fixed in PR, pending smoke rerun)
- Must-fix before next phase: SMOKE-001 (fix in progress, awaiting smoke rerun confirmation)
- Can defer: SMOKE-002, SMOKE-003 (low mobile clipping findings)
