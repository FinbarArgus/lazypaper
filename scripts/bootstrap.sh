#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN=0
SKIP_TEST=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap.sh [--dry-run] [--skip-test]

Bootstraps a lazypaper fork by:
  1. validating config.py
  2. syncing .github/workflows/daily_email.yml cron from config.py
  3. setting required GitHub Actions secrets in the current repo via gh CLI
  4. committing/pushing config and workflow updates
  5. optionally triggering the test email workflow

Environment variables consumed if already set:
  RESEND_API_KEY   Required GitHub Actions secret value
  RESEND_FROM      Optional GitHub Actions secret value
  LAZYPAPER_TO     Optional GitHub Actions secret value

Flags:
  --dry-run        Show what would happen without mutating GitHub or git state
  --skip-test      Skip triggering the test workflow at the end
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --skip-test)
      SKIP_TEST=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: Missing required command: $1" >&2
    exit 1
  fi
}

prompt_secret() {
  local name="$1"
  local prompt_text="$2"
  local default_value="${!name-}"
  if [[ -n "$default_value" ]]; then
    printf '%s' "$default_value"
    return 0
  fi

  local value=""
  read -r -s -p "$prompt_text: " value
  echo >&2
  printf '%s' "$value"
}

prompt_optional() {
  local name="$1"
  local prompt_text="$2"
  local default_value="${!name-}"
  if [[ -n "$default_value" ]]; then
    printf '%s' "$default_value"
    return 0
  fi

  local value=""
  read -r -p "$prompt_text (press Enter to skip): " value
  printf '%s' "$value"
}

set_secret() {
  local repo="$1"
  local name="$2"
  local value="$3"
  if [[ -z "$value" ]]; then
    echo "Skipping optional secret $name"
    return 0
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] gh secret set $name --repo $repo --body-file -"
    return 0
  fi
  printf '%s' "$value" | gh secret set "$name" --repo "$repo" --body-file -
}

PYTHON_BIN="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "ERROR: Python is required to run bootstrap helpers" >&2
  exit 1
fi

require_command git
require_command gh

if [[ ! -d .git ]]; then
  echo "ERROR: bootstrap must be run from a git checkout" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated. Run 'gh auth login' first." >&2
  exit 1
fi

"$PYTHON_BIN" scripts/validate_bootstrap.py

repo_json="$(gh repo view --json nameWithOwner,viewerPermission 2>/dev/null || true)"
if [[ -z "$repo_json" ]]; then
  echo "ERROR: Could not resolve a GitHub repository for this checkout. Run bootstrap from your fork." >&2
  exit 1
fi

repo_name="$(printf '%s' "$repo_json" | "$PYTHON_BIN" -c 'import json,sys; data=json.load(sys.stdin); print(data["nameWithOwner"])')"
viewer_permission="$(printf '%s' "$repo_json" | "$PYTHON_BIN" -c 'import json,sys; data=json.load(sys.stdin); print(data.get("viewerPermission", ""))')"

case "$viewer_permission" in
  ADMIN|MAINTAIN|WRITE)
    ;;
  *)
    echo "ERROR: Current GitHub repo is not writable with this account (permission: $viewer_permission). Run bootstrap from your fork." >&2
    exit 1
    ;;
esac

echo "Using repo: $repo_name"
"$PYTHON_BIN" scripts/sync_workflow_cron.py

RESEND_API_KEY_VALUE="$(prompt_secret RESEND_API_KEY "Enter RESEND_API_KEY")"
if [[ -z "$RESEND_API_KEY_VALUE" ]]; then
  echo "ERROR: RESEND_API_KEY is required" >&2
  exit 1
fi

RESEND_FROM_VALUE="$(prompt_optional RESEND_FROM "Enter RESEND_FROM")"
LAZYPAPER_TO_VALUE="$(prompt_optional LAZYPAPER_TO "Enter LAZYPAPER_TO override")"

echo "Running local domain/feed validation"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] RESEND_FROM=*** LAZYPAPER_TO=*** $PYTHON_BIN scripts/check_domains.py"
else
  RESEND_FROM="$RESEND_FROM_VALUE" LAZYPAPER_TO="$LAZYPAPER_TO_VALUE" "$PYTHON_BIN" scripts/check_domains.py
fi

set_secret "$repo_name" RESEND_API_KEY "$RESEND_API_KEY_VALUE"
set_secret "$repo_name" RESEND_FROM "$RESEND_FROM_VALUE"
set_secret "$repo_name" LAZYPAPER_TO "$LAZYPAPER_TO_VALUE"

if ! git config user.name >/dev/null; then
  echo "ERROR: git user.name is not configured; set it before bootstrap commits workflow/config changes." >&2
  exit 1
fi
if ! git config user.email >/dev/null; then
  echo "ERROR: git user.email is not configured; set it before bootstrap commits workflow/config changes." >&2
  exit 1
fi

run_cmd git add config.py .github/workflows/daily_email.yml
if git diff --cached --quiet; then
  echo "No config or workflow changes to commit"
else
  run_cmd git commit -m "Bootstrap lazypaper setup"
  run_cmd git push
fi

if [[ "$SKIP_TEST" -eq 0 ]]; then
  run_cmd gh workflow run test_paper_email.yml --repo "$repo_name"
  echo "Triggered test_paper_email.yml in $repo_name"
fi

echo "Bootstrap complete."