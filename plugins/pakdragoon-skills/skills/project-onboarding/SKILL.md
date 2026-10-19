---
name: project-onboarding
description: Generate a visual, evidence-backed onboarding guide (single HTML page) for an unfamiliar codebase, built from the code, git history, CLAUDE.md files, code comments, and any handover material the team provides. Works in one repo, or in a parent folder holding several repos (e.g. separate frontend and backend), where it also traces flows across repos. Use when joining or inheriting an existing project, taking over a handover, or when someone asks "explain this whole project to me". Every claim is tagged Confirmed, Inferred, or Open question, and open questions come with a suggested person to ask.
argument-hint: "[scope: whole project | <repo> | module/flow name] [--materials <path>] [--out <dir>]"
allowed-tools: Bash(bash ${CLAUDE_SKILL_DIR}/scripts/*), Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*), Bash(git log *), Bash(git show *), Bash(git blame *), Bash(git shortlog *), Bash(git rev-parse *), Bash(git ls-files *), Bash(git -C *)
---

# Project Onboarding

Turn an existing codebase into one self-contained HTML page that a new team
member can read in an hour and trust. The page explains what the project is,
how it runs, how its core flows work, how it got here, and what is still
unknown, with every claim tied to evidence.

Arguments: `$ARGUMENTS`

## Principles (non-negotiable)

1. **Evidence or it didn't happen.** Every factual claim in the output cites at
   least one `path/to/file.ext:line` (or commit hash, or material filename).
2. **Three confidence tiers, strictly applied.** Read
   [references/confidence-rules.md](references/confidence-rules.md) before
   writing any finding. Never upgrade a tier to make the page look better.
3. **Docs and comments are claims, not truth.** CLAUDE.md, READMEs, comments
   and handover notes are checked against code. Mismatches are findings
   (doc drift), not things to silently resolve.
4. **Specific beats generic.** "NestJS app with controllers" is worthless. Name
   the business flows, the entities, the odd decisions, the risky files.
5. **Never leak secrets.** Env var *names* only. Redact any key, token,
   password, connection string or private hostname you encounter. Scrub
   personal emails from the output; use author names only.
6. **Work in files, not in context.** Large codebases don't fit in one pass.
   Every stage writes notes to disk so later stages (and reruns) build on them.

## Modes

The skill runs in one of two modes, decided in Stage 0:

- **Single-repo mode:** invoked inside a git repo (at its root or any
  subfolder).
- **Workspace mode:** invoked in a folder that is *not* a repo but contains
  repos (e.g. `Relay/` holding `FE/` and `BE/`). Each repo gets the per-repo
  stages, then a cross-repo stage connects them, and one combined page is
  produced. Read [references/workspace-mode.md](references/workspace-mode.md)
  as soon as this mode is detected.

## Inputs

Parse `$ARGUMENTS`:

- **Scope** (free text before any flag). Empty or "whole project" means
  everything. Otherwise:
  - a module, directory, or flow name (e.g. `billing module`, `src/payments`,
    `order checkout flow`);
  - in workspace mode, a repo name (`BE`), a repo plus module (`BE billing`),
    or a flow, which is traced across repos (`deals flow`).
  With a scope, still do Stages 1–2 everywhere (lightly), then go deep only on
  the scope. If invoked from a repo subfolder and no scope is given, propose
  that subfolder as the scope.
- `--materials <path>`: file or folder of handover material (docs, PDFs,
  exported Slack threads, diagrams, meeting notes). Optional.
- `--out <dir>`: output directory. Default `.onboarding/` at the repo root
  (single-repo mode) or at the workspace folder (workspace mode).

If the user mentions material in conversation without a flag, ask for its path
once. Never block on it: material is optional.

## Output layout

```
<out>/
├── onboarding.html          ← the deliverable (self-contained)
├── open-questions.md        ← same questions, plain markdown, for pasting
└── notes/                   ← working notes, reused on reruns
    ├── 00-inventory.md          (workspace mode: one folder per repo,
    ├── 01-git.md                 notes/<repo>/00-inventory.md etc.,
    ├── 02-docs-claims.md         plus notes/00-workspace.md and
    ├── 03-architecture.md        notes/04-api-contract.md)
    ├── modules/<module>.md
    ├── flows/<flow>.md
    └── 99-findings.md
```

If `<out>/notes/` already exists from a previous run, read it first, note the
commit(s) it was built from, and only re-examine what changed since
(`git -C <repo> diff --stat <old>..HEAD`). Say so in the page header.

## Workflow

Create a task list with these stages and tick them off. Tell the user the
stage you are on in one short line; don't narrate details.

### Stage 0: Preflight and mode

1. Detect the mode:
   ```bash
   bash ${CLAUDE_SKILL_DIR}/scripts/find-repos.sh .
   ```
   The first output line is `MODE=single|workspace|none ROOT=<path>`.
   - `single`: continue with ROOT as the repo.
   - `workspace`: show the user the repo table (path, role guess, stack)
     and ask, in one question, whether to document all of them as one
     system or only some. Workspace mode exists for exactly this case, so
     never stop here just because the folder isn't a repo. If the user
     isn't there to answer, document all repos and say so in the page.
   - `none`: stop and say no git repository was found here or in
     subfolders; ask for the right folder.
2. For each repo in play: record `HEAD` hash, branch, and today's date for
   the page header.
3. Shallow clones (shown in the table): tell the user history-based findings
   for that repo will be thin and suggest `git -C <repo> fetch --unshallow`.
   Continue either way.
4. Create `<out>/notes/`. In single-repo mode, if `<out>` is inside the repo
   and not gitignored, mention once that the user may want to gitignore it
   or commit it.

In workspace mode, run Stages 1–3 **per repo**, writing to
`notes/<repo>/`, then continue as described in references/workspace-mode.md.

### Stage 1: Inventory

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/repo-inventory.sh <repo> > <notes-dir>/00-inventory.md
```

It lists languages, manifests, entry-point candidates, every CLAUDE.md /
AGENTS.md / README / docs / ADR file, tests, migrations, CI, container and IaC
files, and env example files. Read the output, then decide:

- **Size class:** small (< 300 tracked source files), medium (300–2,000),
  large (> 2,000). This decides Stage 4 strategy.
- **Module list:** the top-level units worth a deep dive (apps in a monorepo,
  bounded contexts, major `src/` subfolders). Aim for 4–12 per repo.

### Stage 2: Git history

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/git-insights.sh <repo> > <notes-dir>/01-git.md
```

Then follow [references/git-mining.md](references/git-mining.md) to read the
targeted commits (hotspots, reverts, hotfixes, big refactors, the commits that
introduced core files) and record *why* things changed. Map owners per module
from the script's author table: this feeds the "who to ask" column later.

### Stage 3: Read the stated knowledge

Read, in order, and log each claim to `<notes-dir>/02-docs-claims.md` as
`- [source:line] claim`:

1. Every CLAUDE.md / AGENTS.md (root and nested; nested ones describe their
   subtree).
2. README files, `docs/`, ADRs, CONTRIBUTING, runbooks.
3. Handover material from `--materials` (use the pdf/docx reading skills if
   available for binary formats). In workspace mode, also check the
   "outside any repo" files that find-repos.sh listed: they are often
   handover docs or shared config.

These are hypotheses to verify in Stages 4–5, not facts yet.

### Stage 4: Architecture and modules

1. Write `03-architecture.md`: how the system boots (entry points), how it's
   run locally (package scripts, Makefile, docker-compose, `.env.example`
   names), how it's built and deployed (CI pipelines, Dockerfiles, IaC), the
   external services it talks to, and how modules depend on each other.
2. Deep-dive each module (or only the scoped one) into `modules/<name>.md`
   using the module note format in
   [references/exploration.md](references/exploration.md). Read code,
   function/class doc comments, and the module's tests (tests are the best
   record of intended behavior).
   - **Small codebase:** do it yourself, sequentially.
   - **Medium/large, or workspace mode with 2+ repos:** dispatch one
     subagent per module (2–4 at a time) with the brief in
     references/exploration.md. Subagents write their own note files; you
     review them and spot-check citations.

### Stage 5: Core flows and data model

1. Pick the 3–5 flows that matter most: weight by business centrality
   (what the product is *for*), churn (from Stage 2), and what docs/material
   emphasize. Trace each end to end (entry → validation → business logic →
   persistence → side effects such as queues, emails, webhooks) into
   `flows/<flow>.md` with file:line at each hop. In workspace mode, flows
   start at the UI and cross into the backend (see workspace-mode.md).
2. Build the data model from schema files, ORM models and migrations: key
   entities, relationships, and how the schema evolved (migration history is
   history of the business).

### Stage 6: Reconcile and classify

Write `notes/99-findings.md`:

1. Check every claim in `02-docs-claims.md` against what Stages 4–5 found.
   Mark each verified, contradicted (→ doc drift entry), or unverifiable.
2. Assign each finding its tier per references/confidence-rules.md.
3. Collect **gotchas and risk areas**: hotspot files with many fixes, code
   with "don't touch"/"hack"/"TODO"/"FIXME" comments, dead code candidates,
   disabled tests, missing tests on core flows, surprising coupling, and in
   workspace mode, contract mismatches between repos.
4. Build **open questions**. Each one needs: the question, file/commit
   reference, what you assumed meanwhile, and a suggested person to ask (top
   recent author of the relevant files from Stage 2). Group by module (and by
   repo in workspace mode).
5. Build a **glossary** of domain terms found in code and docs.

### Stage 7: Build the page

Read [references/artifact-spec.md](references/artifact-spec.md), then copy
`${CLAUDE_SKILL_DIR}/templates/onboarding.html` to `<out>/onboarding.html` and
fill every section. Write `<out>/open-questions.md` with the same questions.

### Stage 8: Verify

1. Run the reference checker and fix every broken citation it reports:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/check-refs.py <out>/onboarding.html --root <ROOT>
   ```
2. Grep the HTML for anything secret-shaped (keys, `password=`, `://user:pass@`,
   long base64/hex strings, private IPs) and redact.
3. Confirm no `<!-- FILL` markers remain.
4. Re-read the TL;DR and Core flows sections as if you were the new joiner. If
   a sentence wouldn't help them, cut or sharpen it.

## Finish

Reply with: where the page is, the size of each tier (e.g. "41 confirmed, 17
inferred, 9 open questions"), the top 3 risk areas in one line each, and the
suggestion to send `open-questions.md` to the people listed in it. Offer to open
the page in a browser if a browser tool is available. Don't recap the stages.
