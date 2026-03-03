# Backend API Documentation

Base URL: `http://localhost:8000/api/v1`

Swagger UI: `GET /docs`
OpenAPI JSON: `GET /openapi.json`

## Health

- `GET /health`
- `GET /health/provider`

Response:

```json
{ "status": "ok" }
```

`/health/provider` response:

```json
{
  "provider": "openrouter",
  "effective_provider": "openrouter",
  "model_mode": "auto",
  "free_only": true,
  "api_base_host": "openrouter.ai",
  "mock_fallback_allowed": false
}
```

## Auth

- `POST /auth/register`
- `POST /auth/token`

`/auth/register` body:

```json
{
  "username": "demo_user",
  "password": "StrongPass123"
}
```

`/auth/token` form fields:

- `username`
- `password`

## Reviews

- `POST /reviews/run` (Bearer token required)
- `GET /reviews` (Bearer token required)
- `GET /reviews/{submission_id}` (Bearer token required)
- `GET /reviews/{submission_id}/actions` (Bearer token required)
- `POST /reviews/{submission_id}/actions` (Bearer token required)

`/reviews/run` body:

```json
{
  "filename": "demo.py",
  "language": "python",
  "code": "query = 'SELECT * FROM users WHERE id=' + user_input",
  "include_project_context": true,
  "context_text": "This module handles user identity lookup.",
  "dependency_manifest": "django==3.2.0",
  "manifest_type": "requirements"
}
```

`/reviews/{submission_id}/actions` body:

```json
{
  "action_type": "accept_fix",
  "item_key": "query:1:sql-injection:0",
  "payload": {
    "before": "query = \"SELECT * FROM users WHERE id = \" + user_id",
    "after": "cursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_id,))"
  }
}
```

## Dashboard

- `GET /dashboard/metrics` (Bearer token required)

Returns issue distribution and score trend for the authenticated user.

## Integrations (Mock)

- `POST /integrations/github/mock-pr` (Bearer token required)

Body:

```json
{
  "repo": "org/repo",
  "pr_number": 17,
  "issues": [
    {
      "line": 23,
      "severity": "High",
      "message": "Possible SQL injection vulnerability.",
      "suggested_fix": "Use parameterized queries."
    }
  ]
}
```
