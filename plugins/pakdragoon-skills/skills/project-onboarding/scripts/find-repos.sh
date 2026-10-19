#!/usr/bin/env bash
# find-repos.sh: decide single-repo vs workspace mode for a directory.
# Usage: bash find-repos.sh [dir] [max-depth]
#   dir        defaults to the current directory
#   max-depth  how deep to look for child repos in workspace mode (default 3)
# First line of output is machine-readable:
#   MODE=single ROOT=<repo root>
#   MODE=workspace ROOT=<dir> REPOS=<n>
#   MODE=none ROOT=<dir>
# Followed by a markdown summary.
set -uo pipefail

DIR="$(cd "${1:-.}" 2>/dev/null && pwd)" || { echo "MODE=none ROOT=${1:-.}"; echo "error: directory not found" >&2; exit 1; }
DEPTH="${2:-3}"

stack_of() { # $1 = repo dir; prints a short stack guess
  local d="$1" s="" deps=""
  if [ -f "$d/package.json" ] && command -v python3 >/dev/null 2>&1; then
    deps="$(python3 -I -c 'import json,sys
d=json.load(open(sys.argv[1]))
print(" ".join(list(d.get("dependencies",{}))+list(d.get("devDependencies",{}))))' "$d/package.json" 2>/dev/null)"
    for pair in "@nestjs/core:NestJS" "next:Next.js" "nuxt:Nuxt" "@angular/core:Angular" "react-native:React Native" \
                "react:React" "vue:Vue" "svelte:Svelte" "express:Express" "fastify:Fastify" "koa:Koa" \
                "@prisma/client:Prisma" "typeorm:TypeORM" "sequelize:Sequelize" "mongoose:Mongoose" "drizzle-orm:Drizzle" \
                "vite:Vite" "typescript:TypeScript"; do
      pkg="${pair%%:*}"; label="${pair#*:}"
      case " $deps " in *" $pkg "*) s="$s${s:+, }$label";; esac
    done
    [ -z "$s" ] && s="Node.js"
  fi
  [ -f "$d/go.mod" ] && s="$s${s:+, }Go"
  [ -f "$d/Cargo.toml" ] && s="$s${s:+, }Rust"
  { [ -f "$d/pyproject.toml" ] || [ -f "$d/requirements.txt" ] || [ -f "$d/manage.py" ]; } && s="$s${s:+, }Python"
  { [ -f "$d/pom.xml" ] || [ -f "$d/build.gradle" ] || [ -f "$d/build.gradle.kts" ]; } && s="$s${s:+, }JVM"
  [ -f "$d/composer.json" ] && s="$s${s:+, }PHP"
  [ -f "$d/Gemfile" ] && s="$s${s:+, }Ruby"
  ls "$d"/*.csproj "$d"/*.sln >/dev/null 2>&1 && s="$s${s:+, }.NET"
  { [ -f "$d/pubspec.yaml" ]; } && s="$s${s:+, }Flutter"
  echo "${s:-unknown}"
}

role_of() { # $1 = stack string, $2 = dir name; guess frontend/backend/mobile/infra/other
  local st="$1" name b=0
  name="$(echo "$2" | tr '[:upper:]' '[:lower:]')"
  case "$name" in
    *infra*|*terraform*|*devops*|*deploy*|*ops) echo "infra"; return;;
  esac
  case "$st" in
    *"React Native"*|*Flutter*) echo "mobile"; return;;
    *NestJS*|*Express*|*Fastify*|*Koa*|*Go*|*Python*|*JVM*|*PHP*|*Ruby*|*.NET*|*Rust*) b=1;;
  esac
  case "$st" in
    *Next.js*|*Nuxt*) echo "fullstack"; return;;
    *React*|*Vue*|*Angular*|*Svelte*) [ "$b" = 1 ] && echo "fullstack" || echo "frontend"; return;;
  esac
  [ "$b" = 1 ] && { echo "backend"; return; }
  case "$name" in
    fe|*front*|*web*|*client*|*ui*|*dashboard*|*admin*) echo "frontend";;
    be|*back*|*api*|*server*|*service*) echo "backend";;
    *) echo "other";;
  esac
}

repo_row() { # $1 = repo root, $2 = path relative to workspace
  local r="$1" rel="$2" head branch count last shallow stack role
  head="$(git -C "$r" rev-parse --short HEAD 2>/dev/null || echo none)"
  branch="$(git -C "$r" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  count="$(git -C "$r" rev-list --count HEAD 2>/dev/null || echo 0)"
  last="$(git -C "$r" log -1 --format=%ad --date=short 2>/dev/null || echo '-')"
  shallow="$(git -C "$r" rev-parse --is-shallow-repository 2>/dev/null || echo '?')"
  stack="$(stack_of "$r")"
  role="$(role_of "$stack" "$(basename "$r")")"
  printf '| `%s` | %s | %s | `%s` on `%s` | %s | %s | %s |\n' "$rel" "$role" "$stack" "$head" "$branch" "$count" "$last" "$shallow"
}

HEADER='| path | role (guess) | stack (guess) | HEAD | commits | last commit | shallow |
|---|---|---|---|---|---|---|'

# Case 1: inside a repo.
TOP="$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$TOP" ]; then
  echo "MODE=single ROOT=$TOP"
  echo
  echo "# Repository"
  echo
  echo "$HEADER"
  repo_row "$TOP" "."
  if [ "$DIR" != "$TOP" ]; then
    echo
    echo "- Invoked from subfolder \`${DIR#"$TOP"/}\`: treat it as the default scope unless the user said otherwise."
  fi
  if [ -f "$TOP/.gitmodules" ]; then
    echo
    echo "## Submodules"
    echo
    git -C "$TOP" config -f .gitmodules --get-regexp '\.path$' 2>/dev/null | awk '{printf "- `%s`\n", $2}'
  fi
  exit 0
fi

# Case 2: not a repo; look for child repos (a .git dir or file), skipping heavy dirs.
REPOS="$(find "$DIR" -mindepth 2 -maxdepth $((DEPTH + 1)) \
  \( -name node_modules -o -name vendor -o -name .venv -o -name venv -o -name dist -o -name build -o -name .cache \) -prune -o \
  -name .git -print 2>/dev/null | sed 's|/\.git$||' | sort)"

# Drop repos nested inside another found repo (submodules, vendored clones).
FILTERED=""
while IFS= read -r r; do
  [ -z "$r" ] && continue
  nested=0
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    case "$r" in "$p"/*) nested=1;; esac
  done <<< "$FILTERED"
  [ "$nested" = 0 ] && FILTERED="$FILTERED$r"$'\n'
done <<< "$REPOS"
FILTERED="$(printf '%s' "$FILTERED" | sed '/^$/d')"

N="$(printf '%s\n' "$FILTERED" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$N" = 0 ]; then
  echo "MODE=none ROOT=$DIR"
  echo
  echo "No git repository here or in subfolders up to depth $DEPTH."
  exit 0
fi

echo "MODE=workspace ROOT=$DIR REPOS=$N"
echo
echo "# Workspace: \`$(basename "$DIR")\` ($N repositories)"
echo
echo "$HEADER"
while IFS= read -r r; do
  repo_row "$r" "${r#"$DIR"/}"
done <<< "$FILTERED"

LOOSE="$(find "$DIR" -mindepth 1 -maxdepth 1 ! -name '.*' 2>/dev/null | while IFS= read -r f; do
  inrepo=0
  while IFS= read -r r; do case "$r" in "$f"|"$f"/*) inrepo=1;; esac; done <<< "$FILTERED"
  [ "$inrepo" = 0 ] && echo "$f"
done)"
if [ -n "$LOOSE" ]; then
  echo
  echo "## Files and folders outside any repo (may be handover material or shared config)"
  echo
  printf '%s\n' "$LOOSE" | head -40 | while IFS= read -r f; do
    if [ -d "$f" ]; then echo "- \`${f#"$DIR"/}/\`"; else echo "- \`${f#"$DIR"/}\`"; fi
  done
fi
