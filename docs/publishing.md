# Publishing to GitHub

## Repository

- Intended repository: `Erens_Data` (GitHub repository names cannot contain apostrophes, so
  `Eren's_Data` is written as `Erens_Data`).
- Visibility: **private**. The working tree includes candidate artifacts, seed-derived material,
  and `internal_only` tasks; these must not be published publicly.
- GitHub CLI: `gh` is installed at `~/.local/bin/gh` (or install with
  `sudo apt install gh`). Authenticate interactively:

  ```bash
  gh auth login --hostname github.com --git-protocol https --web
  gh auth status
  ```

## What is committed

The private repository includes the working tree:

```
AGENTS.md, CLAUDE.md -> AGENTS.md
README.md
docs/
skills/
scripts/
templates/
profiles/
state/
candidates/
docker/
schemas/
```

Excluded by `.gitignore` and policy:

- `exports/` (generated reference/verify artifacts),
- `candidates/*/base/output/` (solver outputs),
- `candidates/*/verify/independent_solver/` (local solves),
- `~/ale-blind/` (blind workspaces and scores),
- `.env*`, `.credentials.yaml`, `settings.local.json`, keys, tokens,
- the external seed root (never inside the repo).

## Before the first push

```bash
cd ~/ale-task-factory
git status --short
git diff --cached --stat

# No secrets or external seed data
git ls-files | grep -Ei 'credentials|\.env|\.pem$|\.key$|ale-blind|exports/' || true
git grep -nE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|BEGIN .*PRIVATE KEY' || true

# No accidental absolute home paths in published docs (private repo only; still avoid)
git grep -nE '/home/[A-Za-z0-9._-]+' -- '*.md' '*.py' '*.sh' || true

# Confirm internal-only material is expected in this private repo
git grep -n 'internal_only' -- candidates profiles || true
```

If the repository is ever made public, do **not** publish the current working tree. Create a
code-only sanitized mirror containing only `README.md`, `AGENTS.md`, `docs/`, `skills/`,
`scripts/`, `templates/`, `docker/`, `profiles/quotas.json`, and `.gitignore`. Never publish
`candidates/`, `exports/`, seed data, `profiles/seed_profile.json`, pilot notes, or blind results.

## Create and push

The repo currently has a `.git` directory but no commits and no remote.

```bash
cd ~/ale-task-factory
git branch -M main

# Use the authenticated GitHub identity, or set an explicit local identity:
git config user.name "$(gh api user --jq .login)"
git config user.email "$(gh api user --jq '.id')+$(gh api user --jq .login)@users.noreply.github.com"

git add -A
git status --short
git diff --cached --stat

git commit -m "Add task factory with seed and synthetic blind verification tracks" \
  -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"

gh repo create Erens_Data --private --source=. --remote=origin --push
```

If the repository already exists:

```bash
git remote add origin https://github.com/<owner>/Erens_Data.git
git push -u origin main
```

## After the push

```bash
gh repo view Erens_Data --json name,visibility,url
git ls-remote --heads origin
git status --short
```

Expected: `"visibility":"PRIVATE"`, one `main` head, clean working tree.

## If the user later wants a public repository

1. Create a separate sanitized directory or orphan branch.
2. Copy only the framework files listed above.
3. Rerun the sanitization commands against the staged index.
4. Review every candidate for `redistributable: false` / `internal_only: true`.
5. Keep the working repository private.
