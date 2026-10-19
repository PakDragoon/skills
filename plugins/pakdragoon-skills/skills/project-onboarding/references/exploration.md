# Module exploration

## Module note format

Every `notes/modules/<name>.md` uses this shape, so Stage 6 can merge them
mechanically:

```markdown
# <Module name>
Path(s): src/billing/, libs/invoice-pdf/
Owners (last 12 mo): Name A, Name B   Historical: Name C

## Purpose
One or two sentences: what business job this module does.

## Key files
- `src/billing/billing.service.ts`: core invoicing logic
- ...

## Interfaces
What other modules/clients call (routes, exported functions, events, jobs),
with file:line.

## Data
Entities/tables it reads and writes.

## Dependencies
Internal modules and external services (APIs, queues, buckets) it uses.

## Tests
What's covered, what isn't, disabled/skipped tests.

## Findings
- [Confirmed] claim. refs: `file:line`, `test:line`
- [Inferred] claim. refs: `file:line`
- [Open question] question. refs: ... | assumption: ... | ask: Name

## Comments worth knowing
Doc comments, TODO/FIXME/HACK, "do not change" warnings, with file:line.

## Doc claims checked
- "<claim>" (CLAUDE.md:12): verified / contradicted by `file:line` / unverifiable
```

## Reading strategy

1. Start at the module's entry points (routes/controllers/handlers/exported
   API), not alphabetically.
2. Follow calls one or two layers deep; stop at framework/library code.
3. Read the module's tests early. They name the cases the authors cared about.
4. Read doc comments on public functions; ignore boilerplate.
5. Use the churn table: if a hotspot file is in this module, read it fully.
6. Budget: don't read generated code, lockfiles, fixtures, vendored deps,
   minified assets, or snapshot files.

## Subagent brief (medium/large repos)

When dispatching a subagent per module, give it this brief, filled in:

> You are documenting one module of an unfamiliar codebase for a new team
> member. Module: **<name>** at **<paths>**. Repo root: **<root>**.
> Context: <2–3 line project summary from Stages 1–3>.
> Relevant doc claims to verify: <list from 02-docs-claims.md for this module>.
> Hotspot files in this module: <from 01-git.md>. Likely owners: <names>.
>
> Read the module's entry points, follow calls 1–2 layers deep, read its
> tests and doc comments. Write your findings to **<out>/notes/modules/<name>.md**
> using exactly the format in <path to this file> (section "Module note
> format"). Rules: every claim cites `file:line`; tag each finding Confirmed
> (code + a different kind of source agrees), Inferred (single source or
> unclear intent) or Open question (contradiction, oddity, or missing piece);
> never copy secrets, only env var names. Don't modify any code.
> Reply with only: the note path and counts per tier.

After subagents finish, spot-check 3 citations per note. If any are wrong,
re-verify that note yourself.
