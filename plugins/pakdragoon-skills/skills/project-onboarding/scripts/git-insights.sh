#!/usr/bin/env bash
# git-insights.sh: print markdown tables mined from git history for onboarding.
# Usage: bash git-insights.sh [repo-root]
# Env: MAX_COMMITS (default 20000) caps history scanned on huge repos.
# Prints author NAMES only, never emails.
set -uo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "${ROOT}" ] || ! git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "error: not inside a git repository" >&2
  exit 1
fi
cd "$ROOT" || exit 1
if ! git rev-parse HEAD >/dev/null 2>&1; then
  echo "# Git insights"; echo; echo "_Repository has no commits yet._"; exit 0
fi

MAX="${MAX_COMMITS:-20000}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

NOISE='(^|/)(node_modules|vendor|dist|build|coverage|__snapshots__)/|\.min\.(js|css)$|(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|composer\.lock|Gemfile\.lock|poetry\.lock|Cargo\.lock|go\.sum|(CHANGELOG|CHANGES|HISTORY|History|Changelog)\.md)$'
SINCE_12="$(date -d '12 months ago' +%Y-%m-%d 2>/dev/null || date -v-12m +%Y-%m-%d)"

# One pass over history: "@@<hash>\t<date>\t<author>\t<subject>" then file names.
git -c core.quotepath=off log --no-merges -n "$MAX" --date=short \
  --format='@@%h%x09%ad%x09%an%x09%s' --name-only > "$TMP/log"

# Flatten to: hash \t date \t author \t subject \t file
awk -F'\t' '/^@@/ {h=substr($1,3); d=$2; a=$3; s=$4; next}
  NF && $0 !~ /^@@/ {print h"\t"d"\t"a"\t"s"\t"$0}' "$TMP/log" |
  awk -F'\t' -v re="$NOISE" '$5 !~ re' > "$TMP/flat"

# Area key: first segment, or first/second for common source roots.
area_awk='function area(p,   n, s) { n=split(p, s, "/");
  if (n==1) return "(root)";
  if (s[1] ~ /^(src|apps|packages|libs|services|modules|lib|app|internal|cmd|pkg)$/ && n>2) return s[1]"/"s[2]"/";
  return s[1]"/" }'

echo "# Git insights"
echo
SHALLOW="$(git rev-parse --is-shallow-repository)"
TOTAL="$(git rev-list --count HEAD)"
FIRST="$(git log --reverse --format='%ad' --date=short | head -1)"
LAST="$(git log -1 --format='%ad' --date=short)"
echo "- Commits on HEAD: $TOTAL (scanned non-merge: up to $MAX)"
echo "- First commit: $FIRST  |  Last commit: $LAST"
echo "- Contributors (all time): $(git log --format='%an' | sort -u | wc -l | tr -d ' ')  |  active last 12 months: $(git log --since="$SINCE_12" --format='%an' | sort -u | wc -l | tr -d ' ')"
echo "- Shallow clone: $SHALLOW"
[ "$SHALLOW" = "true" ] && echo "- **Warning:** shallow history. Run \`git fetch --unshallow\` for reliable findings."

echo; echo "## Activity by month (non-merge commits, last 36 months)"; echo
git log --no-merges --since="$(date -d '36 months ago' +%Y-%m-01 2>/dev/null || date -v-36m +%Y-%m-01)" \
  --format='%cd' --date=format:'%Y-%m' | sort | uniq -c |
  awk '{bar=""; n=int($1/5)+1; if(n>40)n=40; for(i=0;i<n;i++) bar=bar"#"; printf "- %s %4d %s\n", $2, $1, bar}'

echo; echo "## Activity by year (all history)"; echo
git log --no-merges --format='%ad' --date=format:'%Y' | sort | uniq -c | awk '{printf "- %s: %d\n", $2, $1}'

echo; echo "## Hotspots: most-changed files (all scanned history)"; echo
echo "| commits | fix-commits | file |"; echo "|---:|---:|---|"
awk -F'\t' '{c[$5]++; if (tolower($4) ~ /(^|[^a-z])(fix|bug|hotfix|patch|issue|broken|crash|error)/) f[$5]++}
  END {for (k in c) printf "%d\t%d\t%s\n", c[k], f[k]+0, k}' "$TMP/flat" |
  sort -t$'\t' -k1,1nr | head -25 | awk -F'\t' '{printf "| %d | %d | `%s` |\n", $1, $2, $3}'

echo; echo "## Hotspots: last 12 months"; echo
echo "| commits | file |"; echo "|---:|---|"
awk -F'\t' -v s="$SINCE_12" '$2 >= s {c[$5]++} END {for (k in c) printf "%d\t%s\n", c[k], k}' "$TMP/flat" |
  sort -t$'\t' -k1,1nr | head -15 | awk -F'\t' '{printf "| %d | `%s` |\n", $1, $2}'

echo; echo "## Who knows what: top authors per area"; echo
echo "| area | last 12 months (commits) | all time (commits) |"; echo "|---|---|---|"
awk -F'\t' -v s="$SINCE_12" "$area_awk"'
  { k=area($5); key=$1 SUBSEP k SUBSEP $3; if (key in seen) next; seen[key]=1;
    all[k SUBSEP $3]++; tot[k]++; if ($2 >= s) rec[k SUBSEP $3]++ }
  END { for (x in all) { split(x, p, SUBSEP); print "A\t" p[1] "\t" all[x] "\t" p[2] }
        for (x in rec) { split(x, p, SUBSEP); print "R\t" p[1] "\t" rec[x] "\t" p[2] }
        for (k in tot) print "T\t" k "\t" tot[k] }' "$TMP/flat" > "$TMP/areas"
grep '^T' "$TMP/areas" | sort -t$'\t' -k3,3nr | head -30 | cut -f2 | while IFS= read -r a; do
  rec="$(awk -F'\t' -v a="$a" '$1=="R" && $2==a' "$TMP/areas" | sort -t$'\t' -k3,3nr | head -3 | awk -F'\t' '{printf "%s%s (%d)", sep, $4, $3; sep=", "}')"
  all="$(awk -F'\t' -v a="$a" '$1=="A" && $2==a' "$TMP/areas" | sort -t$'\t' -k3,3nr | head -3 | awk -F'\t' '{printf "%s%s (%d)", sep, $4, $3; sep=", "}')"
  printf '| `%s` | %s | %s |\n' "$a" "${rec:-none}" "${all:-none}"
done

echo; echo "## Reverts, hotfixes and incident-like commits (latest 40)"; echo
git log --no-merges -n "$MAX" --date=short --format='%h%x09%ad%x09%an%x09%s' |
  grep -iE $'\t[^\t]*(revert|hotfix|hot fix|rollback|roll back|urgent|critical|incident|outage|prod(uction)? (issue|bug|fix)|emergency)' |
  head -40 | awk -F'\t' '{printf "- `%s` %s %s: %s\n", $1, $2, $3, $4}'

echo; echo "## Largest commits (likely refactors, migrations, rewrites)"; echo
awk -F'\t' '{c[$1]++; m[$1]=$2"\t"$3"\t"$4} END {for (h in c) print c[h] "\t" h "\t" m[h]}' "$TMP/flat" |
  sort -t$'\t' -k1,1nr | head -15 | awk -F'\t' '{printf "- `%s` %s %s (%d files): %s\n", $2, $3, $4, $1, $5}'

echo; echo "## When each area first appeared"; echo
awk -F'\t' "$area_awk"'{ k=area($5); if (!(k in first) || $2 < first[k]) { first[k]=$2; fh[k]=$1; fs[k]=$4 } }
  END { for (k in first) print first[k] "\t" k "\t" fh[k] "\t" fs[k] }' "$TMP/flat" |
  sort | head -40 | awk -F'\t' '{printf "- %s `%s` via `%s`: %s\n", $1, $2, $3, $4}'

echo; echo "## Commit message conventions"; echo
git log --no-merges -n 1000 --format='%s' > "$TMP/subjects"
N="$(wc -l < "$TMP/subjects" | tr -d ' ')"
CONV="$(grep -cE '^(feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)(\(.+\))?!?:' "$TMP/subjects" || true)"
SHORT="$(awk 'length($0) < 12' "$TMP/subjects" | wc -l | tr -d ' ')"
echo "- Sample: last $N subjects. Conventional-commit style: ${CONV:-0}. Very short/noisy (< 12 chars): $SHORT"
TICKETS="$(grep -owE '[A-Z][A-Z0-9]{1,9}-[0-9]+' "$TMP/subjects" | grep -vE '^(UTF|ISO|SHA|RFC|HTTP|ES|TLS|SSL)-' | sed -E 's/-[0-9]+$//' | sort | uniq -c | sort -rn | head -5 | awk '{printf "%s%s (%d)", sep, $2, $1; sep=", "}')"
echo "- Ticket ID prefixes: ${TICKETS:-none detected}"
GH="$(grep -cE '#[0-9]+' "$TMP/subjects" || true)"
echo "- Subjects referencing #PR/issue numbers: ${GH:-0}"

echo; echo "## Recent merge commits (PR titles, latest 25)"; echo
git log --merges -n 25 --date=short --format='- `%h` %ad %an: %s' || true

echo; echo "## Tags (latest 15)"; echo
TAGS="$(git tag --sort=-creatordate | head -15)"
if [ -n "$TAGS" ]; then
  while IFS= read -r t; do echo "- \`$t\` $(git log -1 --format=%ad --date=short "$t" 2>/dev/null)"; done <<< "$TAGS"
else
  echo "_no tags_"
fi
echo
