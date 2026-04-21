# ADR-0001 — Record architecture decisions

- Status: Accepted
- Date: 2026-04-10
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: process, governance

## Context and Problem Statement

SmartClinic demonstrates several non-trivial architectural patterns
(Event Sourcing, CQRS, Sagas, Specification, ACL) on a non-trivial
domain (six bounded contexts, a production-like stack). Every
non-trivial decision will be questioned in assessment — and, more
importantly, will be second-guessed by us in a month. We need a
durable record of **what** we chose, **why**, and **what we gave up**.

## Decision Drivers

- The marking scheme explicitly rewards "Trade-offs, Alternatives, Risk".
- Decisions must survive team member turnover (a three-person team).
- Documentation must be co-located with code and reviewable in PRs.

## Considered Options

1. **MADR** (Markdown Any Decision Records, v4.0).
2. **Nygard ADRs** — the original 2011 short-form template.
3. **Free-form wiki page per decision** in a separate tool.
4. **No formal ADRs** — rely on commit messages and inline comments.

## Decision Outcome

Chosen option: **MADR 4.0**.

MADR is a strict superset of the Nygard form, adds Decision Drivers
and Considered Options (directly addressing the "Trade-offs" rubric
row), and is still plain Markdown — so it lives in the repo, renders
on GitHub, and is diffable in PRs.

### Positive Consequences
- Every pattern choice has a named file reviewers can read in seconds.
- New team members read `docs/adr/` and know the "why" of the system.
- The template enforces that we *consider* alternatives before choosing.

### Negative Consequences
- Writing ADRs has a cost; small decisions are excluded by convention.
- ADRs can go stale if not superseded explicitly. We mitigate this with
  a CI check that fails if an ADR is edited after acceptance (Phase 1
  does not yet implement the check — see backlog).

## Pros and Cons of the Options

### MADR 4.0
- Good, because it is the current community standard and has tooling.
- Good, because the "Considered Options" section maps 1:1 to the
  marking-scheme row.
- Bad, because it is slightly more verbose than Nygard.

### Nygard
- Good, because it is extremely short.
- Bad, because it lacks explicit alternatives — which is *the* thing we
  need for assessment.

### Wiki per decision
- Bad, because documentation drifts from the code it describes.
- Bad, because it is not reviewable in the same PR as the change.

### No ADRs
- Good, because zero overhead.
- Bad, because institutional memory evaporates.

## Links
- <https://adr.github.io/madr/>
- Nygard 2011, "Documenting Architecture Decisions".
