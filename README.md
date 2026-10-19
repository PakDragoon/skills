# PakDragoon Skills

Claude Code skills I use for real-world engineering work, packaged as a plugin
marketplace.

## Install

```bash
/plugin marketplace add PakDragoon/skills
/plugin install pakdragoon-skills@pakdragoon
```

Or from your shell:

```bash
claude plugin marketplace add PakDragoon/skills
claude plugin install pakdragoon-skills@pakdragoon
```

## Skills

| Skill | Command | What it does |
|---|---|---|
| [project-onboarding](plugins/pakdragoon-skills/skills/project-onboarding/SKILL.md) | `/pakdragoon-skills:project-onboarding` | Turns an unfamiliar codebase into a visual, evidence-backed onboarding guide |

---

## project-onboarding

You've just been moved onto a project that has been in development for years.
The docs are thin or stale, the people who built it are busy, and the code is
the only source of truth. This skill reads the repository the way a careful
senior engineer would and produces one HTML page that explains it.

### Usage

Run it from the root of the repository you want to understand:

```bash
/pakdragoon-skills:project-onboarding
/pakdragoon-skills:project-onboarding billing module
/pakdragoon-skills:project-onboarding --materials ~/handover-docs
/pakdragoon-skills:project-onboarding order checkout flow --out docs/onboarding
```

### What it reads

- **Code**: entry points, modules, schema and migrations, config, CI/CD, IaC
- **Tests**: the best record of intended behavior
- **Git history**: churn hotspots, reverts and hotfixes, large refactors, when
  each area appeared, and who has worked on what recently
- **CLAUDE.md / AGENTS.md** files, root and nested
- **Code comments**: doc comments, TODO/FIXME/HACK, "don't touch" warnings
- **Your material** (optional): handover docs, PDFs, notes from the team

### What you get

`.onboarding/onboarding.html`, a single self-contained page with:

- TL;DR, and how to run it locally (env var names only, never values)
- Architecture diagram and component table
- 3–5 core business flows traced end to end, each with a sequence diagram
- Data model (ER diagram) and how the schema evolved
- Module guide with owners and test coverage
- Build and deploy pipeline
- History and hotspots, incidents, abandoned approaches
- Gotchas and risk areas
- **Doc drift**: where docs and comments disagree with the code
- **Open questions**, each with the current assumption and a suggested person
  to ask, with a "Copy as Markdown" button so you can paste them to your team
- Glossary of domain terms

Plus `open-questions.md` and the working notes in `.onboarding/notes/`, which
make reruns incremental.

### Confidence tiers

Every claim on the page is tagged and cites `file:line` or a commit:

| Tier | Meaning |
|---|---|
| **Confirmed** | The code shows it and an independent source agrees (a test, a commit message, a doc) |
| **Inferred** | One source only, or the mechanics are clear but the intent isn't |
| **Open question** | Sources contradict, behavior looks odd or wrong, or a piece is missing from the repo |

Docs and comments are treated as claims to verify, not facts. Diagrams use
solid edges for confirmed paths and dashed edges for inferred ones. The page
has filters to show or hide each tier.

### How it works

1. **Preflight**: checks the repo, records the commit, warns about shallow clones
2. **Inventory**: `scripts/repo-inventory.sh` maps languages, layout, manifests, docs, tests, migrations, CI, IaC, env var names
3. **Git history**: `scripts/git-insights.sh` mines hotspots, incidents, eras and ownership
4. **Stated knowledge**: CLAUDE.md files, docs and your material, logged as claims to verify
5. **Architecture and modules**: one subagent per module on larger repos
6. **Core flows and data model**: traced hop by hop with citations
7. **Reconcile**: verify claims, classify findings, build open questions
8. **Build and verify**: fills the HTML template, then `scripts/check-refs.py` checks every citation resolves and scans for secrets

### Tips

- Unshallow the clone first (`git fetch --unshallow`) so history findings are reliable.
- Add `.onboarding/` to `.gitignore`, or commit it if your team wants a shared copy.
- Send `open-questions.md` to the people it names. Their answers are the context the code can't give you.
- On large repos, scope it to the area you're starting on.

---

## Repository layout

```
.claude-plugin/marketplace.json          marketplace catalog
plugins/pakdragoon-skills/
├── .claude-plugin/plugin.json           plugin manifest
└── skills/project-onboarding/
    ├── SKILL.md                         workflow
    ├── references/                      confidence rules, git mining, exploration, artifact spec
    ├── scripts/                         repo-inventory.sh, git-insights.sh, check-refs.py
    └── templates/onboarding.html        output page template
```

## Local development

```bash
git clone https://github.com/PakDragoon/skills.git
cd skills
claude plugin validate .
claude --plugin-dir ./plugins/pakdragoon-skills
```

Requirements for the scripts: `bash`, `git`, `awk`, and `python3`. They work on
Linux and macOS.

## License

MIT, see [LICENSE](LICENSE).
