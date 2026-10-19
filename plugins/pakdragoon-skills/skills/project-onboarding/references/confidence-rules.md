# Confidence rules

Every finding on the page carries exactly one tier. The tiers exist so a new
joiner knows what they can rely on and what they must verify. A page where
everything is "Confirmed" is a page nobody should trust.

## Sources of evidence

| Kind | Examples | Counts as |
|---|---|---|
| **Code** | implementation, config, schema, migrations, CI, IaC | behavior evidence |
| **Test** | unit/integration/e2e tests asserting the behavior | intent evidence (strong) |
| **History** | commit messages, PR/merge titles, reverts, blame | intent evidence |
| **Stated** | CLAUDE.md, README, docs/, ADRs, code comments, handover material | intent evidence (may be stale) |

## The tiers

### Confirmed
The code shows the behavior **and** at least one independent source of a
different kind agrees (a test, a commit message, a doc, a comment, or material).

> Orders move to `PAID` only after the Stripe webhook verifies the signature.
> `src/payments/webhook.controller.ts:42`, `test/payments/webhook.spec.ts:88`

### Inferred
Only one source supports it (usually the code alone), or the mechanics are
clear but the *intent* isn't. Phrase it as "appears to", "seems designed to".

> Appears to soft-delete customers (sets `deletedAt`) rather than removing
> rows. `src/customers/customers.service.ts:131`. No test or doc covers this.

### Open question
Any of these:
- Sources contradict each other (doc says X, code does Y) and it's unclear
  which reflects intent.
- Behavior looks wrong, dangerous, or deliberately odd with no explanation.
- A critical piece is missing from the repo (e.g. a service it calls, a
  cron defined elsewhere, a manual deploy step).
- You can't tell whether code is dead or used.

Every open question records: **question**, **evidence refs**, **current
assumption** (what the page assumes until answered), **ask** (person).

## Rules

1. **Two of the same kind is still one.** Two comments, or code plus a
   comment written in the same commit by the same author, don't make
   Confirmed. Need a different kind (code + test, code + commit message
   from a different change, code + doc).
2. **Stale stated knowledge loses.** When a doc/comment contradicts code, the
   code describes current *behavior*. Record the mismatch in Doc drift. If the
   doc might describe the *intended* behavior (i.e. the code could be a bug),
   it's also an Open question.
3. **Generated or vendored code isn't evidence of intent.** Note it, skip it.
4. **Absence is a finding, not a confirmation.** "No tests cover checkout" is
   Confirmed (you checked); "checkout has no bugs" is not a claim you make.
5. **Don't round up for flow.** If one hop in a traced flow is Inferred, mark
   that hop, not the whole flow as Confirmed.
6. **Material from the team isn't automatically right.** It's a Stated source
   like any doc. It can confirm code; it can't override it.

## Markup

In the HTML, wrap each claim's badge as:

```html
<span class="tier tier-confirmed">Confirmed</span>
<span class="tier tier-inferred">Inferred</span>
<span class="tier tier-question">Open question</span>
```

In diagrams: confirmed edges solid (`-->`), inferred edges dashed (`-.->`),
open-question nodes styled with the `question` class.
