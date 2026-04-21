# ADR-0007 — Anti-Corruption Layer for the external drug database

- Status: Accepted
- Date: 2026-04-12
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: tactical-ddd, acl, pharmacy, integration

## Context and Problem Statement

The Pharmacy context needs drug data (formulary, ingredients,
interactions) to evaluate its specifications (ADR-0006). A rich public
source exists — the **U.S. National Library of Medicine's RxNav / RxNorm
REST API**. Its model is idiomatic to its own domain: `rxcui`, `tty`,
`ingredientBase`, polymorphic JSON payloads that have evolved over
time and carry artefacts of US pharmaceutical regulation.

If we let RxNav's shape leak into our domain, our Pharmacy aggregates
will start to reason in RxNav's terms — and every RxNav schema change
will ripple into our code.

## Decision Drivers

- Keep the Pharmacy domain language clean (`Medication`, `Ingredient`,
  `Interaction` — not `rxcui`, `tty`).
- Isolate us from upstream drift.
- Allow swapping RxNav for a local MOHCC formulary later — a real
  possibility, given that RxNav's data is US-centric.
- The marking scheme explicitly rewards the Anti-Corruption Layer.

## Considered Options

1. **Direct client in the domain** — call RxNav from aggregates / services.
2. **Thin mapper** — a `rxnav_client.py` with mapping functions, but
   RxNav types still imported across the code.
3. **Anti-Corruption Layer** — a dedicated module with its own types,
   translating at the boundary into `pharmacy.domain.Medication`.

## Decision Outcome

Chosen option: **Option 3 — Anti-Corruption Layer**.

Location: `services/pharmacy/src/pharmacy/infrastructure/drug_catalog/`.
Contract: a single interface `DrugCatalog` with methods
`get_medication(ndc_or_name) -> Medication` and `list_interactions(a, b)
-> list[Interaction]`, expressed in *our* types. Two implementations:

- `RxNavDrugCatalog` — calls RxNav via `httpx`, maps responses.
- `InMemoryDrugCatalog` — used in tests and in air-gapped demos;
  keeps a curated slice of the formulary.

No RxNav type ever crosses the ACL boundary.

### Positive Consequences
- The domain is stable even if RxNav adds / removes fields.
- We can pivot to a Zimbabwean / African formulary without changing
  the domain.
- Unit tests on Pharmacy aggregates use `InMemoryDrugCatalog`; RxNav
  is integration-tested separately.
- Demonstrates the pattern in a realistic way (against a *real*
  public API, not a toy).

### Negative Consequences
- Maintenance: when RxNav adds a clinically relevant field, we must
  explicitly surface it through our ACL. Accepted trade — intentional
  gate, not drift.
- Small performance overhead of the translation layer — negligible.

## Pros and Cons of the Options

### Direct client
- Good, because zero layering.
- Bad, because RxNav's shape becomes our shape. Upstream schema
  changes become our schema changes.

### Thin mapper
- Good, because cheap.
- Bad, because RxNav types still travel across modules unless we are
  vigilant — and we will not always be.

### Anti-Corruption Layer
- Good, because the boundary is physical: our types, their types, a
  translator in between.
- Good, because the implementation can be swapped at runtime via the
  `DrugCatalog` port.
- Bad, because writing the translation is real work.

## Links
- Evans 2003, *DDD*, ch. 14 — "Anti-Corruption Layer".
- RxNav REST API — <https://rxnav.nlm.nih.gov/>.
- ADR-0006.
