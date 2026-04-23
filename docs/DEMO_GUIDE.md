# SmartClinic — Complete Demo & Assessment Guide

**Project:** SmartClinic Electronic Health Record  
**Course:** Masters in Software Engineering — Software Architecture  
**University of Zimbabwe**  
**Author:** Samson Fukuzeya  

---

## Table of Contents

1. [System Startup](#1-system-startup)
2. [Login Credentials — All Roles](#2-login-credentials--all-roles)
3. [Platform Walkthrough — Start to End](#3-platform-walkthrough--start-to-end)
4. [Feature Demonstrations by Role](#4-feature-demonstrations-by-role)
5. [Architecture Achievements](#5-architecture-achievements)
6. [Marking Scheme Alignment](#6-marking-scheme-alignment)
7. [Seeded Demo Data Reference](#7-seeded-demo-data-reference)
8. [Observability & Infrastructure](#8-observability--infrastructure)

---

## 1. System Startup

### Prerequisites
- Docker Desktop installed and running
- Git clone of the SmartClinic repository

### Start the Full Stack

```bash
# Start all services (first time takes ~3 minutes to pull images)
make up

# Verify all services are healthy
make health

# Seed the demo database with 7 patients and all scenario paths
make seed
# or directly:
python ops/seed/seed.py
```

### Services started by `make up`

| Service | URL | Purpose |
|---|---|---|
| Angular Frontend | http://localhost:4200 | Main application UI |
| Patient Identity | http://localhost:8001/docs | Patient registration API |
| Scheduling | http://localhost:8002/docs | Appointments API |
| Clinical | http://localhost:8003/docs | Encounters, SOAP, prescriptions API |
| Pharmacy | http://localhost:8004/docs | Dispensing API |
| Laboratory | http://localhost:8005/docs | Lab orders & results API |
| Billing | http://localhost:8006/docs | Invoicing API |
| Saga Orchestrator | http://localhost:8007 | Visit lifecycle coordinator |
| Keycloak (OIDC) | http://localhost:8080 | Identity & access management |
| RabbitMQ Management | http://localhost:15672 | Event bus (admin/admin) |
| Grafana | http://localhost:3000 | Metrics & observability (admin/admin) |
| Prometheus | http://localhost:9090 | Metrics scraping |
| Jaeger | http://localhost:16686 | Distributed tracing |

---

## 2. Login Credentials — All Roles

Navigate to **http://localhost:4200** and click **Sign In** on the login screen.

| Role | Username | Password | Access |
|---|---|---|---|
| **Receptionist** | `recep1` | `recep1` | Patient registration, appointments, check-in |
| **Doctor** | `doctor1` | `doctor1` | Encounters, SOAP notes, prescriptions, lab orders |
| **Pharmacist** | `pharm1` | `pharm1` | Prescription dispensing, pharmacy stock |
| **Lab Technician** | `lab1` | `lab1` | Lab order processing, sample collection, results |
| **Accounts Clerk** | `acct1` | `acct1` | Invoice management, payment recording |

> All users are pre-configured in Keycloak realm `smartclinic`. Passwords match usernames for demo convenience.

### What each role sees

**Receptionist (`recep1`):**
- Full patient list with search and pagination
- "Register Patient" button visible
- Appointments list with date filter and "Book Appointment" button
- Can check in, cancel, and rebook appointments
- Read access to invoices (no payment recording)

**Doctor (`doctor1`):**
- Patient list (read only — cannot register)
- Appointments list (own schedule)
- Encounters list with full SOAP, diagnosis, prescription, lab order entry
- AI Clinical Copilot (SOAP note draft + drug safety explanation)
- Read access to prescriptions and lab orders

**Pharmacist (`pharm1`):**
- Prescriptions list — pending, partially dispensed, completed
- Per-prescription dispensing workspace with specification check panel
- AI Drug Safety Explanation button on rejected prescriptions
- Drug stock management

**Lab Technician (`lab1`):**
- Lab orders list with status filter
- Per-order workflow: collect sample → record results → complete
- Results entry with interpretation fields

**Accounts Clerk (`acct1`):**
- Invoices list with status filter
- Per-invoice: issue, add charges, record payment
- Balance summary view

---

## 3. Platform Walkthrough — Start to End

This walkthrough follows **Patient: Chipo Moyo** through her complete visit using all 5 roles.

### Step 1 — Receptionist: Register Patient

1. Login as `recep1` / `recep1`
2. Navigate to **Patients** → click **Register Patient**
3. Fill in patient details:
   - Name: Chipo Moyo
   - Date of birth: 12 Apr 1985
   - Sex: Female
   - National ID: 63-123456A-75
   - Phone: +263771234567
   - Medical Aid: CIMAS / Executive Plan
4. Submit → patient record created in Patient Identity bounded context

### Step 2 — Receptionist: Book Appointment

1. Navigate to **Appointments** → **Book Appointment**
2. Select patient: Chipo Moyo
3. Select doctor: Dr. Doctor1
4. Choose date/time and reason: "Mild chest tightness"
5. Save → appointment created in Scheduling bounded context

### Step 3 — Receptionist: Check In Patient

1. On today's appointment list, find Chipo Moyo
2. Click **View** → **Check In**
3. Status changes from `booked` → `checked_in`
4. The Saga Orchestrator is now tracking this visit

### Step 4 — Doctor: Start Encounter

1. **Sign out** → login as `doctor1` / `doctor1`
2. Navigate to **Appointments** → find Chipo Moyo's checked-in slot
3. Click **View** → **Start Encounter**
4. An encounter is created in the Clinical bounded context
5. A domain event `clinical.encounter.started.v1` is published to RabbitMQ

### Step 5 — Doctor: Record Vitals

1. In the encounter detail → **Record Vital Signs**
2. Enter: Temperature, Blood Pressure, Pulse, SpO2, Weight, Height
3. Submit → `clinical.encounter.vital_signs_recorded.v1` event published

### Step 6 — Doctor: AI SOAP Copilot

1. In the encounter detail, scroll to the **AI Clinical Copilot** panel
2. Click **Draft SOAP Note**
3. The system calls Claude AI (ADR 0013 — AI Provider Port pattern)
4. A structured SOAP note draft appears with a disclaimer banner
5. Clinician reviews and clicks **Accept into SOAP** or **Discard**
6. The decision is recorded for audit (AI accountability)

### Step 7 — Doctor: Add SOAP Note (manual or AI-assisted)

1. In the encounter → **SOAP Notes** section → fill in or accept AI draft:
   - **S**ubjective: Patient complaint
   - **O**bjective: Examination findings
   - **A**ssessment: Diagnosis reasoning
   - **P**lan: Treatment plan
2. Submit → `clinical.encounter.soap_note_added.v1` event

### Step 8 — Doctor: Record Diagnosis

1. In encounter → **Diagnoses** → **Add Diagnosis**
2. Enter ICD-10 code (e.g., `J20.9`) and description
3. Mark as primary diagnosis
4. Submit → `clinical.encounter.diagnosis_recorded.v1` event

### Step 9 — Doctor: Issue Prescription

1. In encounter → **Prescriptions** → **Issue Prescription**
2. Add drug lines:
   - Drug name, dose, route, frequency, duration, instructions
3. Submit → `clinical.encounter.prescription_issued.v1` event published
4. **Pharmacy context** receives this event via RabbitMQ → creates a pending prescription record

### Step 10 — Doctor: Place Lab Order

1. In encounter → **Lab Orders** → **Place Lab Order**
2. Add tests: FBC, CRP
3. Submit → `clinical.encounter.lab_order_placed.v1` event published
4. **Laboratory context** receives this event → creates a pending lab order

### Step 11 — Doctor: Close Encounter

1. Click **Close Encounter**
2. `clinical.encounter.closed.v1` event published
3. **Billing context** receives this event → automatically creates a draft invoice
4. The Patient Visit Saga marks this visit stage as complete

### Step 12 — Pharmacist: Dispense Prescription

1. **Sign out** → login as `pharm1` / `pharm1`
2. Navigate to **Prescriptions** → find Chipo Moyo's pending prescription
3. Click **View** → see the **Dispensing Actions** panel
4. Click **Dispense All (run spec check)**
5. The system runs the **Specification Chain**:
   - `AllDrugsInStock ∧ PatientConsentGranted ∧ NoSevereDrugInteraction`
6. If all specs pass → prescription dispensed
7. If any spec fails → rejection details shown + AI Explain Safety button available

### Step 13 — Lab Technician: Process Lab Order

1. **Sign out** → login as `lab1` / `lab1`
2. Navigate to **Lab Orders** → find Chipo Moyo's pending order
3. Click **View**:
   - Click **Collect Sample** → enter sample type (blood)
   - Click **Record Result** for each test → enter value, unit, interpretation
   - Click **Complete Order**
4. `laboratory.order.completed.v1` event published
5. Doctor can now review results in the encounter

### Step 14 — Accounts Clerk: Issue Invoice & Record Payment

1. **Sign out** → login as `acct1` / `acct1`
2. Navigate to **Invoices** → find Chipo Moyo's draft invoice
3. Click **View** → **Issue Invoice** (changes status to `issued`)
4. Click **Record Payment**:
   - Amount: 18.00 USD
   - Method: Cash
   - Reference: REC-CH001
5. Invoice status changes to `paid`

> **The complete patient visit journey is now done.** All 6 bounded contexts participated via domain events — no direct service-to-service HTTP calls.

---

## 4. Feature Demonstrations by Role

### 4.1 Out-of-Stock Saga Compensation (Patient: Tendai Dube)

**Scenario:** Warfarin prescribed but not in stock.

1. Login as `pharm1`
2. Go to **Prescriptions** → find Tendai Dube's pending prescription
3. Click **Dispense All**
4. The `AllDrugsInStock` specification fires → **REJECTED**
5. Rejection reasons show: "Warfarin not in stock"
6. Out-of-stock saga compensation fires:
   - Saga Orchestrator receives `pharmacy.prescription.out_of_stock.v1`
   - Sends notification event to Clinical context
   - Doctor receives alert to prescribe substitute
7. Click **AI: Explain safety concern** → Claude AI explains the clinical implications
8. Pharmacist reviews AI narrative, clicks **Noted** or **Dismiss**

### 4.2 Drug Interaction Detection (Patient: Farai Mutasa)

1. Login as `pharm1`
2. Find Farai Mutasa's prescription (Aspirin + Ibuprofen)
3. Attempt dispense → `NoSevereDrugInteraction` spec queries RxNav ACL
4. If interaction found → rejected with clinical reason
5. AI Drug Safety Explanation available

### 4.3 Hash-Chained Audit Trail (Any encounter)

1. Login as `doctor1`
2. Open any encounter → click **Timeline** tab
3. Each event shows:
   - Timestamp, actor, event type
   - **Chain hash** (SHA-256 of previous hash + event payload)
   - **Sequence number**
4. Green ✓ badge = chain intact; Red ✗ = tampering detected
5. This is ADR 0012 — every event is a forensic record

### 4.4 AI Clinical Copilot — SOAP Draft (Any encounter)

1. Login as `doctor1`
2. Open an encounter with vitals recorded
3. Scroll to **AI Clinical Copilot** panel → click **Draft SOAP Note**
4. Shows: disclaimer, structured SOAP text, model ID, generation timestamp
5. Clinician must explicitly Accept or Discard — mandatory human oversight

### 4.5 Cancelled Appointment (Patient: Tatenda Banda)

1. Login as `recep1`
2. Go to **Appointments** → find Tatenda Banda's cancelled appointment
3. Status shows `cancelled`
4. A rebooked appointment for next day is also visible
5. Demonstrates the cancel/rebook workflow

---

## 5. Architecture Achievements

### 5.1 Domain-Driven Design — 6 Bounded Contexts

Each bounded context is a separate microservice with its own:
- PostgreSQL schema
- Domain model and ubiquitous language
- Published Language (events)
- API

| Context | Port | Core Aggregate | Key Events |
|---|---|---|---|
| Patient Identity | 8001 | `Patient` | `patient.registered.v1`, `patient.consent.updated.v1` |
| Scheduling | 8002 | `Appointment` | `appointment.booked.v1`, `appointment.checked_in.v1` |
| Clinical | 8003 | `Encounter` | `encounter.started.v1`, `encounter.closed.v1`, `prescription.issued.v1` |
| Pharmacy | 8004 | `Prescription` | `prescription.dispensed.v1`, `prescription.out_of_stock.v1` |
| Laboratory | 8005 | `LabOrder` | `lab_order.completed.v1` |
| Billing | 8006 | `Invoice` | `invoice.issued.v1`, `invoice.paid.v1` |

### 5.2 Event Sourcing (Clinical Context)

The Clinical bounded context stores **every state change as an immutable event**:

```
Event Store (PostgreSQL):
  encounter_id | seq | event_type                              | payload | prev_hash | hash
  enc-001      | 1   | clinical.encounter.started.v1           | {...}   | null      | sha256(...)
  enc-001      | 2   | clinical.encounter.vital_signs.v1       | {...}   | hash-1    | sha256(...)
  enc-001      | 3   | clinical.encounter.soap_note_added.v1   | {...}   | hash-2    | sha256(...)
```

- No mutable `UPDATE` statements in the event store
- Current state is a **projection** rebuilt from the event stream
- ADR 0003 — Event Sourcing for Clinical Context
- ADR 0012 — Hash-chained tamper-evident event store

### 5.3 CQRS (Clinical and Billing)

**Command side:** Domain commands → aggregate → domain events → event store  
**Query side:** Read-optimised projection tables populated by event handlers

```
Write:  POST /encounters/{id}/diagnoses
        → RecordDiagnosisCommand → EncounterAggregate → DiagnosisRecordedEvent → event_store

Read:   GET /encounters/{id}
        → encounter_projection table (denormalised, fast reads)
```

- ADR 0004 — CQRS for Clinical and Billing

### 5.4 Patient Visit Saga (Orchestration)

The Saga Orchestrator (port 8007) coordinates the multi-context patient visit lifecycle:

```
Appointment.CheckedIn
    → Start Encounter (Clinical)
    → [Doctor records vitals, SOAP, diagnosis, prescriptions, lab orders]
    → Encounter.Closed
        → Create Invoice (Billing)        [conformist consumer]
        → Accept Lab Orders (Laboratory)  [conformist consumer]
        → Accept Prescriptions (Pharmacy) [conformist consumer]
    → [Pharmacy dispenses or OOS compensation fires]
    → [Lab processes results]
    → [Billing records payment]
    → Visit Complete
```

**Compensation (OOS path):**
```
Pharmacy.OutOfStock
    → Saga sends SubstituteRequested event → Clinical context
    → Doctor receives notification to prescribe alternative
```

- ADR 0005 — Saga for Patient Visit Lifecycle

### 5.5 Specification Pattern (Pharmacy)

The dispense operation applies a **logical AND of three specifications**:

```python
AllDrugsInStock(drug_names, stock_repository)
    ∧ PatientConsentGranted(patient_id, consent_repository)
    ∧ NoSevereDrugInteraction(drug_names, rxnav_acl)
```

Each specification is a standalone, composable, testable predicate:
- Satisfiable → dispense proceeds
- Not satisfied → rejection with specific reason per spec

- ADR 0006 — Specification Pattern in Pharmacy

### 5.6 Anti-Corruption Layer — RxNav Drug Database

The `NoSevereDrugInteraction` specification does **not** call RxNav directly. Instead, it goes through an ACL:

```
Domain code → DrugInteractionPort (interface)
                    ↓
              RxNavAdapter (ACL)
                    ↓
              RxNav REST API (external)
```

- Domain model is insulated from RxNav's schema and terminology
- The ACL translates `drug_names[]` → RxNav concept IDs → interaction check → domain result
- ADR 0007 — Anti-Corruption Layer for Drug Database

### 5.7 Hash-Chained Tamper-Evident Event Store

Every event written to the clinical event store is chained:

```python
hash_n = sha256(hash_{n-1} + json(event_payload))
```

- If any event is deleted or modified, all subsequent hashes break
- The `/encounters/{id}/events` endpoint returns the chain
- The frontend Timeline component verifies the chain and shows a green ✓ or red ✗ badge
- ADR 0012 — Hash-chained tamper-evident event store

### 5.8 AI Clinical Copilot — Provider Port Pattern

The AI integration follows the **Ports & Adapters (Hexagonal) architecture**:

```
Doctor → AISoapCopilotComponent
              ↓
         EncounterService.draftSoapNote()
              ↓  HTTP
         POST /encounters/{id}/ai/soap-draft
              ↓
         ClaudeAIAdapter  ←→  AISuggestionPort (interface)
              ↓
         Claude API (claude-haiku-4-5)
```

- Swapping AI providers requires only a new adapter — no domain code changes
- Every AI suggestion is stored with: `suggestion_id`, `model_id`, `generated_at`, `disclaimer`
- Clinician `accepted` / `discarded` decision is persisted for audit
- ADR 0013 — AI Clinical Copilot Provider Port

### 5.9 Keycloak OIDC RBAC

```
JWT Bearer Token → shared_kernel.fastapi.dependencies
    → require_role("doctor")     # exact role
    → require_any_role("a","b")  # any of
    → get_current_principal()    # subject + roles
```

- All API endpoints are protected by role annotations
- Frontend uses `AuthService.isDoctor()`, `.isReceptionist()` etc. to conditionally render UI
- ADR 0011 — Keycloak OIDC for RBAC

### 5.10 Transactional Outbox / Inbox Pattern

Events are NOT published directly from domain handlers. Instead:

```
Domain Handler → write event_store row + outbox row (same DB transaction)
Outbox Relay   → poll outbox → publish to RabbitMQ → mark sent
Inbox Handler  → consume from RabbitMQ → idempotent insert → process command
```

- Guarantees at-least-once delivery even if RabbitMQ is temporarily down
- Idempotency keys prevent duplicate processing
- ADR 0009 — Transactional Outbox and Inbox

---

## 6. Marking Scheme Alignment

### DDD Fundamentals

| Requirement | Implementation | Where to See |
|---|---|---|
| Bounded contexts with own language | 6 microservices, each with `/domain/` package | `services/*/src/*/domain/` |
| Aggregate roots with invariants | `Encounter`, `Prescription`, `Invoice`, `LabOrder` aggregates | `domain/*.py` in each service |
| Domain events | 20+ named events (v1 versioned) | `domain/events.py` per service |
| Ubiquitous language | `docs/ubiquitous-language.md` | All entity names match domain vocabulary |
| Value objects | `Money`, `PatientId`, `DrugLine`, `VitalSigns` | `domain/value_objects.py` |
| Context map | Conformist, ACL, Shared Kernel relationships | `docs/context-map.md` |
| Repository pattern | Abstract `IEncounterRepository` → SQLAlchemy impl | `infrastructure/repository.py` |

### Architectural Patterns

| Pattern | ADR | Where to Demo |
|---|---|---|
| Event Sourcing | ADR 0003 | Clinical encounter timeline with chain hashes |
| CQRS | ADR 0004 | GET /encounters uses projection, POST uses command |
| Saga Orchestration | ADR 0005 | Tendai Dube OOS path — watch saga_orchestrator logs |
| Specification Pattern | ADR 0006 | Pharmacist dispense — spec chain result panel |
| Anti-Corruption Layer | ADR 0007 | RxNav adapter in pharmacy service |
| Outbox / Inbox | ADR 0009 | RabbitMQ messages arriving after encounter close |
| Hash-chained Audit | ADR 0012 | Encounter timeline chain verification badge |
| AI Provider Port | ADR 0013 | AI Copilot with accept/discard audit |

### Quality Attributes

| Attribute | Evidence |
|---|---|
| **Security** | Keycloak OIDC, role-gated every endpoint, JWT validation |
| **Auditability** | Hash-chained event store, AI decision logging, immutable events |
| **Availability** | Transactional outbox for event delivery resilience |
| **Maintainability** | Shared kernel with governed cross-service types |
| **Testability** | Domain layer has zero framework dependencies; unit tests in `tests/domain/` |
| **Observability** | Prometheus metrics, Jaeger traces, structured JSON logs |

### Architecture Decision Records

All 13 ADRs are in `docs/adr/`:

| ADR | Decision |
|---|---|
| 0001 | Use ADRs for architecture decisions |
| 0002 | Bounded contexts as microservices |
| 0003 | Event sourcing for clinical context |
| 0004 | CQRS for clinical and billing |
| 0005 | Saga for patient visit lifecycle |
| 0006 | Specification pattern in pharmacy |
| 0007 | Anti-corruption layer for drug database |
| 0008 | RabbitMQ as event bus |
| 0009 | Transactional outbox and inbox |
| 0010 | Shared kernel scope and governance |
| 0011 | Keycloak OIDC for RBAC |
| 0012 | Hash-chained tamper-evident event store |
| 0013 | AI clinical copilot provider port |

---

## 7. Seeded Demo Data Reference

After running `make seed`, the following data is available:

### Patients

| # | Name | DOB | Sex | Medical Aid | Scenario |
|---|---|---|---|---|---|
| 1 | Chipo Moyo | 12 Apr 1985 | F | CIMAS Executive | Full happy path — dispensed, lab complete, invoice paid |
| 2 | Tendai Dube | 30 Nov 1962 | M | None (self-pay) | OOS saga compensation — Warfarin not in stock |
| 3 | Rudo Nhamo | 20 Jul 1990 | F | PSMAS Standard | Lab results complete — HbA1c high (DM review) |
| 4 | Farai Mutasa | 05 Mar 1978 | M | CIMAS Classic | Drug interaction — Aspirin + Ibuprofen |
| 5 | Nyasha Chirwa | 14 Sep 1995 | F | None (self-pay) | UTI — dispensed, paid |
| 6 | Tatenda Banda | 25 Dec 2000 | M | None (self-pay) | Cancelled appointment + rebooked |
| 7 | Simba Ncube | 10 Jun 2018 | M | ZESA Basic | Paediatric pneumonia — full journey complete |

### Appointments (all on 22 Apr 2026)

| Time | Patient | Type | Status |
|---|---|---|---|
| 09:00 | Chipo Moyo | consultation | checked_in |
| 10:00 | Tendai Dube | consultation | checked_in |
| 11:00 | Rudo Nhamo | consultation | checked_in |
| 11:30 | Farai Mutasa | consultation | checked_in |
| 13:00 | Nyasha Chirwa | consultation | checked_in |
| 14:00 | Tatenda Banda | consultation | **cancelled** |
| 14:30 | Simba Ncube | paediatric | checked_in |
| 09:30 (23 Apr) | Tatenda Banda | consultation | booked (rebooked) |

### Prescription Status After Seed

| Patient | Drug(s) | Status |
|---|---|---|
| Chipo Moyo | Salbutamol Inhaler, Paracetamol | **dispensed** |
| Tendai Dube | Warfarin | **pending** (will fail on dispense — OOS demo) |
| Rudo Nhamo | Metformin, Lisinopril | **dispensed** |
| Farai Mutasa | Amlodipine, Aspirin, Ibuprofen | **pending** (interaction demo) |
| Nyasha Chirwa | Ciprofloxacin, Ibuprofen | **dispensed** |
| Simba Ncube | Amoxicillin, Paracetamol | **dispensed** |

### Lab Order Status After Seed

| Patient | Tests | Status |
|---|---|---|
| Chipo Moyo | FBC, CRP | **completed** (results in system) |
| Rudo Nhamo | HbA1c, U&E, LFT, Lipids | **completed** (high HbA1c for DM demo) |
| Nyasha Chirwa | UMCS | **pending** (awaiting lab tech) |
| Simba Ncube | FBC, CXR | **completed** (neutrophilia + consolidation) |

### Invoice Status After Seed

| Patient | Amount | Method | Status |
|---|---|---|---|
| Chipo Moyo | $18.00 | Cash | **paid** |
| Rudo Nhamo | $32.00 | PSMAS Medical Aid | **paid** |
| Farai Mutasa | — | — | **issued** (awaiting payment) |
| Nyasha Chirwa | $15.00 | Cash | **paid** |
| Simba Ncube | $22.00 | ZESA Medical Aid | **paid** |
| Tendai Dube | — | — | **draft** |

---

## 8. Observability & Infrastructure

### RabbitMQ — Event Bus

Open http://localhost:15672 (admin / admin)

- **Exchanges:** `smartclinic.events` (topic exchange)
- **Queues:** one per bounded context consumer (`billing.events`, `pharmacy.events`, etc.)
- **Routing keys:** `clinical.encounter.*`, `pharmacy.prescription.*`, etc.
- Watch message rates spike when running `make seed`

### Grafana — Metrics Dashboard

Open http://localhost:3000 (admin / admin)

- **HTTP request rate** per service
- **Event publish/consume rate** per context
- **Database query latency**
- **Error rate and 4xx/5xx breakdown**

### Jaeger — Distributed Tracing

Open http://localhost:16686

- Select service (e.g., `clinical`) and search recent traces
- Drill into a `POST /encounters/{id}/prescriptions` trace to see:
  - Database writes
  - Outbox insertion in same transaction
  - RabbitMQ publish confirmation

### Audit Trail Query (direct SQL)

```sql
-- Connect to clinical database (postgres:5432)
SELECT seq, event_type, actor, occurred_at, hash, prev_hash
FROM clinical_event_store
WHERE aggregate_id = '<encounter_id>'
ORDER BY seq;
```

Verify chain: each `hash` = SHA-256(`prev_hash` + `payload`).

---

## Quick Reference — Demo Flow for Assessment

```
1. make up && make seed

2. recep1  →  Register patient  →  Book appointment  →  Check in
3. doctor1        →  Start encounter  →  Vitals  →  AI SOAP draft  →  Diagnose
                  →  Prescribe  →  Lab order  →  Close encounter
4. pharm1    →  View prescription  →  Run spec check  →  Dispense
                  (or demonstrate OOS compensation with Tendai Dube)
5. lab1           →  Collect sample  →  Record results  →  Complete order
6. acct1      →  Issue invoice  →  Record payment

Key demo points to highlight:
  ✓  Events in RabbitMQ after each step (show exchanges/queues)
  ✓  Hash chain on encounter timeline (green ✓ badges)
  ✓  Specification pattern panel in pharmacy dispensing view
  ✓  AI Copilot with disclaimer + accept/discard audit
  ✓  Invoice auto-created from domain event (no direct API call from Clinical → Billing)
  ✓  Each bounded context has its own database schema (show pgAdmin)
  ✓  13 ADRs documenting every significant architectural decision
```
