---
name: scaffold-service
description: Scaffold a new service under services/ following this repo's monorepo conventions (docs/Doc2_GitHub_Monorepo_Structure.md). Use when the user wants to add a new backend service, microservice, or app under services/.
---

# Scaffold a new service

Every service under `services/<name>/` follows the same shape (see
`docs/Doc2_GitHub_Monorepo_Structure.md` for the full reference tree):

```
services/<name>/
├── Dockerfile
├── README.md
├── <language project file>     # pyproject.toml | *.csproj+.sln | package.json
├── .env.example
├── app/  (or src/)              # source
└── tests/
```

## Steps

1. Ask (if not already obvious from context) which language/framework this service uses — it
   determines the init command below. Don't guess silently if it's ambiguous.
2. Create `services/<name>/` and initialise the project:

   **Python (FastAPI-style service, e.g. ml-backend, llm-copilot):**
   ```bash
   cd services/<name>
   uv init --python 3.11
   uv add fastapi "uvicorn[standard]" pydantic-settings
   uv add --dev pytest pytest-asyncio httpx
   ```

   **.NET (Worker Service or web app, e.g. decision-engine, yarp-gateway):**
   ```bash
   cd services/<name>
   dotnet new worker -n <PascalCaseName>   # or: dotnet new web -n <PascalCaseName>
   ```

   **Node/frontend-style service:**
   ```bash
   cd services/<name>
   pnpm init
   ```

3. Add a `README.md` (one paragraph: what this service does, which Doc1 §2 component it
   implements) and a short `CLAUDE.md` (purpose, tech stack, current status, pointer to the
   relevant Doc3 phase) — follow the pattern already used in `services/ml-backend/CLAUDE.md` or
   similar sibling services.
4. Add a `tests/` directory even if empty to start, matching the sibling services' layout.
5. Do **not** add a `.github/workflows/ci-<name>.yml` yet unless the service already has real,
   buildable code and at least one passing test — an empty CI workflow just produces permanent
   red X's on every push.

## Verification

- The new service builds/imports: `uv run python -c "import app"` (Python) or
  `dotnet build` (.NET) or `pnpm install` (Node) succeeds with no errors.
- `services/<name>/README.md` and `CLAUDE.md` exist and are non-empty.
