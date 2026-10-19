# Artifact spec

The deliverable is `templates/onboarding.html`, filled in. It's a single
self-contained page: inline CSS/JS, Mermaid loaded from jsDelivr, works offline
except for diagrams. Light and dark mode are handled by the template.

Replace every `<!-- FILL: ... -->` marker. Delete optional sections that have
nothing real to say rather than padding them. Keep the section order.

## Reader and tone

The reader is a competent engineer who has never seen this project and has
one hour. Write plainly, short sentences, concrete nouns. Lead each section
with the most useful sentence. No marketing language, no "robust", no
"comprehensive", no "leverages".

## Sections

| # | id | Section | Must contain |
|---|---|---|---|
| 0 | header | Title block | Project name, repo, branch, commit hash (short), generated date, scope, sources used (checkboxes: code, git history, N CLAUDE.md files, docs, tests, material), tier counts |
| 1 | tldr | TL;DR | 4–6 bullets: what it does, for whom, stack, how big/old, current state (active/maintenance), the one thing to be careful about |
| 1b | system | System overview | **Workspace mode only** (delete the section and its TOC link otherwise). Repo table (path, role, stack, owners), Mermaid flowchart of repos and integration points, how FE reaches BE (base URL env names, proxy, auth), API contract summary: matched count, table of FE-calls-without-route and routes-without-caller after verification |
| 2 | start | Run it locally | Prereqs, ordered commands, env var **names** with one-line purpose (never values), seed/test data, how to run tests. Mark steps you couldn't verify as Inferred |
| 3 | architecture | Architecture | Mermaid `flowchart` of components and external services; table: component, path, responsibility, owners |
| 4 | flows | Core flows | 3–5 flows. Each: one-paragraph story, Mermaid `sequenceDiagram`, numbered hops with file:line and tier per hop |
| 5 | data | Data model | Mermaid `erDiagram` of key entities (not every table), notes on important fields/states, schema evolution highlights from migrations |
| 6 | modules | Module guide | One card per module: purpose, key files, interfaces, tests status, owners, findings with tiers |
| 7 | infra | Build & deploy | CI pipeline steps, environments, deploy mechanism, infra-as-code, scheduled jobs, external dependencies. Missing/manual steps → Open questions |
| 8 | history | History & hotspots | Era timeline, top hotspot files with why they churn, notable reverts/incidents, abandoned approaches, who knows what (current vs historical) |
| 9 | gotchas | Gotchas & risk areas | Ranked list: what, where (file:line), why it matters, tier |
| 10 | drift | Doc drift | Table: source (doc:line), what it says, what code does (file:line). Omit section if none found, but say "no drift found" in header sources |
| 11 | questions | Open questions | Grouped by module. Table: #, question, refs, current assumption, ask. A "Copy as Markdown" button is wired in the template |
| 12 | glossary | Glossary | Domain terms → meaning → where defined |
| 13 | method | How this was made | What was read, what wasn't (generated code, vendored deps), shallow-clone caveat, previous-run delta, tier rules summary |

## Workspace mode differences

- **Header:** the Repository cell lists every repo with its short hash
  (`FE <code>1abcad2</code>, BE <code>0f61c03</code>`); Commit cell becomes
  "see repos"; sources list counts per repo.
- **TL;DR:** describe the system first, then one bullet per repo.
- **Run it locally, Build & deploy, History:** one `<h3>` per repo, plus a
  first `<h3>Together</h3>` for running the full stack (start order, ports,
  which env var points FE at BE).
- **Architecture:** the system diagram goes in System overview; Architecture
  holds one diagram per repo (or the most important one if space is tight).
- **Module cards:** prefix the card title with the repo (`BE · Billing`) and
  give ids like `mod-be-billing`.
- **Core flows:** cross-repo sequence diagrams with `box` groups per repo.
- **Open questions:** `data-module` is `"<repo> · <module>"`; contract
  questions use `"Contract"`.
- **Citations:** workspace-relative paths (`BE/src/...`), commits as
  `<code class="ref commit">BE@a1b2c3d</code>`.

## HTML patterns

Tier badges:
```html
<span class="tier tier-confirmed">Confirmed</span>
<span class="tier tier-inferred">Inferred</span>
<span class="tier tier-question">Open question</span>
```

File reference (the checker validates these):
```html
<code class="ref">src/orders/orders.service.ts:118</code>
```
Use repo-relative paths. A line range is `file:118-140`. A commit is
`<code class="ref commit">a1b2c3d</code>`. Material is
`<code class="ref material">handover-notes.pdf p.4</code>` (not checked).

Finding list item:
```html
<li class="finding"><span class="tier tier-inferred">Inferred</span>
  Appears to retry failed webhooks 3 times with no backoff.
  <code class="ref">src/hooks/retry.ts:22</code></li>
```

Module card:
```html
<article class="card" id="mod-billing">
  <h3>Billing <span class="path">src/billing/</span></h3>
  <p class="purpose">...</p>
  <dl class="meta"><dt>Owners</dt><dd>Name A, Name B</dd><dt>Tests</dt><dd>...</dd></dl>
  <h4>Key files</h4><ul>...</ul>
  <h4>Findings</h4><ul class="findings">...</ul>
</article>
```

Flow step list:
```html
<ol class="hops">
  <li><span class="tier tier-confirmed">Confirmed</span> Controller validates
  the DTO. <code class="ref">src/orders/orders.controller.ts:31</code></li>
</ol>
```

Open question row (keep `data-*` attributes; the copy button reads them):
```html
<tr data-module="Billing" data-q="Is the 3-day grace period still required?"
    data-refs="src/billing/dunning.ts:57" data-assume="Yes, kept as is"
    data-ask="Name A">
  <td>1</td><td>Is the 3-day grace period still required?</td>
  <td><code class="ref">src/billing/dunning.ts:57</code></td>
  <td>Yes, kept as is</td><td>Name A</td>
</tr>
```

## Diagrams (Mermaid)

Place each in `<pre class="mermaid">...</pre>`.

- Confirmed relationships: solid `-->`. Inferred: dashed `-.->`.
- Open-question nodes: add `:::question`, e.g. `Cron[Nightly sync?]:::question`
  (the template's init defines the class via `classDef`; include
  `classDef question stroke-dasharray:4 3,stroke-width:2px` at the end of each
  flowchart that uses it).
- Keep diagrams readable: ≤ 15 nodes in a flowchart, ≤ 8 participants in a
  sequence diagram, ≤ 12 entities in an ER diagram. Split if bigger.
- Escape special characters in labels: wrap labels with `()`, `/`, `:` in quotes,
  e.g. `A["POST /orders"]`.
- No secrets, internal IPs, or customer data in labels.

## Length

Aim for a page readable in about an hour: TL;DR + Run it + Architecture +
Flows should be enough for day one; the rest is reference.
