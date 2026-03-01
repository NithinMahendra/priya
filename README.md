# AI Code Reviewer Web App

Production-grade AI-powered code review platform with:

- Multi-language static analysis (Python, JavaScript/TypeScript, Java heuristics)
- Security scanning with SSRF, SQLi, deserialization, command execution checks
- Dependency vulnerability checks (`requirements.txt` / `package.json`)
- Pluggable AI semantic review (OpenAI or mock fallback)
- Context-aware AI review (optional README/project structure context)
- Severity scoring and quality score
- Persisted submissions and dashboard analytics
- Persisted review actions (accept/ignore issue/fix)
- JWT auth and rate limiting

## Architecture

### Backend (FastAPI)

- `app/api`: route handlers (`auth`, `reviews`, `dashboard`, `integrations`, `health`)
- `app/services`:
  - `static_analyzer.py`
  - `security_scanner.py`
  - `dependency_scanner.py`
  - `project_context.py`
  - `ai_reviewer.py`
  - `llm_provider.py` (`LLMProvider`, `OpenAIProvider`, `MockProvider`)
  - `review_service.py` orchestration layer
- `app/models`: SQLAlchemy models (`User`, `Submission`, `ReviewAction`)
- `app/schemas`: Pydantic contracts
- `app/middleware/rate_limit.py`: in-memory request throttling

### Frontend (React + Vite + Tailwind + Monaco)

- Monaco editor and file upload
- Review panel with severity badges, score, diff view, apply/ignore fix actions
- Inline Monaco annotations for detected lines
- Keyboard shortcuts (`Ctrl/Cmd+Enter` run, `Esc` clear)
- Dark/light theme toggle (dark default)
- Dashboard with issue distribution and score trend (Recharts)
- JWT login/register workflow

### Data Storage

- SQLite by default for development
- PostgreSQL support via `DATABASE_URL`

## LLM Provider Behavior

Environment-driven provider selection:

- `LLM_PROVIDER=openai` and `OPENAI_API_KEY` set: use `OpenAIProvider`
- Missing key or invalid provider: automatic fallback to `MockProvider`

The rest of the system only calls `LLMProvider` abstraction.

## API Response Shape

Review endpoint returns structured JSON:

```json
{
  "issues": [
    {
      "line": 23,
      "type": "Security",
      "severity": "High",
      "message": "Possible SQL injection vulnerability.",
      "suggested_fix": "Use parameterized queries.",
      "source": "security"
    }
  ],
  "summary": {
    "critical": 1,
    "high": 2,
    "medium": 1,
    "low": 0,
    "score": 82
  },
  "technical_debt": "Moderate",
  "overall_assessment": "Code needs refactoring for maintainability.",
  "refactor_suggestions": [
    {
      "before": "query = \"SELECT * FROM users WHERE id = \" + user_input",
      "after": "cursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_input,))",
      "reason": "Use parameterized SQL to avoid injection."
    }
  ],
  "provider": "mock",
  "submission_id": 1,
  "created_at": "2026-03-01T08:10:00.000000+00:00"
}
```

## Local Setup

### 1. Configure environment

```bash
cp .env.example .env
```

### 2. Run backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 3. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## Docker Setup

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## API Endpoints

- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/token`
- `POST /api/v1/reviews/run` (auth)
- `GET /api/v1/reviews`
- `GET /api/v1/reviews/{submission_id}`
- `GET /api/v1/reviews/{submission_id}/actions`
- `POST /api/v1/reviews/{submission_id}/actions`
- `GET /api/v1/dashboard/metrics`
- `POST /api/v1/integrations/github/mock-pr`

Detailed endpoint reference: [`backend/API.md`](backend/API.md)

## Sample Test Request

1. Register:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"demo_user\",\"password\":\"StrongPass123\"}"
```

2. Login and capture token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo_user&password=StrongPass123"
```

3. Run review:

```bash
curl -X POST http://localhost:8000/api/v1/reviews/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d "{\"language\":\"python\",\"filename\":\"demo.py\",\"code\":\"query = 'SELECT * FROM users WHERE id=' + user_input\\nprint(eval(user_input))\"}"
```

## Tests

```bash
cd backend
pytest
```
