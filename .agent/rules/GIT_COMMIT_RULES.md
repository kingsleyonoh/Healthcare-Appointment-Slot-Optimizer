# Git Commit Rules

## NEVER blind-add files

When committing and pushing, **only stage files that `git status` reports as tracked (modified/deleted)**. For untracked files, only `git add` them if you are certain they are not gitignored.

### Mandatory pre-commit checklist

1. Run `git status` first.
2. Read the output. Only stage files that appear under **"Changes not staged for commit"** or **"Untracked files"**.
3. **Never** attempt to `git add` a file that does not appear in `git status` output.
4. If a file you expect to see is missing from `git status`, it is likely gitignored — do NOT force-add it.
5. Use explicit file paths in `git add`, never `git add .` or `git add -A` unless the user explicitly asks for it.

### Gitignored files in this project

The following are gitignored and must NEVER be committed:

- `.env` / `.env.local` — local environment secrets
- `docs/progress.md` — local progress tracker
- `venv/` — Python virtual environment
- `__pycache__/` — Python bytecode cache
- `.pytest_cache/` — pytest cache
