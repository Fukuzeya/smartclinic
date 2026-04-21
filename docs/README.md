# SmartClinic — Documentation

This directory is the architectural spine of the project. Everything
here is Markdown so it renders on GitHub and diffs cleanly in PRs.

## Index

| Document                                                        | Purpose                                                                                         |
|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| [arc42/architecture.md](arc42/architecture.md)                  | The full architecture in arc42 structure (sections 1–9).                                        |
| [context-map.md](context-map.md)                                | The six bounded contexts and the relationship type on each edge (Partnership, ACL, etc.).       |
| [ubiquitous-language.md](ubiquitous-language.md)                | Per-context glossary — the canonical term for a concept inside each boundary.                   |
| [quality-attribute-scenarios.md](quality-attribute-scenarios.md)| ATAM-style scenarios for every quality attribute we care about, each linked to a tactic.        |
| [trade-offs-and-risks.md](trade-offs-and-risks.md)              | Sensitivity points, trade-offs, risks and non-risks — the "what we gave up" row on the rubric.  |
| [security-and-compliance.md](security-and-compliance.md)        | STRIDE threat model, POPIA / HIPAA controls, Keycloak token flow.                               |
| [adr/](adr/)                                                    | Architecture Decision Records (MADR 4.0). One file per decision, immutable after merge.         |

## How to read this

1. Start with [context-map.md](context-map.md) to see the shape of
   the system at a glance.
2. Skim [arc42/architecture.md](arc42/architecture.md) §1–5 for
   requirements, constraints, context, strategy, and the building-
   block view.
3. Open the ADR index (`adr/README.md`) when you want to know *why*
   a specific pattern was chosen over alternatives.
4. [quality-attribute-scenarios.md](quality-attribute-scenarios.md)
   and [trade-offs-and-risks.md](trade-offs-and-risks.md) are where
   architectural rigour is visible — read them together.
