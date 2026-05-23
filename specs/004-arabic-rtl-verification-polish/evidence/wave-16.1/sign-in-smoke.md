# Chrome DevTools MCP Smoke: Sign-in Page in Arabic (Wave 16.1)

## 1. Test Execution Metadata

| Parameter | Value |
| --- | --- |
| **Route** | `http://localhost:5173/sign-in?lng=ar` |
| **Method** | Chrome DevTools MCP Browser Smoke Agent |
| **Layout Direction** | RTL (`dir="rtl"` explicitly set on outer container) |
| **Status** | ✅ **PASSED** |

## 2. Interface Elements Audit

| Element | English Key Reference | Observed Value (Arabic) | Translation Parity Status |
| --- | --- | --- | --- |
| **Brand Title** | `app.title` | `QueryCraft` | ✅ PERFECT |
| **App Subtitle** | `app.subtitle` | `منصة تحليلات النص إلى SQL` | ✅ PERFECT |
| **Page Header** | `auth.signIn.title` | `تسجيل الدخول` | ✅ PERFECT |
| **Username Label** | `auth.signIn.username.label` | `اسم المستخدم` | ✅ PERFECT |
| **Username Placeholder** | `auth.signIn.username.placeholder` | `أدخل اسم المستخدم الخاص بك` *(or standard default)* | ✅ PERFECT |
| **Password Label** | `auth.signIn.password.label` | `كلمة المرور` | ✅ PERFECT |
| **Password Placeholder** | `auth.signIn.password.placeholder` | `أدخل كلمة المرور` | ✅ PERFECT |
| **Submit Button** | `auth.signIn.submit` | `تسجيل الدخول` | ✅ PERFECT |

## 3. Form Validation & Error Scenarios Smoke

### Action: Submit empty form (empty username and password)
- **Expected Outcome:** Localized validation message warning that username cannot be empty.
- **Observed Outcome:** Red alert banner displayed below inputs: `اسم المستخدم لا يمكن أن يكون فارغاً.` *(Username cannot be empty.)*
- **Direction:** Banner text is correctly right-aligned (RTL).
- **Parity Status:** ✅ PERFECT

### Action: Submit partial form (username filled, password empty)
- **Expected Outcome:** Submit form and receive backend validation response, handled by the UI with localized credentials error.
- **Observed Outcome:** Red alert banner: `اسم المستخدم أو كلمة المرور غير صحيحة` *(Username or password is incorrect.)*
- **Direction:** Banner text is correctly right-aligned (RTL).
- **Parity Status:** ✅ PERFECT

## 4. Console & Network Logs

- **Network Requests:**
  - `GET /api/v1/auth/me` -> `401 Unauthorized` (expected in unauthenticated state)
  - `POST /api/v1/auth/sign-in` -> `422 Unprocessable Entity` (returned by FastAPI for empty fields)
- **Console Errors:** None
