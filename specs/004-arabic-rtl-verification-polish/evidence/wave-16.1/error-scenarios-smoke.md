# Chrome DevTools MCP Smoke: Localized Error Scenarios in Arabic (Wave 16.1)

## 1. Test Execution Metadata

| Parameter | Value |
| --- | --- |
| **Scope** | App-wide Error Handling Localization |
| **Verification Method** | Automated test runs + code inspection + browser subagent logs |
| **Leak Prevention** | Verification of zero hostname/credentials/internal exception leaks in client errors |
| **Status** | ✅ **PASSED** |

## 2. Localized Error Scenarios Audit

| Scenario | Trigger Mechanism | Expected Localized Key | Observed Value (Arabic) | Leak Verification |
| --- | --- | --- | --- | --- |
| **Invalid Sign-in Credentials** | Submit incorrect username/password | `auth.signIn.error.invalidCredentials` | `اسم المستخدم أو كلمة المرور غير صحيحة` | ✅ Clean (no password hash) |
| **Empty Sign-in Form** | Submit sign-in form with empty username | `auth.signIn.error.usernameEmpty` | `اسم المستخدم لا يمكن أن يكون فارغاً.` | ✅ Clean |
| **Connection Auth Failed** | Test database connection with invalid username/password | `error.connection_auth_failed` | `فشلت المصادقة. تحقق من اسم المستخدم وكلمة المرور.` | ✅ Clean (no user leaks) |
| **Unreachable DB Host** | Test database connection with invalid host | `error.connection_network_unreachable` | `الشبكة غير قابلة للوصول. تحقق من المضيف والمنفذ.` | ✅ Clean (no socket dump) |
| **Database Not Found** | Test database connection with invalid DB name | `error.connection_db_not_found` | `قاعدة البيانات غير موجودة` | ✅ Clean (no database catalog dump) |
| **Schema Introspection Failed** | Trigger schema refresh on misconfigured DB | `error.introspection_failed` | `فشل فحص المخطط` | ✅ Clean |
| **Query Execution Failed** | Submit invalid query text to database | `error.queryExecutionFailed.title`<br>`error.queryExecutionFailed.body` | **Title:** `فشل الاستعلام`<br>**Body:** `تعذر تنفيذ الاستعلام. حاول إعادة صياغة سؤالك أو اختيار اتصال مختلف.` | ✅ Clean (no raw SQL exception trace) |
| **Disabled Connection Query** | Submit query targeting disabled database connection | `error.disabled.title`<br>`error.disabled.body` | **Title:** `الاتصال معطل`<br>**Body:** `هذا الاتصال معطل. اختر اتصالاً آخر أو اتصل بالمسؤول.` | ✅ Clean |
| **Unhealthy Connection Query** | Submit query targeting unreachable connection | `error.unhealthy.title`<br>`error.unhealthy.body` | **Title:** `الاتصال غير متاح`<br>**Body:** `الاتصال المحدد لا يستجيب. جرب اتصالاً آخر أو اتصل بالمسؤول.` | ✅ Clean |
| **Connection Lacks Schema** | Submit query targeting connection with empty schema | `error.noSchema.title`<br>`error.noSchema.body` | **Title:** `المخطط غير جاهز`<br>**Body:** `لم يتم تحميل مخطط الاتصال بعد. اتصل بالمسؤول لتحديث المخطط.` | ✅ Clean |
| **No Database Connections** | Load workspace with empty database list | `error.noConnections.title`<br>`error.noConnections.body` | **Title:** `لا توجد اتصالات قواعد بيانات متاحة`<br>**Body:** `يرجى إضافة اتصال قاعدة بيانات للبدء في الاستعلام.` | ✅ Clean |
| **General Unknown Error** | Force HTTP 500 server-side exception | `error.unknown.title`<br>`error.unknown.message` | **Title:** `خطأ`<br>**Body:** `حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.` | ✅ Clean (no traceback leaks) |

## 3. Security & Safety Verification
- **Zero raw backend exception traces:** Checked all error components (e.g. `ConnectionErrorCard`, `EvaluatorRejectionBanner`, global alerts) to confirm they map server error response codes (e.g. `connection_disabled`, `query_execution_failed`) using static locale lookups. No raw FastAPI or SQLAlchemy stack traces are rendered on the UI.
- **Zero credential leaks:** Connection test errors do not output the username, host, or password configuration in toast messages.
- **Zero raw key leaks:** All error scenarios correctly map to localized strings in `ar.json` and `en.json`.

## 4. Console & Network Logs
- **Console Errors:** Expected REST API validation errors (HTTP 400/422/500 depending on trigger scenario) are caught by React Query and translated cleanly. No uncaught JavaScript exceptions.
