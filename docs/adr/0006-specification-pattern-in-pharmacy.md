# ADR-0006 — Specification Pattern in Pharmacy

- Status: Accepted
- Date: 2026-04-12
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: tactical-ddd, specification, pharmacy

## Context and Problem Statement

When a prescription arrives at Pharmacy, the pharmacist (code) must
evaluate a number of business rules before dispensing:

- Does the patient have a known allergy to any ingredient?
- Is there a pharmacologically significant interaction with any
  existing prescription?
- Does dispensing exceed a scheduled-substance quota?
- Is stock available?

These rules are **composable** (an interaction can be allergy-based OR
pharmacological), they **change** (the interaction list is
data-driven), and they must produce **explanatory output** — "rejected
because X" is shown to the pharmacist in the UI.

Ad-hoc `if`-soup has obvious problems: untestable, uncomposable, and
the rules scatter across handlers.

## Decision Drivers

- Rules must compose (AND, OR, NOT).
- Rules must explain *why* they are (not) satisfied.
- Rules must be unit-testable in isolation.
- The domain language the pharmacist uses is itself specification-
  shaped: "dispensable if-and-only-if no-allergy AND no-interaction AND
  stock-available".
- The marking scheme rewards the Specification pattern.

## Considered Options

1. **Inline `if` expressions** in the command handler.
2. **Rule engine** (e.g., Python durable-rules).
3. **Specification Pattern** (Evans 2003 / Fowler) implemented in
   the Shared Kernel.

## Decision Outcome

Chosen option: **Option 3 — Specification Pattern**.

Base in Shared Kernel: `Specification[T]` with `is_satisfied_by`,
`__and__`, `__or__`, `__invert__`, `assert_satisfied_by`, and an
`explain()` method that yields human-readable reasons for failure.
Pharmacy composes domain-specific specs from it:
`HasAllergyInteraction`, `HasPharmacologicalInteraction`,
`ExceedsScheduledSubstanceQuota`, `HasStockAvailable`.

### Positive Consequences
- Rules are pure, deterministic functions → trivial to unit-test.
- Composition lets us express the business rule declaratively:
  ```python
  dispensable = HasStockAvailable() & ~(HasAllergyInteraction() | HasPharmacologicalInteraction())
  ```
- `explain()` output powers the UI: `pharmacy.dispensing.rejected.v1`
  carries a list of reasons, not a generic "rejected".
- New rules are a new class — no modification to existing handlers
  (Open/Closed).

### Negative Consequences
- Another layer of abstraction — trivial rules could have stayed
  inline. We restrict use to the dispensing decision specifically.
- Performance: composed specs evaluate eagerly. For the dispensing
  decision (single-digit specs) this is a non-issue; for something
  bulk-batch we would revisit.

## Pros and Cons of the Options

### Inline `if`
- Good, because zero overhead.
- Bad, because uncomposable and untestable in isolation.
- Bad, because the domain vocabulary stops at the handler boundary.

### Rule engine
- Good, because dynamic rules at runtime.
- Bad, because the rule grammar is *outside* Python's type system.
- Bad, because heavy for our scope.

### Specification Pattern
- Good, because aligns with DDD and is explicitly on the mark sheet.
- Good, because `explain()` is a direct UX win.
- Bad, because the ergonomics cost a little boilerplate.

## Quantified Trade-offs

| Attribute | Inline `if` | Rule engine | **Specification Pattern** (chosen) |
|---|---|---|---|
| Lines to add a new dispensing rule | ~15 (handler edit) | ~10 (rule file) | ~25 (new class) |
| Unit-testable in isolation | No | Partially | Yes — pure function, no I/O |
| Composable with `&` / `\|` / `~` | No | Depends on grammar | Yes — operator overloads in base class |
| UI can display *which rule* failed | No — single boolean | Depends | Yes — `reasons_for_failure()` |
| External dependency | None | Rule engine package | None |
| Evaluation strategy | Eager (short-circuit varies) | Engine-specific | Eager by default; lazy via `LazyAnd` |

**Key win**: the `reasons_for_failure()` output feeds directly into the
`pharmacy.dispensing.rejected.v1` event payload and the Angular rejection
panel — a UX improvement that inline `if` cannot provide without significant
refactoring.

## Why not the alternatives?

**Inline `if`**: the dispensing decision has 3 composable rules today. The
business domain (*patient consent*, *stock check*, *interaction check*) makes
it clear that a 4th rule (e.g., allergy) will be added without modifying the
handler — which is exactly the Open/Closed Principle the Specification pattern
enforces. The first time a new pharmacist asks "why was this rejected?", inline
`if` produces `False` with no explanation.

**Rule engine (durable-rules, Drools-style)**: the rule grammar is a DSL
outside Python's type system. Mistyped attribute names silently produce wrong
evaluations at runtime. The marketing value ("configurable at runtime") is not
needed — our rules change quarterly at most and require a code review anyway.
The 50-line Specification base class in the Shared Kernel achieves the same
composability inside the type system with zero new dependencies.

## Links
- Evans 2003, *DDD*, ch. 9 "Making Implicit Concepts Explicit".
- Fowler, "Specifications" — <https://www.martinfowler.com/apsupp/spec.pdf>.
- ADR-0010 (Shared Kernel scope).
