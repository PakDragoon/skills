#!/usr/bin/env bash
# repo-inventory.sh: print a markdown inventory of the current git repository.
# Usage: bash repo-inventory.sh [repo-root]
# Only lists tracked files (respects .gitignore). Prints env var NAMES, never values.
set -uo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "${ROOT}" ] || ! git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "error: not inside a git repository" >&2
  exit 1
fi
cd "$ROOT" || exit 1

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FILES="$TMP/files"
git -c core.quotepath=off ls-files -z | tr '\0' '\n' > "$FILES"

# Files we never treat as source.
NOISE='(^|/)(node_modules|vendor|dist|build|out|\.next|coverage|__snapshots__|\.yarn)/|\.min\.(js|css)$|(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|composer\.lock|Gemfile\.lock|poetry\.lock|Cargo\.lock|go\.sum)$'
grep -Ev "$NOISE" "$FILES" > "$TMP/src" || true
# Same exclusions as git pathspecs, for git grep.
EXCL=(':(exclude,glob)**/node_modules/**' ':(exclude,glob)**/vendor/**' ':(exclude,glob)**/dist/**'
      ':(exclude,glob)**/build/**' ':(exclude,glob)**/*.min.js' ':(exclude,glob)**/*.lock'
      ':(exclude,glob)**/package-lock.json' ':(exclude,glob)**/pnpm-lock.yaml' ':(exclude,glob)**/go.sum')

section() { printf '\n## %s\n\n' "$1"; }
list_matches() { # $1 = ERE, $2 = max lines
  local out
  out="$(grep -Ei "$1" "$FILES" | head -n "${2:-50}")"
  if [ -n "$out" ]; then printf '%s\n' "$out" | sed 's/^/- `/; s/$/`/'; else echo "_none found_"; fi
}

echo "# Repository inventory"
echo
echo "- Root: \`$ROOT\`"
echo "- HEAD: \`$(git rev-parse --short HEAD 2>/dev/null || echo none)\` on \`$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo detached)\`"
echo "- Tracked files: $(wc -l < "$FILES" | tr -d ' ') (source-like, excluding noise: $(wc -l < "$TMP/src" | tr -d ' '))"
echo "- Shallow clone: $(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)"

section "Languages (by file extension, top 15)"
awk -F/ '{f=$NF; if (index(f,".")==0) next; if (substr(f,1,1)=="." && gsub(/\./,".",f)==1) next; n=split(f,p,"."); e=tolower(p[n]); c[e]++}
  END {for (e in c) printf "%d\t%s\n", c[e], e}' "$TMP/src" | sort -rn | head -15 |
  awk -F'\t' '{printf "- .%s: %d files\n", $2, $1}'

section "Top-level layout"
awk -F/ '{ if (NF==1) k="(root files)"; else k=$1"/"; c[k]++ }
  END {for (k in c) printf "%d\t%s\n", c[k], k}' "$TMP/src" | sort -rn | head -30 |
  awk -F'\t' '{printf "- `%s` %d files\n", $2, $1}'

section "Second-level layout for common source roots"
awk -F/ '$1 ~ /^(src|apps|packages|libs|services|modules|lib|app|internal|cmd|pkg)$/ && NF>2 {c[$1"/"$2"/"]++}
  END {for (k in c) printf "%d\t%s\n", c[k], k}' "$TMP/src" | sort -rn | head -40 |
  awk -F'\t' '{printf "- `%s` %d files\n", $2, $1}'

section "Build manifests and workspace config"
list_matches '(^|/)(package\.json|pnpm-workspace\.yaml|lerna\.json|nx\.json|turbo\.json|go\.mod|Cargo\.toml|pyproject\.toml|requirements[^/]*\.txt|setup\.py|Pipfile|Gemfile|composer\.json|pom\.xml|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|[^/]+\.csproj|[^/]+\.sln|mix\.exs|Makefile|justfile|Taskfile\.ya?ml)$' 60

section "Agent / AI instruction files (CLAUDE.md, AGENTS.md, ...)"
list_matches '(^|/)(CLAUDE\.md|CLAUDE\.local\.md|AGENTS\.md|GEMINI\.md|\.cursorrules|copilot-instructions\.md)$|(^|/)\.claude/|(^|/)\.cursor/rules/' 80

section "Documentation"
list_matches '(^|/)(README|CONTRIBUTING|CHANGELOG|ARCHITECTURE|RUNBOOK|HANDOVER)[^/]*$|(^|/)(docs?|documentation|adr|adrs|decisions)/.*\.(md|mdx|rst|txt|adoc|pdf)$' 80

section "Entry point candidates"
list_matches '(^|/)(main|index|app|server|bootstrap|program|startup|wsgi|asgi|manage)\.(ts|tsx|js|mjs|cjs|py|go|rs|java|kt|cs|rb|php)$|(^|/)cmd/[^/]+/main\.go$|(^|/)Program\.cs$' 40

section "Tests"
grep -Ei '(^|/)(tests?|__tests__|spec|specs|e2e|integration)/|\.(test|spec)\.[a-z]+$|_test\.(go|py)$|(^|/)test_[^/]+\.py$' "$TMP/src" > "$TMP/tests" || true
echo "- Test files: $(wc -l < "$TMP/tests" | tr -d ' ')"
awk -F/ '{ if (NF==1) k="(root)"; else k=$1"/"; c[k]++ } END {for (k in c) printf "  - `%s` %d\n", k, c[k]}' "$TMP/tests" | sort | head -20
SKIPPED="$(git grep -nE '(^|[^A-Za-z_.])(it|test|describe)\.skip\(|(^|[^A-Za-z_.])(xit|xdescribe|xtest)\(|@Disabled|@pytest\.mark\.skip|@unittest\.skip|t\.Skip\(' -- . "${EXCL[@]}" 2>/dev/null | wc -l | tr -d ' ')"
echo "- Skipped/disabled test markers: ${SKIPPED:-0}"

section "Schema, models and migrations"
list_matches '(^|/)migrations?/|(^|/)(schema\.prisma|schema\.graphql|[^/]*\.sql|alembic\.ini|ormconfig\.[a-z]+|knexfile\.[a-z]+|typeorm[^/]*|drizzle\.config\.[a-z]+|db/schema\.rb|structure\.sql)$|(^|/)(models|entities|entity|schemas)/' 60
MIG_COUNT="$(grep -Ec '(^|/)migrations?/' "$FILES" || true)"
echo
echo "- Migration files total: ${MIG_COUNT:-0}"

section "CI/CD"
list_matches '(^|/)\.github/workflows/|(^|/)(\.gitlab-ci\.yml|bitbucket-pipelines\.yml|Jenkinsfile|azure-pipelines\.yml|\.travis\.yml|buildspec\.ya?ml|cloudbuild\.ya?ml|appspec\.ya?ml|vercel\.json|netlify\.toml|fly\.toml|render\.yaml|Procfile)$|(^|/)\.circleci/' 40

section "Containers and infrastructure as code"
list_matches '(^|/)(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|compose\.ya?ml|serverless\.ya?ml|cdk\.json|template\.ya?ml|samconfig\.toml|Chart\.yaml|skaffold\.yaml|kustomization\.yaml)$|\.tf$|(^|/)(k8s|kubernetes|helm|terraform|infra|infrastructure|deploy|deployment|ops)/' 60

section "Environment variables (names from example files only)"
ENVF="$(grep -Ei '(^|/)\.env\.(example|sample|template|dist|defaults)$|(^|/)env\.example$|(^|/)example\.env$' "$FILES" || true)"
if [ -z "$ENVF" ]; then
  echo "_no env example files tracked_"
else
  while IFS= read -r f; do
    echo "- \`$f\`:"
    grep -Eo '^[[:space:]]*(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*=' "$f" 2>/dev/null |
      sed -E 's/^[[:space:]]*(export[[:space:]]+)?//; s/=$//' | sort -u | tr '\n' ' ' | sed 's/^/  /'
    echo
  done <<< "$ENVF"
fi
CODE_ENV="$(git grep -hoE 'process\.env\.[A-Z_][A-Z0-9_]*|os\.environ(\.get)?\(?\[?["'"'"'][A-Z_][A-Z0-9_]*|os\.Getenv\("[A-Z_][A-Z0-9_]*|ENV\[["'"'"'][A-Z_][A-Z0-9_]*|getenv\(["'"'"'][A-Z_][A-Z0-9_]*' -- . "${EXCL[@]}" 2>/dev/null |
  grep -oE '[A-Z_][A-Z0-9_]{2,}$' | sort | uniq -c | sort -rn | head -60 | awk '{printf "%s ", $2}')"
echo "- Referenced in code (top 60): ${CODE_ENV:-none detected}"

section "Package scripts (root package.json)"
if [ -f package.json ] && command -v python3 >/dev/null 2>&1; then
  python3 -I -c 'import json,sys
d=json.load(open("package.json"))
s=d.get("scripts",{})
print("\n".join(f"- `{k}`: `{v}`" for k,v in s.items()) or "_no scripts_")
deps=list(d.get("dependencies",{}).keys())
print(f"\n- dependencies ({len(deps)}): " + ", ".join(deps[:40]))' 2>/dev/null || echo "_could not parse package.json_"
else
  echo "_no root package.json_"
fi

section "Code annotations (TODO / FIXME / HACK / XXX) by area"
git grep -IcwE 'TODO|FIXME|HACK|XXX' -- . "${EXCL[@]}" 2>/dev/null |
  awk -F: '{split($1,p,"/"); k=(index($1,"/")?p[1]"/":"(root)"); c[k]+=$NF; t+=$NF}
    END {printf "- Total: %d\n", t; for (k in c) printf "  - `%s` %d\n", k, c[k]}' | head -25

section "Likely generated or vendored paths (skip when reading)"
grep -E '(^|/)(vendor|third_party|generated|__generated__|gen|dist|build)/|\.generated\.|\.pb\.go$|_pb2\.py$' "$FILES" |
  awk -F/ '{print $1"/"($2?$2"/":"")}' | sort | uniq -c | sort -rn | head -15 | awk '{printf "- `%s` %d files\n", $2, $1}'
echo
