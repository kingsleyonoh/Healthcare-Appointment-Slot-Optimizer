# AI Project Template

> Your reusable Antigravity project setup. Copy this folder into any new project to get production-grade AI-assisted development out of the box.

## The Complete Flow

```
1. Have an idea → write rough PRD in ChatGPT
2. Copy this template into your project
3. Drop raw PRD into docs/
4. Open in Antigravity

5. /refine-prd      ← Discuss PRD in artifacts: add comments, fill gaps, iterate
6. /prepare-prd     ← AI restructures into standard 20-section format
7. /bootstrap       ← AI auto-fills progress.md, coding standards, .env
8. /implement-next  ← AI builds with TDD
9. Repeat until done
```

**You only write the rough PRD. Everything else is automatic.**

## What's Included

```
project-template/
├── .agent/
│   ├── rules/
│   │   ├── CODING_STANDARDS.md          ← Core rules (AI discipline, git, modularity)
│   │   ├── CODING_STANDARDS_TESTING.md  ← Testing rules (TDD, anti-cheat, quality)
│   │   ├── CODING_STANDARDS_DOMAIN.md   ← Project conventions (deploy, security, env)
│   │   └── CODEBASE_CONTEXT.md          ← AI's source of truth for project understanding
│   ├── guides/
│   │   ├── bootstrap-guide.md           ← Full bootstrap instructions (read via view_file)
│   │   └── retrofit-guide.md            ← Full retrofit instructions (read via view_file)
│   └── workflows/
│       ├── refine-prd.md                ← Discuss & iterate on PRD in artifacts
│       ├── prepare-prd.md               ← Restructure PRD into standard format
│       ├── bootstrap.md                 ← Stub → reads guides/bootstrap-guide.md
│       ├── implement-next.md            ← TDD implementation loop
│       ├── resume.md                    ← Context restore for new conversations
│       ├── deep-study.md                ← Codebase analysis before implementation
│       ├── bug-investigator.md          ← Root-cause analysis
│       ├── generate-tests.md            ← Test generation
│       ├── sync-context.md              ← Keep docs in sync with code
│       ├── security-audit.md            ← Security scanning
│       ├── validate-prd.md              ← PRD acceptance testing
│       ├── check-modularity.md          ← Code quality checks
│       ├── finalize-plan.md             ← Pre-execution plan verification
│       ├── status.md                    ← Quick project status check
│       ├── generate-readme.md           ← Generate professional README from code
│       ├── hotfix.md                    ← Emergency production fix
│       ├── audit-progress.md            ← Audit progress.md for missing items and build order
│       ├── setup-ci.md                  ← Generate GitHub Actions CI/CD from codebase
│       └── fix-ci.md                    ← Auto-fix CI failures (pull error, fix, push, monitor)
├── Dockerfile                            ← Multi-stage build template (customized by /bootstrap)
├── docker-compose.prod.yml               ← Traefik reverse proxy config for DigitalOcean VPS
├── .dockerignore                         ← Docker build exclusions
└── docs/
    ├── PRD_TEMPLATE.md                  ← Required PRD structure (20 sections)
    └── progress.md                      ← Implementation tracker template
```

## Setup

```powershell
# 1. Create your project
mkdir my-new-project ; cd my-new-project ; git init

# 2. Copy the template
Copy-Item -Recurse "C:\Users\harri\OneDrive\Documents\SAAS DEV\project-template\.agent" ".\.agent"
Copy-Item -Recurse "C:\Users\harri\OneDrive\Documents\SAAS DEV\project-template\docs" ".\docs"
Copy-Item "C:\Users\harri\OneDrive\Documents\SAAS DEV\project-template\Dockerfile" ".\Dockerfile"
Copy-Item "C:\Users\harri\OneDrive\Documents\SAAS DEV\project-template\docker-compose.prod.yml" ".\docker-compose.prod.yml"
Copy-Item "C:\Users\harri\OneDrive\Documents\SAAS DEV\project-template\.dockerignore" ".\.dockerignore"

# 3. Drop your raw PRD into docs/
# 4. Open in Antigravity
# 5. /refine-prd → /prepare-prd → /bootstrap → /implement-next
```

## Workflows

| Command | When to Use |
|---------|-------------|
| `/refine-prd` | Discuss raw PRD in artifacts, add comments, fill gaps |
| `/prepare-prd` | Restructure refined PRD into standard 20-section format |
| `/bootstrap` | Auto-fill project config from the formatted PRD |
| `/resume` | Start of every new conversation |
| `/status` | Quick velocity check without full context restore |
| `/implement-next` | Build the next feature with TDD |
| `/deep-study` | Before any implementation work |
| `/bug-investigator` | When something breaks |
| `/generate-tests` | Add tests for a specific module |
| `/check-modularity` | Audit code quality |
| `/sync-context` | After major changes, update docs |
| `/validate-prd` | After all progress items done, before CI/CD setup |
| `/setup-ci` | Generate GitHub Actions CI/CD from codebase (after validate-prd) |
| `/fix-ci` | Auto-fix CI failures — pull error, fix, push, monitor until green |
| `/security-audit` | Before deployment |
| `/generate-readme` | Generate a professional README from the codebase |
| `/finalize-plan` | Before executing a complex plan |
| `/hotfix` | Emergency production fix (bypasses normal TDD cycle) |
| `/audit-progress` | Audit progress.md for missing items, vague tasks, and build order |

## PRD Pipeline

```
Raw PRD (from ChatGPT)
    │
    ▼
/refine-prd    ── Artifact discussion ── iterate ── approve
    │
    ▼
/prepare-prd   ── Restructure into 20 sections ── quality check
    │
    ▼
/bootstrap     ── Auto-fill progress.md, standards, .env
    │
    ▼
/implement-next ── TDD: tests first → implement → regression → next
```

See `docs/PRD_TEMPLATE.md` for the required 20-section structure.
