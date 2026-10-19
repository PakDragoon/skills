# Git mining

Goal: recover the *why* that code can't tell you, find where the risk lives,
and learn who to ask. Don't read every commit; read the ones that matter.

`scripts/git-insights.sh` gives you the raw tables. Then dig into these, in
this order, and write what you learn into `notes/01-git.md` under a
`## Interpretation` heading.

## 1. Timeline and eras

From the monthly commit counts and the first/last commit dates, split the
project into eras (e.g. "MVP 2021", "rewrite to NestJS 2023", "maintenance
2025–"). Look for:
- Sudden spikes (launches, rewrites, migrations)
- Long gaps (handovers, team changes)
- Big structural commits: `git log --diff-filter=A --format='%h %ad %s' --date=short -- <dir>` shows when a directory first appeared.

## 2. Hotspots (most-changed files)

The top 15 churn files are where complexity and bugs concentrate. For each of
the top ~5:
```bash
git log --format='%h %ad %an  %s' --date=short -n 25 -- <file>
```
Ask: why does this keep changing? Feature growth, bug fixes, config churn?
Hotspots with many `fix` commits go into Gotchas & risk areas.

## 3. Reverts, hotfixes, incidents

The script lists commits matching revert/hotfix/fix/urgent/rollback. For the
notable ones, `git show --stat <hash>` and read the message. These reveal:
- Things that broke in production and how
- Approaches that were tried and abandoned (valuable: stops the newcomer
  repeating them)

## 4. Origin of core files

For each core flow's main files:
```bash
git log --diff-filter=A --format='%h %ad %an  %s' --date=short -- <file>
git log --follow --format='%h %ad %s' --date=short -- <file> | tail -5
```
The introducing commit message often states the original intent.

## 5. Who knows what

From the per-area author table, take the **top 2 authors in the last 12
months** per module. Older authors may have left; list them separately as
"historical". Use names, never emails, in the output.

For a specific confusing block, `git blame -L <start>,<end> <file>` then
`git show <hash>` gives author + reason. Use sparingly; it's slow on big files.

## 6. Commit message quality

Note whether messages are informative (conventional commits, ticket IDs like
`ABC-123`) or noise ("fix", "wip"). If ticket IDs exist, record the tracker
prefix: the newcomer can look tickets up. If messages are noise, say so: it
lowers how much history can confirm.

## Shallow clones

If the repo is shallow, every finding from this stage is thin. Say so in the
page's method section and don't over-interpret.
