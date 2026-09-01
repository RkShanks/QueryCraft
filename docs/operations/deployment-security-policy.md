# Deployment security and API documentation policy

The production-facing Nginx proxy is the sole owner of deployment security headers. The FastAPI backend owns endpoint-specific API cache policy. Operators must not add the deployment headers to FastAPI middleware or replace backend `Cache-Control` values at another proxy layer.

The executable proxy source of truth is `frontend/nginx.conf`; `frontend/Dockerfile` installs it as `/etc/nginx/conf.d/default.conf` in the runtime image.

## Header ownership

Nginx emits each deployment security header once at server scope with the `always` parameter, including on Nginx-generated and proxied error responses.

| Header | Deployed value |
| --- | --- |
| `Content-Security-Policy` | `default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), geolocation=(), microphone=(), payment=(), usb=()` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |

The proxy passes redirects, `Set-Cookie`, downloads, and API response headers through without redefining them. HSTS takes effect only when the public response is delivered over HTTPS, so the Nginx service must remain behind the deployment's TLS endpoint.

## Cache ownership

The proxy adds `Cache-Control` only for the web application:

- HTML and SPA fallback responses use `no-store`.
- Fingerprinted files under `/assets/` use `public, max-age=31536000, immutable`.
- Missing asset responses are HTML errors and use `no-store`.

For `/api/v1/`, the proxy neither hides nor ignores upstream cache headers. FastAPI endpoint contracts therefore remain authoritative. Sensitive connection and audit-download responses continue to pass through as one `Cache-Control: no-store` value, and download `Content-Disposition` remains unchanged.

## API documentation exposure

`API_DOCUMENTATION_ENABLED` is a validated boolean backend setting with a secure default of `false`.

- Production sets `API_DOCUMENTATION_ENABLED=false`. FastAPI does not register `/docs`, `/redoc`, `/docs/oauth2-redirect`, or `/openapi.json`, and Nginx returns `404` for those public paths instead of serving the SPA fallback.
- `.env.example` explicitly sets `API_DOCUMENTATION_ENABLED=true` for development. Interactive documentation is then available directly from the backend port. The production-facing Nginx paths remain disabled.

HTTP route exposure does not control schema generation. `create_app().openapi()` remains available in-process, `backend/scripts/generate_openapi.py` remains the canonical generator, and the checked-in `backend/openapi.json` remains the Schemathesis and generated-client input. The runtime, canonical, and generated application contracts each contain 65 operations.

Verify the policy after a deployment change:

```bash
cd backend
uv run python scripts/generate_openapi.py --check
uv run pytest tests/unit/test_api_documentation_policy.py tests/unit/test_openapi_canonical.py tests/unit/test_deployment_proxy_policy.py -q
```

From the repository root, validate Compose and Nginx syntax:

```bash
docker compose -f docker-compose.dev.yml config
docker run --rm --add-host backend:127.0.0.1 \
  -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:alpine nginx -t
```
