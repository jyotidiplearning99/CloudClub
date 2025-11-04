#!/usr/bin/env bash
# Sync your personal repo into OSU monorepo under apps/ai-resume-parser
# Usage: ./sync_to_osu.sh [branch-name]
# Env overrides:
#   PREFIX=apps/ai-resume-parser
#   RESUME_REMOTE=resume-src
#   RESUME_REMOTE_URL=git@github.com:jyotidiplearning99/CloudClub.git

set -euo pipefail

BRANCH="${1:-ai-parser-updates}"
PREFIX="${PREFIX:-apps/ai-resume-parser}"
RESUME_REMOTE="${RESUME_REMOTE:-resume-src}"
RESUME_REMOTE_URL="${RESUME_REMOTE_URL:-git@github.com:jyotidiplearning99/CloudClub.git}"

#--- helpers ---------------------------------------------------------------
append_gitignore_line() {
  local line="$1"
  grep -qxF "$line" .gitignore 2>/dev/null || echo "$line" >> .gitignore
}

info()  { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
error() { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*" >&2; }

#--- sanity checks ---------------------------------------------------------
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { error "Not inside a git repo"; exit 1; }

# Ensure origin exists (OSU monorepo)
git remote get-url origin >/dev/null 2>&1 || { error "No 'origin' remote found (OSU monorepo)."; exit 1; }

# Ensure resume-src remote exists (your personal repo)
if ! git remote get-url "$RESUME_REMOTE" >/dev/null 2>&1; then
  info "Adding remote $RESUME_REMOTE -> $RESUME_REMOTE_URL"
  git remote add "$RESUME_REMOTE" "$RESUME_REMOTE_URL"
fi

#--- branch & fetch --------------------------------------------------------
info "Fetching origin (OSU) and $RESUME_REMOTE (your repo)..."
git fetch origin --prune
git fetch "$RESUME_REMOTE" --prune

# Create/switch PR branch off origin/main
if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  info "Switching to existing branch: $BRANCH"
  git switch "$BRANCH"
else
  info "Creating branch $BRANCH from origin/main"
  git switch -c "$BRANCH" origin/main
fi

# Ensure the source branch exists
git rev-parse --verify "$RESUME_REMOTE/main" >/dev/null 2>&1 || {
  error "Branch '$RESUME_REMOTE/main' not found. Push your repo first: git push origin main"; exit 1; }

#--- import tree -----------------------------------------------------------
info "Importing $RESUME_REMOTE/main into $PREFIX ..."
git read-tree --prefix="$PREFIX" -u "$RESUME_REMOTE/main"

#--- hygiene ---------------------------------------------------------------
# Rename DockerFile -> Dockerfile if present
if git ls-files -- "$PREFIX/DockerFile" >/dev/null 2>&1; then
  info "Renaming DockerFile -> Dockerfile"
  git mv -f "$PREFIX/DockerFile" "$PREFIX/Dockerfile" || true
fi

# Remove binaries from index if they sneak in
git rm -f --cached "$PREFIX/ngrok" "$PREFIX/"*.tgz 2>/dev/null || true

# Make run.sh executable if present
if [ -f "$PREFIX/run.sh" ]; then
  git update-index --chmod=+x "$PREFIX/run.sh" || true
fi

# Append ignore rules (idempotent)
append_gitignore_line "$PREFIX/.env"
append_gitignore_line "$PREFIX/.env.*"
append_gitignore_line "$PREFIX/*.env"
append_gitignore_line "$PREFIX/__pycache__/"
append_gitignore_line "$PREFIX/.venv/"
append_gitignore_line "$PREFIX/.pytest_cache/"
append_gitignore_line "$PREFIX/*.pyc"
append_gitignore_line "$PREFIX/ngrok*"
append_gitignore_line "$PREFIX/*.tgz"

# Quick (non-blocking) secret pattern check
if git grep -nE '(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{32,})' "$PREFIX" >/dev/null 2>&1; then
  warn "Potential secret-like strings detected under $PREFIX. Review before pushing."
fi

#--- commit & push ---------------------------------------------------------
SRC_SHA="$(git rev-parse --short "$RESUME_REMOTE/main")"
git add -A

if git diff --cached --quiet; then
  info "No changes to commit."
else
  info "Committing sync from $RESUME_REMOTE@$SRC_SHA"
  git commit -m "Sync ai-resume-parser from $RESUME_REMOTE@${SRC_SHA}"
fi

info "Pushing to origin/$BRANCH ..."
git push origin "$BRANCH"

info "Done. Open/refresh PR: $BRANCH -> origin/main"
