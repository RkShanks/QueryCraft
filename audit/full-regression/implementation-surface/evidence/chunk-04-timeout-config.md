# CHUNK-04 configured query deadline evidence

## Status

| Check | Value |
| --- | --- |
| Overall | Passed |
| Sanitized timeout HTTP status | 504 |
| Sanitized timeout body | Passed |
| Browser required | False |
| Response/UI contract changed | False |
| CHUNK-05 started | False |

## Deadline and lock timing

| Check | Duration / status |
| --- | --- |
| Short configured deadline | 1 second |
| Real HTTP duration | 1.05 seconds |
| Submit timeout duration | 1.01 seconds |
| Regenerate timeout duration | 1.00 seconds |
| Accepted-query rerun timeout duration | 1.00 seconds |
| Controlled long configured deadline | 60 seconds |
| Provider remaining budget after earlier work | 55 seconds |
| Source remaining budget after earlier work | 45 seconds |
| Hidden 30-second cap present | False |
| Invalid zero/negative/non-integer configuration accepted | False |
| Lock example configured deadline | 7 seconds |
| Fixed cleanup grace | 5 seconds |
| Derived lock TTL | 12 seconds |
| Replacement lock owner preserved | True |

## Boundary and outcome status

| Boundary | Status |
| --- | --- |
| Detection expiry | Passed |
| Quota expiry | Passed |
| Provider timeout | Passed |
| Evaluator expiry | Passed |
| Policy expiry | Passed |
| Source timeout | Passed |
| Masking expiry | Passed |
| Persistence expiry | Passed |
| Success-audit expiry | Passed |
| Exactly one timeout audit | True |
| False success audit | False |
| Accepted history/result after timeout | False |
| Timeout attempt state truthful | True |
| Session deletion precedence | Passed |
| Owned lock cleanup | Passed |
| Owned active-attempt cleanup | Passed |
| Owned operation cleanup | Passed |
| Live task/coroutine after cleanup | False |

## Real dialect timing

| Dialect | Timeout duration | Timed out | Immediately reusable |
| --- | ---: | --- | --- |
| PostgreSQL | 0.258 seconds | True | True |
| MySQL | 0.251 seconds | True | True |
| MSSQL | 1.021 seconds | True | True |

## Automated gates

| Gate | Status / count |
| --- | --- |
| Focused timeout/provider/source/cancellation | Passed |
| Full unit | Passed |
| Source-continuity compatibility | Passed |
| Full backend | Passed |
| Ruff check | Passed |
| Ruff format check | Passed |
| Diff check | Passed |
| Test Guard | Passed |
| Clean Code Guard | Passed |
| Docs Guard | Passed |
| Backend CI | Required before merge |
| Frontend CI | Required before merge |

## Cleanup

| Check | Status |
| --- | --- |
| Disposable services removed | Passed |
| Disposable volumes removed | Passed |
| Temporary proof files removed | Passed |
| Browser artifacts retained | False |
| Protected baseline preserved | Passed |
