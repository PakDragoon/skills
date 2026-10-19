# Workspace mode

Used when the skill is invoked in a folder that isn't a git repo but contains
repos, for example:

```
Relay/            ← invoked here (not a repo)
├── FE/           ← repo (React)
├── BE/           ← repo (NestJS)
└── docs/         ← loose files, often handover material
```

The goal is one page that explains the **system**, not two pages glued
together. A new joiner needs to see how the repos talk to each other first,
then each repo in detail.

## Paths and citations

- `ROOT` is the workspace folder. Every citation is **workspace-relative**:
  `BE/src/deals/deals.controller.ts:42`, not `src/deals/...`.
- Commits are cited as `<repo>@<hash>`, e.g. `BE@a1b2c3d`.
- Notes live in `notes/<repo>/` for per-repo stages and directly in `notes/`
  for workspace-wide ones.

## Choosing repos

`find-repos.sh` lists each repo with a role guess (frontend, backend,
fullstack, mobile, infra, other) and stack guess. The guesses come from
dependencies and folder names: confirm them while reading code, and correct
them on the page if wrong.

Ask the user once which repos to include (default: all). Skip repos that are
clearly unrelated (an old prototype, a forked library) only if the user agrees.

## Stage order

1. **Stage 0** as usual, then write `notes/00-workspace.md`: the repo table
   from find-repos.sh, the user's selection, and the loose files.
2. **Stages 1–3 per repo**, into `notes/<repo>/`. Read loose workspace files
   (docs, a root docker-compose, shared `.env.example`) in Stage 3 too.
3. **Stage 3b: API contract** (below).
4. **Stage 4 per repo**: architecture and module notes in
   `notes/<repo>/03-architecture.md` and `notes/<repo>/modules/`. With 2+
   repos, use subagents (one per module, 2–4 at a time).
5. **Stage 4b: System architecture** (below).
6. **Stage 5: cross-repo flows** (below).
7. **Stages 6–8** once for the whole workspace.

## Stage 3b: API contract

Run the matcher with every backend-ish repo as `--backend` and every
frontend-ish repo as `--frontend` (a fullstack repo can be both):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/api-contract.py \
  --backend BE --frontend FE --root . > <out>/notes/04-api-contract.md
```

It lists matched routes, frontend calls with no backend route, and backend
routes with no frontend caller. **It is a static heuristic.** Before any of it
reaches the page:

- **Matched:** open both sides for the routes used in core flows and confirm
  the method, path params and payload shape line up. Only then mark the link
  Confirmed (code on both sides plus a test or doc makes it Confirmed; code on
  both sides alone is still strong but stays Inferred if intent is unclear).
- **FE calls with no BE route:** check for a base URL pointing elsewhere
  (third-party API, another service), router mount prefixes the script lists
  but can't apply, or dynamic URLs. What remains is a candidate bug or a
  removed endpoint → Open question.
- **BE routes with no FE caller:** check for webhooks, mobile apps, cron,
  admin tools, or other consumers mentioned in docs. What remains is a dead
  code candidate → Gotchas (Inferred) or Open question.
- Also compare shared shapes where cheap: DTOs / validation schemas on the
  backend against the TypeScript types or form fields on the frontend for
  the core flows. Mismatches go to Gotchas.

Also find how the frontend reaches the backend: base URL env var names,
proxy config (vite/webpack/next rewrites), auth token handling (where it's
stored, how it's attached), CORS settings on the backend.

## Stage 4b: System architecture

Write `notes/03-system.md`:

- Repos and their roles, how they're deployed relative to each other (same
  domain? separate hosts? one docker-compose?).
- The integration points: REST/GraphQL API, websockets, shared database,
  queues, webhooks, shared packages, SSO.
- Auth across repos: where login happens, token type and lifetime, where it's
  validated.
- Environment wiring: which env var in which repo points at which other repo
  or service.
- Version coupling: shared type packages, API versioning, whether FE and BE
  must be deployed together.

## Stage 5: Cross-repo flows

A core flow in workspace mode starts where the user acts and ends where data
lands:

```
FE screen/component → FE state/hook → FE API client → HTTP → BE route/controller
→ BE validation → BE service → DB/ORM → side effects → response → FE update
```

Cite a file:line at each hop, tier each hop separately, and draw one Mermaid
`sequenceDiagram` with a participant per layer, grouping repos with
`box` blocks, e.g.:

```
sequenceDiagram
  box FE
    participant UI as DealForm
    participant API as api/deals.ts
  end
  box BE
    participant C as DealsController
    participant S as DealsService
    participant DB as Postgres
  end
  UI->>API: submit(deal)
  API->>C: POST /api/deals
  C->>S: create(dto)
  S->>DB: INSERT deal
```

## Who to ask

Owners differ per repo. Take "who to ask" for a question from the repo the
evidence lives in. For contract questions, name one person from each side.

## Page differences

See the workspace notes in artifact-spec.md: the header lists every repo, the
"System overview" section is filled, per-repo subsections appear in Run it
locally, Module guide, Build & deploy and History, and questions are grouped
by repo then module.
