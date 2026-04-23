# ADR-0013 — AI Clinical Copilot behind a Provider Port

- Status: Accepted
- Date: 2026-04-21
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: ai, hexagonal-architecture, clinical-safety, innovation

## Context and Problem Statement

SmartClinic targets under-resourced Zimbabwean private clinics where doctors
handle high volumes of patients. Two high-friction tasks recur in every
consultation:

1. **SOAP note authoring** — the structured format (Subjective, Objective,
   Assessment, Plan) is clinically valuable but time-consuming to write from
   scratch when vitals and presenting complaint are already in the system.
2. **Drug-safety communication** — the Specification chain (ADR-0006) produces
   machine-readable violation strings that are precise but not immediately
   actionable by a non-pharmacist doctor who needs to substitute a drug.

Introducing an AI language model for these tasks creates three tension points:

- **Domain integrity**: LLM output must never be mistaken for a verified
  clinical fact and must not enter the hash-chained event store (ADR-0012).
- **Provider lock-in**: the Anthropic API is the best fit today but models
  evolve quickly; the cost of switching must be near zero.
- **Safety**: the AI is advisory. A licensed clinician must explicitly
  accept or discard each suggestion; the system must log both actions.

## Decision Drivers

- Domain freedom from external dependencies (ubiquitous language principle).
- Swappability: change the AI provider without touching domain or application
  code.
- Auditability: every AI-generated suggestion and every clinician decision
  must be logged.
- Graceful degradation: the system must function fully when no API key is
  configured.

## Considered Options

1. **Direct Anthropic SDK calls inside command handlers** — fast to write,
   but imports `anthropic` into the application layer and couples the domain
   test suite to network availability.
2. **AI suggestion as a Domain Event** stored in `clinical_events` — the
   event-sourced record then contains non-deterministic, non-clinical AI text;
   violates the medico-legal integrity invariant of ADR-0012.
3. **Separate `ai_suggestions` table + Provider Port** (this decision) —
   the domain and application layers depend only on an abstract
   `ClinicalCopilotPort`; the concrete adapter is injected at startup.
4. **External AI microservice** — avoids any coupling, but adds a network
   hop and a new deployed service for a feature that is fundamentally
   presentation-layer.

## Decision Outcome

Chosen option: **Option 3 — Provider Port + separate audit table**.

### Structure

```
shared_kernel/ai/
  copilot_port.py        ← ClinicalCopilotPort (abstract), AISuggestion (VO)
                           MockClinicalCopilot, AnthropicClinicalCopilot
                           build_copilot() factory

services/clinical/infrastructure/orm.py
  AISuggestionRecord     ← audit table (NOT in clinical_events)

services/clinical/application/handlers.py
  DraftSOAPNoteHandler   ← reads event stream, calls port, persists record
  ExplainDrugSafetyHandler
  RecordAIDecisionHandler

services/clinical/api/routes.py
  POST /encounters/{id}/ai/soap-draft
  POST /encounters/{id}/ai/drug-safety
  POST /encounters/ai/suggestions/{id}/decision
```

The `ClinicalCopilotPort` defines two methods:

```python
async def draft_soap_note(
    presenting_complaint: str,
    vitals: dict,
    existing_diagnoses: list[str] | None,
) -> AISuggestion

async def explain_drug_safety(
    drug_names: list[str],
    spec_failure_reasons: list[str],
) -> AISuggestion
```

`AISuggestion` is a frozen dataclass carrying `text`, `model_id`,
`generated_at`, and `disclaimer`. It is a Value Object: the domain accepts
it but never stores it in `clinical_events`.

### Provider selection at startup

```python
def build_copilot() -> ClinicalCopilotPort:
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicClinicalCopilot()   # claude-haiku-4-5-20251001
    return MockClinicalCopilot()            # deterministic stub, no API key
```

Switching to a different model or provider requires changing one line.

### Audit separation

AI suggestions are stored in `ai_suggestions`, a table with its own schema,
never joined with `clinical_events`. The `decision` column records
`"accepted"` or `"discarded"` when the clinician acts. This means:

- A medical audit of `clinical_events` is clean: it contains only verified
  clinical facts.
- A compliance audit of `ai_suggestions` answers: who requested AI assistance,
  which model was used, and whether the suggestion was adopted.

### Frontend contract

- A prominent disclaimer badge labels every AI suggestion as
  *non-authoritative and subject to clinician review*.
- The Accept / Discard buttons are always visible; the decision is posted to
  `RecordAIDecisionHandler` synchronously.
- The AI SOAP panel only renders for `in_progress` encounters and `doctor`
  role — it is invisible to receptionists, pharmacists, and lab techs.

### Positive Consequences

- The domain and application layers have zero dependency on `anthropic` or
  any HTTP client.
- Swapping to OpenAI, Mistral, or a self-hosted Ollama model is a one-class
  change confined to the shared kernel's `ai/` package.
- The mock adapter makes unit tests and CI deterministic.
- `ai_suggestions` creates a compliance artefact that would satisfy a HIPAA /
  WHO AI audit trail requirement.

### Negative Consequences

- Two database writes per AI call (suggestion record + optional decision
  record) — negligible.
- `AnthropicClinicalCopilot` has a cold-start import check; if the
  `anthropic` package is absent the factory falls through to mock silently —
  a warning log would improve visibility.
- AI suggestions read from the event store projection, not a purpose-built
  query — means the handler re-reads events already read by the domain
  aggregate. Acceptable for a low-frequency feature; a dedicated read model
  could be added if latency becomes an issue.

## Quantified Trade-offs

| Concern | Option 1 (direct) | Option 3 (port) |
|---|---|---|
| Lines to swap provider | ~50 (scattered) | 1 (factory) |
| Unit-testable without API | No | Yes (mock) |
| Domain/application imports `anthropic` | Yes | No |
| AI text in medico-legal event store | Risk (accidental) | Impossible by design |
| Audit trail of suggestions | None | Full (table + decision) |
| Graceful degradation without key | No | Yes (mock fallback) |

## Alternatives Considered

**Option 2 — AI as domain event**: rejected because it pollutes the
hash-chained `clinical_events` table with non-deterministic, non-clinical
text generated by a third-party service. This would break the tamper-evidence
guarantee of ADR-0012 (a verified chain that includes LLM output is not a
credible medico-legal record) and would require the `verify_chain` endpoint
to acknowledge AI-authored events as equal to physician-authored facts.

**Option 4 — Separate AI microservice**: rejected because the feature is
presentation-layer (read event data, call API, return text). An extra service
adds DevOps overhead and a network hop for a feature that adds no bounded
context invariant of its own. The Port pattern achieves the same decoupling
within the Clinical service's process.

## Links

- ADR-0006 — Specification Pattern (whose violation reasons feed `explain_drug_safety`)
- ADR-0007 — Anti-Corruption Layer (same principle: domain never imports provider SDK)
- ADR-0012 — Hash-chained event store (why AI text cannot enter `clinical_events`)
- Ports and Adapters — Alistair Cockburn, 2005
