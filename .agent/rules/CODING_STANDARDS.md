# Healthcare Appointment Slot Optimizer — Coding Standards

> Part 1 of 5. Also loaded: `CODING_STANDARDS_TESTING.md`, `CODING_STANDARDS_TESTING_LIVE.md`, `CODING_STANDARDS_DOMAIN.md`, `CODING_STANDARDS_AI.md`

These rules are ALWAYS ACTIVE. Follow them on every response without being asked.

## Workflow Pipeline Awareness
- After completing ANY workflow, **read `.agent/workflows/PIPELINE.md`** and suggest the NEXT logical workflow based on the current context.
- **PIPELINE.md is the single source of truth** for "what comes next." Individual workflows do NOT hardcode their next step — they defer to PIPELINE.md.
- Never leave the user guessing what to do next. Always end with a clear next step.
- **When creating a NEW workflow file**, ALWAYS add it to `PIPELINE.md` with its "When Done, Suggest" message.
- **When deleting a workflow file**, ALWAYS remove it from `PIPELINE.md`.
- `PIPELINE.md` must ALWAYS match the actual files in `.agent/workflows/`. If they're out of sync, fix `PIPELINE.md` immediately.

## Workflow Approval Gates (CRITICAL — Prevents Plan Mode Errors)
When a workflow step says "present to user", "wait for approval", or "approve before proceeding":
1. Present the content directly as **formatted text in the conversation**.
2. End with a clear question: `Approve? [yes / no / edit]`
3. Wait for the user's response before proceeding to the next step.
4. **NEVER call `ExitPlanMode` or `EnterPlanMode`** during workflow execution. These are Claude Code built-in tools for a separate system (toggled via `Shift+Tab`). Workflow approval gates are handled through direct conversation.
5. **NEVER write to `.claude/plans/`** during workflow execution — that directory is reserved for Claude Code's built-in plan mode.

This applies to ALL approval gates: batch selection, implementation plans, RED/GREEN/REGRESSION evidence, commit approval, refactor plans, and any other "present and wait" step in any workflow.

## Domain-Specific Rules

If your task touches any of the domains below, **also read the corresponding rules file before starting**. These files contain deeper conventions than fit here.

| When working on... | Also read |
|--------------------|-----------|
| Authentication / sessions / permissions | `.agent/rules/auth_rules.md` (if exists) |
| Database / migrations / queries | `.agent/rules/db_rules.md` (if exists) |
| Background jobs / queues / scheduling | `.agent/rules/jobs_rules.md` (if exists) |
| API endpoints / serializers / validation | `.agent/rules/api_rules.md` (if exists) |

> These files are created by `/bootstrap` when a domain has 5+ concentrated conventions. If a file doesn't exist for a domain, the relevant rules are here in CODING_STANDARDS.md.

## Git Commit Convention

**Format:** `type(scope): descriptive message`

| Type | When to use |
|------|------------|
| `feat` | New feature or functionality |
| `fix` | Bug fix |
| `refactor` | Code restructuring without behavior change |
| `test` | Adding or updating tests |
| `docs` | Documentation changes |
| `chore` | Tooling, workflows, config, dependencies |
| `style` | Formatting, whitespace, no logic change |

**Scope** = the module or area affected. Valid scopes for this project:
- `optimizer` — slot computation, scoring, constraints
- `booking` — booking service, cancellation, backfill
- `api` — routes, endpoints, middleware
- `db` — models, migrations, session, seed data
- `config` — settings, environment, config loader
- `auth` — API key middleware
- `lib` — shared utilities (time_utils, logger)
- `integrations` — notification hub, external service clients
- `jobs` — background jobs (no-show marker, stats calculator)
- `deploy` — Dockerfile, docker-compose, CI/CD
- `workflows` — `.agent/workflows/` changes

**Rules:**
- Subject line max 72 characters.
- Use imperative mood: "add filter" not "added filter".
- Reference the `[BUG]`/`[FIX]`/`[FEATURE]` from `progress.md` when applicable.
- One commit per completed item. Don't bundle unrelated changes.

**Examples:**
```
feat(db): implement Provider and Room models with UUID PKs
feat(optimizer): add availability window calculator
feat(booking): implement idempotent booking with request_id
fix(api): handle concurrent booking conflict with 409 response
refactor(optimizer): extract buffer time logic to constraints module
test(booking): add 8 tests for cancellation backfill candidates
docs(context): update CODEBASE_CONTEXT.md with new schema tables
chore(deploy): customize Dockerfile for Python/FastAPI
```

## Architecture — Dependency Hierarchy (PRD Section 9)

```
lib/          → nothing (leaf modules)
db/           → lib/
optimizer/    → lib/, db/
booking/      → lib/, db/
integrations/ → nothing (leaf — HTTP client only)
jobs/         → db/, lib/, optimizer/, integrations/, booking/
api/          → optimizer/, booking/, integrations/, db/, lib/
main.py       → api/, db/, integrations/, jobs/, lib/, config
```

**Rules:**
- Lower layers NEVER import from higher layers.
- `lib/` and `db/` must NOT import from `optimizer/`, `booking/`, `integrations/`, `jobs/`, or `api/`.
- `optimizer/` and `booking/` must NOT import from `api/` or `jobs/`.
- `integrations/` must NOT import from any other `src/` module.
- All cross-module access goes through function parameters, not direct imports up the chain.

## File Size Limits
- **Max 300 lines** per source file. If approaching 250, plan to split.
- **Max 50 lines** per function/method.
- **Max 200 lines** per class.

## PowerShell Environment
- **ALWAYS activate the virtual environment before ANY `python` or `pip` command:**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **NEVER run `pip install` without the venv active.** This installs to system Python and breaks other projects.
- Verify venv is active: prompt shows `(venv)` prefix. If not, activate first.
- Use `;` to chain commands, **NEVER** `&&`
- **NEVER use inline `python -c "..."`** for complex code. Write a `.py` file instead.
- Special characters that break PowerShell: `|`, `>`, `<`, `$`, `()`, `{}`
- Write Python scripts to files instead of inline commands.

## Git Branching Strategy

### Two-Branch Model
- **`main`** — Production only. Code merges here when ready to deploy.
- **`dev`** — Active development. All work happens here.
- `/implement-next` always runs on `dev`.
- Tests always run against local dev services on `dev` branch.
- Merge `dev` → `main` only when all tests pass and feature is complete.
- After merge, run migrations against production.
