# SmartClinic: Intelligent Clinic Management System
## Advanced Domain-Driven Design Patterns — Project Proposal
**Team:** TARUVINGA, KATONDO, FUKUZEYA
**Date:** April 2026
**Assessment:** Masters in Computer Science — Software Architecture Mini Project

---

## 1. Problem Statement

Private clinics in Zimbabwe operate with fragmented systems: appointments are disconnected from consultations, prescriptions are invisible to the pharmacy until the patient physically walks over, billing is done retroactively, and lab results are tracked on paper. This causes missed prescriptions, billing disputes, repeated tests, and patient safety risks.

The root cause is that clinic software is built as a monolith. In reality, clinic operations are a network of autonomous domains — each with its own language, rules, and lifecycle. A **"visit"** means a calendar slot to the receptionist, a clinical encounter to the doctor, a billable event to accounts, and a dispensing trigger to the pharmacist. This semantic mismatch is precisely the complexity that Domain-Driven Design was designed to tame.

**SmartClinic** is a prototype clinic management platform that demonstrates how Advanced DDD patterns decompose and coordinate this complexity through well-defined bounded contexts communicating via domain events.

---

## 2. What We Are Building

A working prototype covering the full patient visit lifecycle across **six bounded contexts**:

| Bounded Context | Responsibility |
|---|---|
| **Patient Identity** | Patient registration, demographics, medical aid information |
| **Scheduling** | Appointment booking, provider availability, conflict detection |
| **Clinical** | Consultation recording — vitals, ICD-10 diagnoses, prescriptions, lab orders |
| **Pharmacy** | Prescription dispensing, drug interaction checking, stock management |
| **Laboratory** | Lab test ordering and result recording |
| **Billing** | Auto-generated invoices from clinical services, payment processing, medical aid schemes |

The system is event-driven: when a doctor completes a consultation, domain events automatically trigger prescription fulfillment in Pharmacy, invoice generation in Billing, and patient notification — with each context operating independently and asynchronously.

---

## 3. Advanced DDD Patterns Demonstrated

| Pattern | Applied In | What It Shows |
|---|---|---|
| **Bounded Contexts** | All 6 contexts | Each domain has its own model, language, and database |
| **Context Map** | Cross-context design | All 6 DDD relationship types: Partnership, Customer-Supplier, Conformist, Anti-Corruption Layer, Shared Kernel, Published Language |
| **Aggregates + Invariants** | Encounter, Appointment, Invoice, Dispensing | Business rules enforced at the aggregate boundary (e.g., cannot issue prescription without a diagnosis) |
| **Event Sourcing** | Clinical Context | Full immutable audit trail of every encounter change — required for medico-legal compliance |
| **CQRS** | Clinical + Billing | Separate optimized read models (dashboards) from write models (enforcing invariants) |
| **Saga / Process Manager** | Patient Visit Saga | Orchestrates the full visit lifecycle across all contexts with compensating actions on failure |
| **Specification Pattern** | Pharmacy + Scheduling | Composable, testable business rules for drug interaction checks, dosage validation, and appointment conflict detection |
| **Anti-Corruption Layer** | Pharmacy ↔ Drug Database | Protects the clean domain model from external drug API format changes |
| **Domain Services** | DrugInteractionService, TariffCalculationService | Operations spanning multiple entities that don't belong to a single aggregate |
| **Value Objects** | ICD10Code, Dosage, Money, VitalReading | Immutable, self-validating domain concepts |

---

## 4. Technology Stack

| Layer | Technology |
|---|---|
| **Backend Services** | Python 3.12 + FastAPI (one service per bounded context) |
| **Frontend** | Angular 20 (role-based views: Receptionist, Doctor, Pharmacist, Billing) |
| **Event Store** | PostgreSQL (append-only events table with optimistic concurrency) |
| **Event Bus** | RabbitMQ (domain events routed between contexts) |
| **Databases** | PostgreSQL — one schema per bounded context |
| **Deployment** | Docker + Docker Compose (single `docker-compose up` command) |
| **Testing** | pytest — domain invariant unit tests + integration tests |

---

## 5. Implementation Plan (7 Days)

| Day | Deliverable |
|---|---|
| **Day 1** | Docker Compose environment, shared kernel (PatientId, Money value objects), all FastAPI service skeletons, domain model classes for Clinical and Scheduling |
| **Day 2** | Clinical Context — Event-sourced Encounter aggregate, command handlers, event store, CQRS read projections, domain invariant unit tests |
| **Day 3** | Pharmacy Context (Specification pattern, ACL), Billing Context (auto-invoice from events), Patient Visit Saga with compensation |
| **Day 4** | Angular 20 frontend — Receptionist, Doctor, Pharmacist, and Billing views; Event timeline component visualizing event sourcing |
| **Day 5** | Scheduling Context (conflict detection), Lab Context, end-to-end integration testing, Anti-Corruption Layer for mock drug database |
| **Day 6** | Architecture Decision Records (5 ADRs), Arc42 documentation, context map diagram, ubiquitous language glossary |
| **Day 7** | Demo rehearsal, final testing, presentation preparation |

---

## 6. Demo Highlights

- **Happy path:** Book appointment → Check in → Doctor records vitals + diagnosis + prescription → Pharmacist dispenses → Invoice auto-generated → Payment processed
- **Specification pattern in action:** Doctor prescribes two drugs with a severe interaction — system blocks issuance with a detailed violation message
- **Saga compensation:** Prescribed drug is out of stock — saga triggers compensating action, notifying the doctor for substitution
- **Event timeline:** Reconstruct the full history of any encounter from the event store, showing event sourcing and temporal queries live

---

## 7. Team Responsibilities

| Member | Role | Bounded Context |
|---|---|---|
| Member 1 | Architecture Lead — event storming, context mapping, cross-cutting design | Cross-cutting |
| Member 2 | Clinical Context — event sourcing, CQRS, Encounter aggregate | Clinical |
| Member 3 | Pharmacy + Billing — Specification pattern, ACL, invoice generation | Pharmacy + Billing |
| Member 4 | Saga orchestration, Scheduling, Docker Compose DevOps | Scheduling + Saga |
| Member 5 | Angular 20 frontend, Patient Identity, documentation | Frontend + Patient Identity |
