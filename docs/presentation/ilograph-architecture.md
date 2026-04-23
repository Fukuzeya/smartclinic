# SmartClinic — Ilograph Animated Architecture Spec

> **How to use:** open [https://app.ilograph.com](https://app.ilograph.com) →
> *New Diagram* → paste the YAML block below into the left-hand editor.
> Ilograph renders the `resources:` tree on the right and each entry under
> `perspectives:` becomes a selectable, animated view in the top bar.
>
> The spec intentionally uses **eight perspectives** and **two sequence
> perspectives** to demonstrate the advanced features of the platform
> (multi-view navigation, stepped walkthroughs, animated sequences,
> coloured subdomains, cross-cutting relation overlays).

---

## Perspectives you will get after pasting

| # | Perspective | Type | What it shows |
|---|---|---|---|
| 1 | **Strategic DDD — Context Map** | Relations | Core / Supporting / Generic subdomains, all six DDD relationship types on the edges |
| 2 | **Hexagonal Clean Architecture (inside one context)** | Relations | Domain / Application / Infrastructure / API layers, import direction |
| 3 | **Event Sourcing & CQRS write/read paths** | Sequence | Animated walkthrough of an Encounter command |
| 4 | **Patient Visit Saga (Orchestration)** | Sequence | End-to-end animated saga with compensations |
| 5 | **Runtime — Event-Driven Choreography** | Relations | Topic exchange, routing keys, published language |
| 6 | **Deployment — AWS target topology** | Relations | ECS/RDS/MQ/ALB/Route53/CloudWatch + dev `docker-compose` parity |
| 7 | **Observability — Three Pillars Pipeline** | Relations | OTel → Jaeger / Prometheus / Loki → Grafana correlation |
| 8 | **DevOps — GitHub Actions → AWS** | Walkthrough | Lint → Typecheck → Fitness → Tests → Build → Deploy |
| 9 | **Security & Compliance — Zero-Trust** | Relations | Keycloak OIDC, JWKS, RBAC, audit trail, hash-chain, crypto-shredding |
| 10 | **AI Clinical Copilot — Provider Port** | Relations | Hexagonal port/adapter, separate `ai_suggestions` audit table |

---

## Paste this full block into Ilograph

```yaml
---
imports:
- from: ilograph/aws
  namespace: AWS

layout:
  orientation: top-down
  lineSpacing: 1.1

resources:
- name: SmartClinic Platform
  subtitle: Advanced DDD capstone · Zimbabwe healthcare
  description: >
    Intelligent clinic management system built around six bounded contexts
    communicating via a Published Language on RabbitMQ. Core contains a
    hash-chained event-sourced Clinical EMR; saga orchestrates the patient
    visit end-to-end; deployed to AWS via GitHub Actions with full three-
    pillar observability.
  backgroundColor: '#f7f9fc'
  color: '#1a1a2e'

  children:

  # ─────────────────────────────────────────────────────────
  # ACTORS
  # ─────────────────────────────────────────────────────────
  - name: Actors
    subtitle: Human roles (Keycloak realm)
    style: outline
    backgroundColor: '#fff7ed'
    children:
    - name: Receptionist
      subtitle: role=receptionist
      description: Registers patients, books & checks in appointments.
    - name: Doctor
      subtitle: role=doctor
      description: Runs clinical encounters, issues prescriptions & lab orders, accepts/discards AI suggestions.
    - name: Pharmacist
      subtitle: role=pharmacist
      description: Dispenses prescriptions gated by Specification chain.
    - name: Lab Tech
      subtitle: role=lab_tech
      description: Records lab results against orders.
    - name: Accounts
      subtitle: role=accounts
      description: Reconciles invoices, records payments.
    - name: Patient
      subtitle: external
      description: Data subject; POPIA-equivalent rights.

  # ─────────────────────────────────────────────────────────
  # FRONTEND
  # ─────────────────────────────────────────────────────────
  - name: Angular SPA
    subtitle: Angular 20 · Nginx container
    description: >
      Role-aware shell with feature modules per bounded context; OIDC PKCE
      public client; lazy-loaded routes; event-timeline view for Event Sourcing.
    color: '#dd0031'
    children:
    - name: Auth Core
      subtitle: oidc-client-ts · AuthGuard
    - name: Shell & Nav
      subtitle: role-based navigation
    - name: Feature · Patients
    - name: Feature · Appointments
    - name: Feature · Encounters
      subtitle: SOAP + AI copilot panel
    - name: Feature · Prescriptions
    - name: Feature · Lab Orders
    - name: Feature · Invoices
    - name: Feature · Visit Tracker
      subtitle: saga state viewer

  # ─────────────────────────────────────────────────────────
  # IDENTITY
  # ─────────────────────────────────────────────────────────
  - name: Keycloak IdP
    subtitle: OIDC · realm=smartclinic (ADR-0011)
    description: >
      Issues JWTs carrying realm_access.roles. Every bounded context validates
      offline via cached JWKS. Conformist relationship — we adopt Keycloak's
      claim shape as-is.
    color: '#4d4dff'
    children:
    - name: JWKS Endpoint
      subtitle: /protocol/openid-connect/certs
    - name: Token Endpoint
      subtitle: PKCE · code flow
    - name: Users & Roles
      subtitle: seeded realm

  # ─────────────────────────────────────────────────────────
  # BOUNDED CONTEXTS
  # ─────────────────────────────────────────────────────────
  - name: Bounded Contexts
    subtitle: Six autonomous services · one DB schema each
    style: outline
    backgroundColor: '#eef6ff'
    children:

    # ---------- SUPPORTING ----------
    - name: Patient Identity
      subtitle: Supporting subdomain · upstream system of record
      description: >
        Registration, demographics, national ID, medical aid. Upstream for
        the Published Language event patient.registered.v1 / patient.updated.v1.
      color: '#f59e0b'
      children:
      - name: API · FastAPI
        subtitle: REST + OIDC-bearer
      - name: Application Layer
        subtitle: Command/Query handlers
      - name: Domain Layer
        subtitle: Patient aggregate · VOs (NationalId, PersonName, Phone)
      - name: Infrastructure
        subtitle: Postgres repo · Outbox publisher
      - name: DB · patient_identity
        subtitle: PostgreSQL schema

    - name: Scheduling
      subtitle: Supporting subdomain · Partnership with Clinical
      description: >
        Appointment aggregate with conflict-detection Specifications. Publishes
        appointment.checked_in.v1 which opens an encounter downstream.
      color: '#f59e0b'
      children:
      - name: API · FastAPI
      - name: Application Layer
      - name: Domain Layer
        subtitle: Appointment · Specifications (SlotAvailable, NoOverlap)
      - name: Infrastructure
        subtitle: Outbox publisher · Inbox subscriber
      - name: DB · scheduling

    # ---------- CORE ----------
    - name: Clinical
      subtitle: Core subdomain · Event Sourcing + CQRS + Hash-chain
      description: >
        The differentiating core. Encounter is an event-sourced aggregate;
        every write appends to a hash-chained events table (ADR-0012) that
        makes any retroactive tamper detectable in O(events). CQRS read
        model projects into denormalised views for the SPA.
      color: '#dc2626'
      children:
      - name: API · FastAPI
        subtitle: /encounters · /ai/soap-draft · /verify-chain
      - name: Application Layer
        subtitle: CommandBus · QueryBus · Mediator
      - name: Domain Layer
        subtitle: Encounter (event-sourced aggregate) · Value Objects
      - name: Published Language
        subtitle: clinical.*.v1 event contracts
      - name: AI Copilot Port
        subtitle: ClinicalCopilotPort (ADR-0013)
      - name: Write Model
        subtitle: hash-chained events table · prev_hash + hash
      - name: Read Model
        subtitle: CQRS projection (ADR-0004)
      - name: AI Suggestions Store
        subtitle: separate audit table · NOT in events
      - name: DB · clinical_write
        subtitle: PostgreSQL · append-only events
      - name: DB · clinical_read
        subtitle: PostgreSQL · materialised projections

    # ---------- GENERIC ----------
    - name: Pharmacy
      subtitle: Generic subdomain · Specification + Anti-Corruption Layer
      description: >
        Prescription dispensing gated by a composable Specification chain
        (allergy, interaction, duplicate therapy, out-of-stock). Talks to
        RxNav through an Anti-Corruption Layer so that a swap to a local
        formulary is a one-adapter change.
      color: '#16a34a'
      children:
      - name: API · FastAPI
      - name: Application Layer
      - name: Domain Layer
        subtitle: Prescription · Dispensing · Specifications
      - name: ACL Adapter
        subtitle: RxNavClient · DrugInteractionPort
      - name: Infrastructure
      - name: DB · pharmacy

    - name: Laboratory
      subtitle: Generic subdomain
      description: Lab orders & results; flags abnormal values against ranges.
      color: '#16a34a'
      children:
      - name: API · FastAPI
      - name: Application Layer
      - name: Domain Layer
        subtitle: LabOrder · Result
      - name: Infrastructure
      - name: DB · laboratory

    - name: Billing
      subtitle: Generic subdomain · downstream of everyone
      description: >
        Auto-generates invoices from clinical, pharmacy, and lab events.
        Tariff calculation is a Domain Service. Medical-aid adjudication
        logic is a Specification chain.
      color: '#16a34a'
      children:
      - name: API · FastAPI
      - name: Application Layer
      - name: Domain Layer
        subtitle: Invoice · Money VO · TariffCalculationService
      - name: Infrastructure
      - name: DB · billing

    # ---------- ORCHESTRATOR ----------
    - name: Saga Orchestrator
      subtitle: Process Manager · Patient Visit (ADR-0005)
      description: >
        Stateful coordinator that listens to every context on the topic
        exchange and drives the visit state machine — including
        compensating actions when a step fails (out-of-stock, payment
        decline, no-show).
      color: '#7c3aed'
      children:
      - name: API · read-only saga state
      - name: Saga State Machine
        subtitle: deterministic transitions
      - name: Compensation Handlers
        subtitle: cancel-encounter · refund-invoice · notify-doctor
      - name: DB · saga

  # ─────────────────────────────────────────────────────────
  # SHARED KERNEL
  # ─────────────────────────────────────────────────────────
  - name: Shared Kernel
    subtitle: libs/shared_kernel · ADR-0010 (narrow & governed)
    description: >
      Jointly-owned tiny library. Domain primitives, Outbox, Inbox,
      Event Bus adapter, structured logging, OTel tracing, Prometheus
      metrics, Keycloak JWT validator, FastAPI factory with RFC 7807
      problem+json. Imported by every context; changes governed by joint
      code-review.
    color: '#0ea5e9'
    children:
    - name: Domain Primitives
      subtitle: AggregateRoot · ValueObject · Entity · DomainEvent · Specification · Result
    - name: Application Primitives
      subtitle: Command · Query · Mediator · UnitOfWork
    - name: Outbox + Inbox
      subtitle: Transactional reliability (ADR-0009)
    - name: Event Bus Adapter
      subtitle: aio-pika topic publisher/subscriber
    - name: Security Adapter
      subtitle: KeycloakJwtValidator · require_role
    - name: Telemetry
      subtitle: structlog · OpenTelemetry · prometheus-client
    - name: AI Copilot Factory
      subtitle: MockCopilot · AnthropicCopilot (ADR-0013)

  # ─────────────────────────────────────────────────────────
  # MESSAGING
  # ─────────────────────────────────────────────────────────
  - name: RabbitMQ
    subtitle: AMQP 0-9-1 · topic exchange (ADR-0008)
    description: >
      Single topic exchange smartclinic.events carries all Published
      Language events. Durable queues per consumer with DLX + retry TTL.
      Routing keys follow <context>.<entity>.<event>.v<N>.
    color: '#f97316'
    children:
    - name: Exchange · smartclinic.events
      subtitle: topic · durable
    - name: Queue · patient.events
    - name: Queue · clinical.events
    - name: Queue · pharmacy.clinical.events
    - name: Queue · laboratory.clinical.events
    - name: Queue · billing.clinical.events
    - name: Queue · billing.laboratory.events
    - name: Queue · saga.all.events
    - name: DLX · smartclinic.events.dlx
      subtitle: retry TTL + parking lot

  # ─────────────────────────────────────────────────────────
  # DATA PLANE
  # ─────────────────────────────────────────────────────────
  - name: PostgreSQL 16
    subtitle: One logical DB per bounded context
    description: Append-only events in Clinical; transactional data elsewhere.
    color: '#336791'

  # ─────────────────────────────────────────────────────────
  # EXTERNAL SYSTEMS
  # ─────────────────────────────────────────────────────────
  - name: External Systems
    subtitle: Third-party · accessed through adapters only
    style: outline
    backgroundColor: '#fef3f2'
    children:
    - name: RxNav / RxNorm
      subtitle: NLM drug database
      description: Behind Anti-Corruption Layer (ADR-0007).
    - name: Anthropic API
      subtitle: claude-haiku-4-5 · optional
      description: Behind ClinicalCopilotPort (ADR-0013). Mock fallback when key absent.
    - name: MailHog / SES
      subtitle: SMTP (dev) · AWS SES (prod)

  # ─────────────────────────────────────────────────────────
  # OBSERVABILITY PLATFORM
  # ─────────────────────────────────────────────────────────
  - name: Observability Platform
    subtitle: Three-pillar correlated telemetry
    style: outline
    backgroundColor: '#f0fdf4'
    children:
    - name: OTel Collector
      subtitle: OTLP gRPC receiver · fan-out
    - name: Jaeger
      subtitle: distributed tracing
    - name: Prometheus
      subtitle: metrics · exemplars · remote-write
    - name: Loki
      subtitle: log aggregation
    - name: Grafana
      subtitle: dashboards · trace↔log↔metric correlation
    - name: AlertManager
      subtitle: SLO breach → PagerDuty

  # ─────────────────────────────────────────────────────────
  # CI/CD
  # ─────────────────────────────────────────────────────────
  - name: GitHub
    subtitle: Source of truth
    color: '#24292e'
    children:
    - name: Repo · SmartClinic
      subtitle: uv workspace monorepo
    - name: Pull Request
      subtitle: required checks
    - name: Main Branch
      subtitle: protected · deploys to AWS

  - name: GitHub Actions
    subtitle: CI/CD pipeline (.github/workflows/ci.yml)
    color: '#2088ff'
    children:
    - name: Job · Lint (ruff)
    - name: Job · Typecheck (mypy strict)
    - name: Job · Unit Tests (pytest)
    - name: Job · Architecture Fitness
      subtitle: no cross-context imports · ADR-0002 enforced
    - name: Job · Integration Tests
      subtitle: testcontainers · Postgres + RabbitMQ
    - name: Job · Docker Build Matrix
      subtitle: 7 service images · cached layers
    - name: Job · Stack Smoke Test
      subtitle: compose up infra · healthchecks
    - name: Job · Image Push (prod)
      subtitle: OIDC → ECR · no long-lived secrets
    - name: Job · Deploy to AWS
      subtitle: ECS rolling · CodeDeploy blue/green

  # ─────────────────────────────────────────────────────────
  # AWS PRODUCTION TARGET
  # ─────────────────────────────────────────────────────────
  - name: AWS Cloud
    subtitle: Production deployment target
    instanceOf: AWS::Cloud
    children:
    - name: Route 53
      subtitle: DNS · ACM certificates
      instanceOf: AWS::NetworkingContentDelivery::Route53
    - name: CloudFront
      subtitle: SPA edge caching
      instanceOf: AWS::NetworkingContentDelivery::CloudFront
    - name: WAF
      subtitle: OWASP top-10 rules
      instanceOf: AWS::SecurityIdentityCompliance::WAF

    - name: VPC · smartclinic-prod
      instanceOf: AWS::NetworkingContentDelivery::VPC
      children:
      - name: Public Subnet · ALB
        children:
        - name: ALB
          subtitle: TLS termination · path routing
          instanceOf: AWS::NetworkingContentDelivery::ElasticLoadBalancing::ApplicationLoadBalancer

      - name: Private Subnet · Apps
        children:
        - name: ECS Fargate Cluster
          instanceOf: AWS::Compute::ECS
          children:
          - name: Task · patient_identity
          - name: Task · scheduling
          - name: Task · clinical
          - name: Task · pharmacy
          - name: Task · laboratory
          - name: Task · billing
          - name: Task · saga_orchestrator
          - name: Task · frontend (nginx)
        - name: ECR
          subtitle: container registry
          instanceOf: AWS::Compute::ECR

      - name: Private Subnet · Data
        children:
        - name: RDS PostgreSQL
          subtitle: multi-AZ · automated backup · PITR
          instanceOf: AWS::Database::RDS
        - name: Amazon MQ (RabbitMQ)
          subtitle: managed broker · cluster
          instanceOf: AWS::ApplicationIntegration::MQ
        - name: Secrets Manager
          subtitle: DB creds · OIDC client secret
          instanceOf: AWS::SecurityIdentityCompliance::SecretsManager
        - name: KMS
          subtitle: envelope encryption · crypto-shred keys
          instanceOf: AWS::SecurityIdentityCompliance::KMS

    - name: CloudWatch
      subtitle: logs · metrics · alarms
      instanceOf: AWS::ManagementGovernance::CloudWatch
    - name: SES
      subtitle: invoice + reminder emails
      instanceOf: AWS::CustomerEngagement::SES
    - name: IAM
      subtitle: OIDC trust with GitHub · least-privilege roles
      instanceOf: AWS::SecurityIdentityCompliance::IAM

# ═════════════════════════════════════════════════════════════
# PERSPECTIVES
# ═════════════════════════════════════════════════════════════
perspectives:

# ──────────────────────────────────────────────────────────────
# 1. STRATEGIC DDD — CONTEXT MAP
# ──────────────────────────────────────────────────────────────
- name: 1. Strategic DDD · Context Map
  notes: |
    **Strategic DDD view.** Colours encode subdomain type:
    🔴 Core (Clinical) · 🟡 Supporting (Patient Identity, Scheduling) ·
    🟢 Generic (Pharmacy, Laboratory, Billing) · 🟣 Process Manager (Saga).

    Every edge is labelled with the **DDD relationship type**:
    Partnership · Customer-Supplier (U→D) · Conformist · Anti-Corruption
    Layer · Shared Kernel · Published Language. This map is enforced by
    a CI fitness function (no cross-context imports).
  relations:

  # Published Language from Patient Identity (Customer-Supplier U→D)
  - from: Patient Identity
    to: Scheduling
    label: Published Language · Customer-Supplier (U→D)
    description: patient.registered.v1 / patient.updated.v1 · downstream subscribes, builds read model, never writes back.
    color: '#f59e0b'
  - from: Patient Identity
    to: Clinical
    label: Published Language · U→D
    color: '#f59e0b'
  - from: Patient Identity
    to: Billing
    label: Published Language · U→D
    color: '#f59e0b'

  # Partnership
  - from: Scheduling
    to: Clinical
    label: Partnership
    description: Check-in triggers encounter start; both teams evolve appointment.checked_in.v1 together.
    color: '#7c3aed'
    arrowDirection: bidirectional

  # Clinical publishes to downstream
  - from: Clinical
    to: Pharmacy
    label: Published Language · U→D
    description: clinical.encounter.prescription_issued.v1
    color: '#dc2626'
  - from: Clinical
    to: Laboratory
    label: Published Language · U→D
    description: clinical.encounter.lab_ordered.v1
    color: '#dc2626'
  - from: Clinical
    to: Billing
    label: Published Language · U→D
    description: clinical.encounter.finalised.v1
    color: '#dc2626'

  # Generic → Billing
  - from: Pharmacy
    to: Billing
    label: Published Language · U→D
    description: pharmacy.dispensing.completed.v1 becomes an invoice line.
    color: '#16a34a'
  - from: Laboratory
    to: Billing
    label: Published Language · U→D
    description: laboratory.result.recorded.v1
    color: '#16a34a'

  # ACL to RxNav
  - from: Pharmacy
    to: RxNav / RxNorm
    label: Anti-Corruption Layer
    description: Translates RxNav vocabulary (rxcui/tty) into Pharmacy's ubiquitous language. ADR-0007.
    color: '#be123c'

  # Conformist to Keycloak
  - from: Patient Identity
    to: Keycloak IdP
    label: Conformist
    color: '#6b7280'
  - from: Scheduling
    to: Keycloak IdP
    label: Conformist
    color: '#6b7280'
  - from: Clinical
    to: Keycloak IdP
    label: Conformist
    color: '#6b7280'
  - from: Pharmacy
    to: Keycloak IdP
    label: Conformist
    color: '#6b7280'
  - from: Laboratory
    to: Keycloak IdP
    label: Conformist
    color: '#6b7280'
  - from: Billing
    to: Keycloak IdP
    label: Conformist
    color: '#6b7280'

  # Saga orchestrates
  - from: Saga Orchestrator
    to: Patient Identity
    label: orchestrates
    color: '#7c3aed'
    arrowDirection: bidirectional
  - from: Saga Orchestrator
    to: Scheduling
    label: orchestrates
    color: '#7c3aed'
    arrowDirection: bidirectional
  - from: Saga Orchestrator
    to: Clinical
    label: orchestrates
    color: '#7c3aed'
    arrowDirection: bidirectional
  - from: Saga Orchestrator
    to: Pharmacy
    label: orchestrates
    color: '#7c3aed'
    arrowDirection: bidirectional
  - from: Saga Orchestrator
    to: Laboratory
    label: orchestrates
    color: '#7c3aed'
    arrowDirection: bidirectional
  - from: Saga Orchestrator
    to: Billing
    label: orchestrates
    color: '#7c3aed'
    arrowDirection: bidirectional

  # Shared Kernel
  - from: Patient Identity
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'
  - from: Scheduling
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'
  - from: Clinical
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'
  - from: Pharmacy
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'
  - from: Laboratory
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'
  - from: Billing
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'
  - from: Saga Orchestrator
    to: Shared Kernel
    label: Shared Kernel
    color: '#0ea5e9'

# ──────────────────────────────────────────────────────────────
# 2. HEXAGONAL / CLEAN ARCHITECTURE INSIDE A CONTEXT
# ──────────────────────────────────────────────────────────────
- name: 2. Hexagonal Layering (Clinical)
  notes: |
    **Inside one bounded context.** Every service follows the same
    four-layer hexagonal layout. Arrows encode the **allowed import
    direction** and are enforced by the fitness test in
    `libs/shared_kernel/tests/fitness/test_architecture.py`.

    - API → Application → Domain (inward)
    - Infrastructure → Application, Domain (adapter side)
    - Domain depends on nothing external — it is the centre of the hexagon.
  relations:
  - from: API · FastAPI
    to: Application Layer
    label: calls command/query handlers
    parents: [Clinical]
  - from: Application Layer
    to: Domain Layer
    label: uses aggregate & invariants
    parents: [Clinical]
  - from: Application Layer
    to: AI Copilot Port
    label: asks for SOAP draft / drug-safety explanation
    parents: [Clinical]
  - from: Application Layer
    to: Write Model
    label: persists events · optimistic concurrency
    parents: [Clinical]
  - from: Write Model
    to: Read Model
    label: projection (CQRS · ADR-0004)
    description: Denormalised views: EncounterSummaryView, PrescriptionListView.
    parents: [Clinical]
  - from: Application Layer
    to: Read Model
    label: query handlers
    parents: [Clinical]
  - from: Application Layer
    to: AI Suggestions Store
    label: writes non-authoritative suggestion audit
    parents: [Clinical]
  - from: Write Model
    to: DB · clinical_write
    label: append-only events · hash-chained
    parents: [Clinical]
  - from: Read Model
    to: DB · clinical_read
    parents: [Clinical]
  - from: Clinical
    to: Shared Kernel
    label: uses AggregateRoot, Outbox, UoW, JWT, Telemetry
  - from: Clinical
    to: Published Language
    label: publishes clinical.*.v1
    parents: [Clinical]

# ──────────────────────────────────────────────────────────────
# 3. EVENT SOURCING + CQRS — ANIMATED SEQUENCE
# ──────────────────────────────────────────────────────────────
- name: 3. Event Sourcing + CQRS (Encounter)
  notes: |
    **Animated sequence.** Hit *Play* to see the full command path:
    command → aggregate rehydration → invariant check → event append
    (hash-chained) → outbox → projection → CQRS read. The same pattern
    backs the `verify_chain(aggregate_id)` tamper-detection call.
  sequence:
    start: Doctor
    steps:
    - to: Angular SPA
      label: 1. POST /encounters/{id}/prescribe
    - to: API · FastAPI
      label: 2. validate JWT via Keycloak JWKS
      parents: [Clinical]
    - to: Application Layer
      label: 3. IssuePrescriptionCommand → handler
      parents: [Clinical]
    - to: Write Model
      label: 4. load events for aggregate_id (FOR UPDATE)
      parents: [Clinical]
    - to: Domain Layer
      label: 5. rehydrate Encounter · check invariants (diagnosis present, etc.)
      parents: [Clinical]
    - to: Write Model
      label: 6. append PrescriptionIssued event · sha256(payload + prev_hash)
      parents: [Clinical]
    - to: Outbox + Inbox
      label: 7. write outbox row in same transaction (ADR-0009)
      parents: [Shared Kernel]
    - to: Exchange · smartclinic.events
      label: 8. relay publishes clinical.encounter.prescription_issued.v1
      parents: [RabbitMQ]
    - to: Read Model
      label: 9. projector updates EncounterSummaryView
      parents: [Clinical]
    - to: Angular SPA
      label: 10. 202 Accepted · event-timeline refreshes
      bidirectional: true

# ──────────────────────────────────────────────────────────────
# 4. PATIENT VISIT SAGA — ANIMATED
# ──────────────────────────────────────────────────────────────
- name: 4. Patient Visit Saga
  notes: |
    **The happy path followed by a compensation example.** The saga is a
    Process Manager (ADR-0005) — stateful, durable, drives the visit
    end-to-end, and issues compensating commands when a step fails.
  sequence:
    start: Receptionist
    steps:
    - to: Scheduling
      label: 1. Check in appointment
    - to: Saga Orchestrator
      label: 2. scheduling.appointment.checked_in.v1
    - to: Clinical
      label: 3. StartEncounter command
    - to: Saga Orchestrator
      label: 4. clinical.encounter.started.v1
    - to: Clinical
      label: 5. Doctor records diagnosis + prescriptions + labs
      bidirectional: true
    - to: Pharmacy
      label: 6. clinical.encounter.prescription_issued.v1
    - to: Laboratory
      label: 7. clinical.encounter.lab_ordered.v1
    - to: Saga Orchestrator
      label: 8. pharmacy.dispensing.completed.v1
    - to: Saga Orchestrator
      label: 9. laboratory.result.recorded.v1
    - to: Billing
      label: 10. clinical.encounter.finalised.v1 → auto-invoice
    - to: Saga Orchestrator
      label: 11. billing.invoice.issued.v1
    - to: Saga Orchestrator
      label: 12. billing.invoice.paid.v1 → saga.patient_visit.completed.v1
    # Compensation path
    - to: Compensation Handlers
      label: ↯ COMPENSATION · drug out of stock
      parents: [Saga Orchestrator]
    - to: Clinical
      label: ↯ notify doctor · request substitution
    - to: Pharmacy
      label: ↯ re-dispense after substitution

# ──────────────────────────────────────────────────────────────
# 5. RUNTIME — EVENT-DRIVEN CHOREOGRAPHY
# ──────────────────────────────────────────────────────────────
- name: 5. Runtime · Event Bus
  notes: |
    **All cross-context integration is asynchronous and typed.** A single
    topic exchange `smartclinic.events` carries the Published Language.
    Routing key format: `<context>.<entity>.<event>.v<N>`. Every consumer
    has a durable queue + DLX. The Outbox+Inbox pair guarantees
    **at-least-once delivery with exactly-once effect**.
  relations:
  - from: Patient Identity
    to: Exchange · smartclinic.events
    label: publishes patient.*.v1
    parents: [RabbitMQ]
    color: '#f59e0b'
  - from: Scheduling
    to: Exchange · smartclinic.events
    label: publishes scheduling.*.v1
    color: '#f59e0b'
  - from: Clinical
    to: Exchange · smartclinic.events
    label: publishes clinical.*.v1
    color: '#dc2626'
  - from: Pharmacy
    to: Exchange · smartclinic.events
    label: publishes pharmacy.*.v1
    color: '#16a34a'
  - from: Laboratory
    to: Exchange · smartclinic.events
    label: publishes laboratory.*.v1
    color: '#16a34a'
  - from: Billing
    to: Exchange · smartclinic.events
    label: publishes billing.*.v1
    color: '#16a34a'

  - from: Exchange · smartclinic.events
    to: Queue · clinical.events
    label: binding · scheduling.*.v1 · patient.*.v1
  - from: Exchange · smartclinic.events
    to: Queue · pharmacy.clinical.events
    label: binding · clinical.encounter.prescription_issued.v1
  - from: Exchange · smartclinic.events
    to: Queue · laboratory.clinical.events
    label: binding · clinical.encounter.lab_ordered.v1
  - from: Exchange · smartclinic.events
    to: Queue · billing.clinical.events
    label: binding · clinical.encounter.finalised.v1
  - from: Exchange · smartclinic.events
    to: Queue · billing.laboratory.events
    label: binding · laboratory.result.recorded.v1
  - from: Exchange · smartclinic.events
    to: Queue · saga.all.events
    label: binding · # (wildcard, all events)

  - from: Queue · clinical.events
    to: Clinical
    label: idempotent consumer (Inbox)
  - from: Queue · pharmacy.clinical.events
    to: Pharmacy
  - from: Queue · laboratory.clinical.events
    to: Laboratory
  - from: Queue · billing.clinical.events
    to: Billing
  - from: Queue · billing.laboratory.events
    to: Billing
  - from: Queue · saga.all.events
    to: Saga Orchestrator

# ──────────────────────────────────────────────────────────────
# 6. DEPLOYMENT — AWS TOPOLOGY
# ──────────────────────────────────────────────────────────────
- name: 6. Deployment · AWS
  notes: |
    **Production target on AWS.** ECS Fargate runs the seven stateless
    services; RDS PostgreSQL (multi-AZ) backs the write/read databases;
    Amazon MQ (RabbitMQ engine) replaces the self-hosted broker. Secrets
    in Secrets Manager; envelope encryption with KMS (also supplies the
    per-record key for POPIA crypto-shredding). CloudFront serves the
    Angular SPA; ALB path-routes to ECS tasks; Route 53 + ACM provide
    DNS and TLS.
  relations:
  - from: Patient
    to: Route 53
    label: https://smartclinic.health
  - from: Route 53
    to: CloudFront
  - from: CloudFront
    to: Task · frontend (nginx)
    label: origin
    parents: [ECS Fargate Cluster]
  - from: Route 53
    to: ALB
  - from: CloudFront
    to: WAF
    label: OWASP rules
  - from: ALB
    to: Task · patient_identity
    label: /api/patients/*
  - from: ALB
    to: Task · scheduling
    label: /api/appointments/*
  - from: ALB
    to: Task · clinical
    label: /api/encounters/*
  - from: ALB
    to: Task · pharmacy
    label: /api/prescriptions/*
  - from: ALB
    to: Task · laboratory
    label: /api/lab/*
  - from: ALB
    to: Task · billing
    label: /api/invoices/*
  - from: ALB
    to: Task · saga_orchestrator
    label: /api/saga/* (read-only)

  - from: Task · patient_identity
    to: RDS PostgreSQL
    label: db=patient_identity
  - from: Task · scheduling
    to: RDS PostgreSQL
    label: db=scheduling
  - from: Task · clinical
    to: RDS PostgreSQL
    label: db=clinical_write + clinical_read
  - from: Task · pharmacy
    to: RDS PostgreSQL
    label: db=pharmacy
  - from: Task · laboratory
    to: RDS PostgreSQL
    label: db=laboratory
  - from: Task · billing
    to: RDS PostgreSQL
    label: db=billing
  - from: Task · saga_orchestrator
    to: RDS PostgreSQL
    label: db=saga

  - from: Task · patient_identity
    to: Amazon MQ (RabbitMQ)
    label: AMQP 0-9-1
    arrowDirection: bidirectional
  - from: Task · scheduling
    to: Amazon MQ (RabbitMQ)
    arrowDirection: bidirectional
  - from: Task · clinical
    to: Amazon MQ (RabbitMQ)
    arrowDirection: bidirectional
  - from: Task · pharmacy
    to: Amazon MQ (RabbitMQ)
    arrowDirection: bidirectional
  - from: Task · laboratory
    to: Amazon MQ (RabbitMQ)
    arrowDirection: bidirectional
  - from: Task · billing
    to: Amazon MQ (RabbitMQ)
    arrowDirection: bidirectional
  - from: Task · saga_orchestrator
    to: Amazon MQ (RabbitMQ)
    arrowDirection: bidirectional

  - from: Task · clinical
    to: Secrets Manager
    label: DB creds · OIDC secret
  - from: Task · clinical
    to: KMS
    label: envelope encryption · crypto-shred keys
  - from: Task · pharmacy
    to: RxNav / RxNorm
    label: HTTPS · via ACL adapter
  - from: Task · clinical
    to: Anthropic API
    label: HTTPS · via Copilot Port
  - from: Task · billing
    to: SES
    label: invoice emails

  - from: ECS Fargate Cluster
    to: CloudWatch
    label: container logs + metrics

# ──────────────────────────────────────────────────────────────
# 7. OBSERVABILITY PIPELINE
# ──────────────────────────────────────────────────────────────
- name: 7. Observability · Three Pillars
  notes: |
    **Trace · Metric · Log — correlated.** Every service emits OTLP to a
    central OpenTelemetry Collector. Traces land in Jaeger, metrics in
    Prometheus (with exemplars linking back to traces), logs in Loki
    (with `trace_id` labels). Grafana stitches all three into one pane
    with `traceToMetrics` and `tracesToLogs` so that clicking a slow
    span shows you the metric chart and the exact log lines.
  relations:
  - from: Patient Identity
    to: OTel Collector
    label: OTLP gRPC · traces/metrics/logs
    parents: [Observability Platform]
  - from: Scheduling
    to: OTel Collector
    parents: [Observability Platform]
  - from: Clinical
    to: OTel Collector
    parents: [Observability Platform]
  - from: Pharmacy
    to: OTel Collector
    parents: [Observability Platform]
  - from: Laboratory
    to: OTel Collector
    parents: [Observability Platform]
  - from: Billing
    to: OTel Collector
    parents: [Observability Platform]
  - from: Saga Orchestrator
    to: OTel Collector
    parents: [Observability Platform]

  - from: OTel Collector
    to: Jaeger
    label: traces
    parents: [Observability Platform]
  - from: OTel Collector
    to: Prometheus
    label: metrics + exemplars
    parents: [Observability Platform]
  - from: OTel Collector
    to: Loki
    label: structlog JSON
    parents: [Observability Platform]
  - from: Prometheus
    to: Grafana
    label: datasource
    parents: [Observability Platform]
  - from: Loki
    to: Grafana
    label: datasource
    parents: [Observability Platform]
  - from: Jaeger
    to: Grafana
    label: datasource
    parents: [Observability Platform]
  - from: Prometheus
    to: AlertManager
    label: SLO breach rules
    parents: [Observability Platform]
  - from: AlertManager
    to: SES
    label: email · PagerDuty webhook

# ──────────────────────────────────────────────────────────────
# 8. DEVOPS — GITHUB ACTIONS → AWS (WALKTHROUGH)
# ──────────────────────────────────────────────────────────────
- name: 8. DevOps · CI/CD Walkthrough
  notes: |
    **Each step highlights the part of the system involved in that CI
    stage.** Click forward to advance through the pipeline.
  walkthrough:

  - text: |
      **Step 0 — Developer commits.** A push or PR to `main`/`develop`
      triggers `.github/workflows/ci.yml`. The concurrency group cancels
      stale runs for the same ref.
    highlight:
    - resource: Repo · SmartClinic
      color: '#24292e'

  - text: |
      **Step 1 — Lint.** `ruff check` and `ruff format --check` run
      against the entire uv workspace. Fast; kills obviously-broken PRs
      early.
    highlight:
    - resource: Job · Lint (ruff)
      color: '#2088ff'

  - text: |
      **Step 2 — Type check.** `mypy --strict` on the shared kernel
      (highest-risk surface) plus the default mypy config on every
      service. Catches contract drift before integration.
    highlight:
    - resource: Job · Typecheck (mypy strict)
      color: '#2088ff'

  - text: |
      **Step 3 — Unit tests.** `pytest` across every service + shared
      kernel. Pure domain tests: no Docker, no network.
    highlight:
    - resource: Job · Unit Tests (pytest)
      color: '#2088ff'

  - text: |
      **Step 4 — Architecture fitness functions.** The DDD context map
      is code: this job asserts no cross-context imports, no domain
      layer importing infrastructure, no API layer skipping the
      application layer. The architecture diagram above is **enforced**,
      not aspirational.
    highlight:
    - resource: Job · Architecture Fitness
      color: '#10b981'
    - resource: Bounded Contexts
      color: '#10b981'

  - text: |
      **Step 5 — Integration tests.** testcontainers spins up Postgres
      and RabbitMQ; we exercise the Outbox relay, inbox idempotency, the
      hash-chain verifier, and the saga's happy + compensation paths.
    highlight:
    - resource: Job · Integration Tests
      color: '#2088ff'
    - resource: PostgreSQL 16
    - resource: RabbitMQ

  - text: |
      **Step 6 — Docker build.** Matrix builds 7 service images +
      frontend. Buildx cache key per service keeps incremental builds
      under a minute.
    highlight:
    - resource: Job · Docker Build Matrix
      color: '#2088ff'

  - text: |
      **Step 7 — Smoke test.** `docker compose up` infra profile +
      readiness probes confirm the whole stack can stand up green.
    highlight:
    - resource: Job · Stack Smoke Test
      color: '#2088ff'

  - text: |
      **Step 8 — OIDC → ECR.** On merge to `main`, Actions assumes an
      AWS IAM role via GitHub OIDC (no long-lived secrets) and pushes
      tagged images to ECR.
    highlight:
    - resource: Job · Image Push (prod)
      color: '#ff9900'
    - resource: IAM
    - resource: ECR

  - text: |
      **Step 9 — Deploy.** CodeDeploy performs a blue/green rolling
      update of each ECS service. Health-check failure auto-rolls back;
      CloudWatch alarms gate the deployment.
    highlight:
    - resource: Job · Deploy to AWS
      color: '#ff9900'
    - resource: ECS Fargate Cluster
    - resource: CloudWatch

  - text: |
      **Step 10 — Observed live.** Traces, metrics and logs flow
      immediately into Grafana. An SLO breach during the canary window
      pages the on-call via AlertManager → SES.
    highlight:
    - resource: Observability Platform
      color: '#10b981'
    - resource: AlertManager

# ──────────────────────────────────────────────────────────────
# 9. SECURITY · ZERO-TRUST
# ──────────────────────────────────────────────────────────────
- name: 9. Security & Compliance
  notes: |
    **Zero-trust posture.** Every request is authenticated at the edge
    (Keycloak OIDC) and **re-validated** in every service (offline JWKS
    cache). Roles enforced by a `require_role("doctor")` FastAPI
    dependency. PII confined to Patient Identity; other contexts hold
    only `PatientId` references. Medical records cannot be hard-deleted
    — POPIA right-to-be-forgotten uses **crypto-shredding** (KMS key
    deletion). Integrity proven by the hash-chain (ADR-0012).
  relations:
  - from: Angular SPA
    to: Token Endpoint
    label: OIDC PKCE · public client
    parents: [Keycloak IdP]
  - from: Angular SPA
    to: Patient Identity
    label: Bearer JWT
  - from: Angular SPA
    to: Clinical
    label: Bearer JWT
  - from: Angular SPA
    to: Pharmacy
    label: Bearer JWT
  - from: Patient Identity
    to: JWKS Endpoint
    label: cache TTL · offline validation
    parents: [Keycloak IdP]
  - from: Clinical
    to: JWKS Endpoint
    parents: [Keycloak IdP]
  - from: Pharmacy
    to: JWKS Endpoint
    parents: [Keycloak IdP]
  - from: Clinical
    to: KMS
    label: per-record DEK · envelope encryption
  - from: Clinical
    to: Write Model
    label: every event hashed · prev_hash chain
    parents: [Clinical]
  - from: Doctor
    to: Clinical
    label: actor_id in event header · audit trail
  - from: WAF
    to: CloudFront
    label: request filter · OWASP top-10
    arrowDirection: backward
  - from: Secrets Manager
    to: Task · clinical
    label: rotated creds
    arrowDirection: backward

# ──────────────────────────────────────────────────────────────
# 10. AI CLINICAL COPILOT — PROVIDER PORT (INNOVATION)
# ──────────────────────────────────────────────────────────────
- name: 10. AI Copilot · Hexagonal Port
  notes: |
    **Innovation under hexagonal discipline (ADR-0013).** The Anthropic
    model is consumed via a `ClinicalCopilotPort` in the shared kernel.
    The domain and application layers import **only the port**; the
    adapter is injected at startup. A mock adapter is used when no API
    key is present — so CI is deterministic and the feature degrades
    gracefully. Suggestions are stored in a separate `ai_suggestions`
    table — **never** in the hash-chained `clinical_events`, protecting
    the medico-legal integrity guarantee.
  relations:
  - from: Doctor
    to: Feature · Encounters
    label: click "Draft SOAP"
    parents: [Angular SPA]
  - from: Feature · Encounters
    to: Clinical
    label: POST /ai/soap-draft
    parents: [Angular SPA]
  - from: Application Layer
    to: AI Copilot Port
    label: depends on PORT only
    parents: [Clinical]
  - from: AI Copilot Port
    to: AI Copilot Factory
    label: MockCopilot | AnthropicCopilot
    parents: [Clinical]
  - from: AI Copilot Factory
    to: Anthropic API
    label: claude-haiku-4-5 · cached prompt
    parents: [Shared Kernel]
  - from: Application Layer
    to: AI Suggestions Store
    label: stores AISuggestion VO + decision
    parents: [Clinical]
  - from: Application Layer
    to: Write Model
    label: ❌ AI text NEVER enters hash-chained events
    parents: [Clinical]
    color: '#dc2626'
    arrowDirection: none
```

---

## Presentation tips

- Open the **Strategic DDD · Context Map** first — this is what an examiner wants to see within the first 20 seconds.
- Use the **Sequence** perspectives (3 & 4) live during the demo: click *Play* and narrate over the animation.
- The **DevOps Walkthrough** (8) is a scripted click-through — perfect for the "DevOps & Deployment" marking area.
- Hover any resource for the embedded description (every node has one). Ilograph's side-panel doubles as speaker notes.
- Each perspective has a `notes:` block that renders as markdown in the UI — you do not need separate slides for these views.
