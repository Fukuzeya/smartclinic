# SmartClinic — SVG Architecture Diagrams (D2)

> **Goal:** generate clean SVG diagrams that Diagramotion
> ([app.diagramotion.com](https://app.diagramotion.com)) can animate
> layer-by-layer.
>
> **Tool chosen: [D2](https://d2lang.com)** — an architecture-focused
> DSL whose SVG output gives every node, container, and edge its own
> semantic `<g id="…">` group. Diagramotion uses those groups as its
> animation layers, so the animation quality is limited by the quality
> of the source SVG — and D2 is the best open source option for that.
>
> **How to compile to SVG (no install):**
> 1. Open [play.d2lang.com](https://play.d2lang.com).
> 2. Paste one of the code blocks below into the editor.
> 3. Top-right → **Export → SVG**.
> 4. Upload the `.svg` file to Diagramotion and build the animation.
>
> **How to compile locally (optional, batch mode):**
> ```bash
> # install once (macOS/Linux; on Windows use the Scoop/Chocolatey package)
> curl -fsSL https://d2lang.com/install.sh | sh -s --
>
> d2 --layout=elk --theme=0 --sketch=false 01-context-map.d2 01-context-map.svg
> ```
> `--layout=elk` gives the cleanest orthogonal routing (best for
> animation), `--theme=0` picks the neutral palette, `--sketch=false`
> keeps edges crisp so Diagramotion can trace them.

---

## Diagrams you will get (five separate SVGs)

| # | File | What it shows | Best animation in Diagramotion |
|---|---|---|---|
| 1 | `01-context-map.d2` | Strategic DDD context map with all 6 edge types | Reveal contexts by subdomain type, then edges |
| 2 | `02-runtime-event-flow.d2` | RabbitMQ topic exchange + routing keys | Trace a published event from producer → queue → consumer |
| 3 | `03-patient-visit-saga.d2` | Saga happy path + compensation | Step-by-step event emission |
| 4 | `04-aws-deployment.d2` | AWS production topology (ECS, RDS, Amazon MQ, CloudFront, etc.) | Layer reveal: edge → compute → data → observability |
| 5 | `05-cicd-pipeline.d2` | GitHub Actions → AWS | Sequential job reveal |

Save each block to its own `.d2` file with the filename shown.

---

## 1 · Strategic DDD Context Map — `01-context-map.d2`

```d2
# SmartClinic — Strategic DDD Context Map
# Colours encode subdomain type (Evans ch.15):
#   core (red) / supporting (amber) / generic (green)
# Every edge is labelled with its DDD relationship type.

direction: right

classes: {
  core: {
    style: {
      fill: "#fee2e2"
      stroke: "#dc2626"
      stroke-width: 3
      font-color: "#7f1d1d"
      font-size: 18
    }
  }
  supporting: {
    style: {
      fill: "#fef3c7"
      stroke: "#f59e0b"
      stroke-width: 2
      font-color: "#78350f"
      font-size: 16
    }
  }
  generic: {
    style: {
      fill: "#dcfce7"
      stroke: "#16a34a"
      stroke-width: 2
      font-color: "#14532d"
      font-size: 16
    }
  }
  process: {
    style: {
      fill: "#ede9fe"
      stroke: "#7c3aed"
      stroke-width: 2
      font-color: "#4c1d95"
      font-size: 16
    }
  }
  external: {
    style: {
      fill: "#f3f4f6"
      stroke: "#6b7280"
      stroke-width: 2
      stroke-dash: 4
      font-color: "#374151"
    }
  }
  kernel: {
    style: {
      fill: "#e0f2fe"
      stroke: "#0ea5e9"
      stroke-width: 2
      font-color: "#0c4a6e"
    }
  }
}

title: SmartClinic — Context Map (Strategic DDD) {
  near: top-center
  shape: text
  style: {
    font-size: 28
    bold: true
    font-color: "#0f172a"
  }
}

# ───── Supporting subdomains ─────
PI: Patient Identity {
  class: supporting
  shape: rectangle
  tooltip: Upstream system of record; owns PII; publishes patient.*.v1
}

SCH: Scheduling {
  class: supporting
  shape: rectangle
  tooltip: Appointments; conflict detection via Specification chain
}

# ───── Core subdomain ─────
CLIN: "Clinical\n(Core)\nEvent Sourcing + CQRS\nHash-chained log" {
  class: core
  shape: rectangle
  tooltip: Differentiating core; ADR-0003 / 0004 / 0012
}

# ───── Generic subdomains ─────
PHARM: "Pharmacy\nSpecification + ACL" {
  class: generic
  shape: rectangle
  tooltip: Dispensing gate; RxNav behind Anti-Corruption Layer (ADR-0007)
}

LAB: Laboratory {
  class: generic
  shape: rectangle
}

BILL: Billing {
  class: generic
  shape: rectangle
  tooltip: Auto-invoicing from events; Money VO; TariffCalculationService
}

# ───── Process manager ─────
SAGA: "Saga Orchestrator\nPatient Visit" {
  class: process
  shape: hexagon
  tooltip: Process Manager; owns the visit state machine; compensations
}

# ───── Shared kernel ─────
SK: "Shared Kernel\n(libs/shared_kernel)" {
  class: kernel
  shape: cylinder
}

# ───── External systems ─────
RxNav: "RxNav / RxNorm" {
  class: external
  shape: cloud
}
KC: "Keycloak IdP" {
  class: external
  shape: cloud
}

# ─── Edges: Patient Identity is Customer-Supplier Upstream ───
PI -> SCH: "Published Language\nCustomer-Supplier (U→D)" {
  style: {
    stroke: "#f59e0b"
    stroke-width: 2
    font-color: "#78350f"
  }
}
PI -> CLIN: "Published Language (U→D)" {
  style.stroke: "#f59e0b"
  style.stroke-width: 2
}
PI -> BILL: "Published Language (U→D)" {
  style.stroke: "#f59e0b"
  style.stroke-width: 2
}

# ─── Partnership (bidirectional, coloured) ───
SCH <-> CLIN: Partnership {
  style: {
    stroke: "#7c3aed"
    stroke-width: 3
    font-color: "#4c1d95"
    bold: true
  }
}

# ─── Clinical publishes downstream ───
CLIN -> PHARM: "Published Language (U→D)\nprescription_issued.v1" {
  style.stroke: "#dc2626"
  style.stroke-width: 2
}
CLIN -> LAB: "Published Language (U→D)\nlab_ordered.v1" {
  style.stroke: "#dc2626"
  style.stroke-width: 2
}
CLIN -> BILL: "Published Language (U→D)\nencounter.finalised.v1" {
  style.stroke: "#dc2626"
  style.stroke-width: 2
}

# ─── Generic → Billing ───
PHARM -> BILL: "Published Language (U→D)" {
  style.stroke: "#16a34a"
  style.stroke-width: 2
}
LAB -> BILL: "Published Language (U→D)" {
  style.stroke: "#16a34a"
  style.stroke-width: 2
}

# ─── Anti-Corruption Layer ───
PHARM -> RxNav: "Anti-Corruption Layer\n(ADR-0007)" {
  style: {
    stroke: "#be123c"
    stroke-width: 3
    stroke-dash: 5
    bold: true
  }
}

# ─── Conformist to Keycloak (one representative arrow to avoid clutter) ───
PI   -> KC: Conformist { style.stroke: "#6b7280"; style.stroke-dash: 3 }
SCH  -> KC: Conformist { style.stroke: "#6b7280"; style.stroke-dash: 3 }
CLIN -> KC: Conformist { style.stroke: "#6b7280"; style.stroke-dash: 3 }
PHARM-> KC: Conformist { style.stroke: "#6b7280"; style.stroke-dash: 3 }
LAB  -> KC: Conformist { style.stroke: "#6b7280"; style.stroke-dash: 3 }
BILL -> KC: Conformist { style.stroke: "#6b7280"; style.stroke-dash: 3 }

# ─── Saga orchestrates ───
SAGA -> PI: orchestrates { style.stroke: "#7c3aed"; style.stroke-dash: 2 }
SAGA -> SCH: orchestrates { style.stroke: "#7c3aed"; style.stroke-dash: 2 }
SAGA -> CLIN: orchestrates { style.stroke: "#7c3aed"; style.stroke-dash: 2 }
SAGA -> PHARM: orchestrates { style.stroke: "#7c3aed"; style.stroke-dash: 2 }
SAGA -> LAB: orchestrates { style.stroke: "#7c3aed"; style.stroke-dash: 2 }
SAGA -> BILL: orchestrates { style.stroke: "#7c3aed"; style.stroke-dash: 2 }

# ─── Shared kernel (consumed by everyone) ───
PI -> SK: Shared Kernel { style.stroke: "#0ea5e9" }
SCH -> SK: Shared Kernel { style.stroke: "#0ea5e9" }
CLIN -> SK: Shared Kernel { style.stroke: "#0ea5e9" }
PHARM -> SK: Shared Kernel { style.stroke: "#0ea5e9" }
LAB -> SK: Shared Kernel { style.stroke: "#0ea5e9" }
BILL -> SK: Shared Kernel { style.stroke: "#0ea5e9" }
SAGA -> SK: Shared Kernel { style.stroke: "#0ea5e9" }

legend: {
  shape: text
  near: bottom-center
  label: |md
    **Legend** — 🔴 Core · 🟡 Supporting · 🟢 Generic · 🟣 Process Manager · 🔵 Shared Kernel · ☁️ External
  |
  style.font-size: 14
}
```

---

## 2 · Runtime — Event Bus & Routing — `02-runtime-event-flow.d2`

```d2
# SmartClinic — Runtime view
# Shows how the Published Language flows through the topic exchange.
# Trace a single event in Diagramotion by animating layers in producer→queue→consumer order.

direction: right

classes: {
  svc: {
    style: {
      fill: "#eff6ff"
      stroke: "#2563eb"
      stroke-width: 2
      font-color: "#1e3a8a"
    }
  }
  core: {
    style: {
      fill: "#fee2e2"
      stroke: "#dc2626"
      stroke-width: 3
      font-color: "#7f1d1d"
      bold: true
    }
  }
  queue: {
    shape: queue
    style: {
      fill: "#fff7ed"
      stroke: "#f97316"
      stroke-width: 2
      font-color: "#7c2d12"
    }
  }
  exch: {
    shape: hexagon
    style: {
      fill: "#fef3c7"
      stroke: "#f59e0b"
      stroke-width: 3
      font-color: "#78350f"
      bold: true
    }
  }
}

title: Runtime — Event-Driven Choreography on RabbitMQ {
  near: top-center
  shape: text
  style: { font-size: 26; bold: true }
}

# ───── Producers (left side) ─────
producers: Producers {
  style: { fill: "#f8fafc"; stroke: "#94a3b8"; stroke-dash: 3 }
  PI: Patient Identity { class: svc }
  SCH: Scheduling { class: svc }
  CLIN: Clinical { class: core }
  PHARM: Pharmacy { class: svc }
  LAB: Laboratory { class: svc }
  BILL: Billing { class: svc }
}

# ───── Broker (middle) ─────
broker: RabbitMQ {
  style: { fill: "#fff7ed"; stroke: "#f97316"; stroke-width: 2 }

  EX: "smartclinic.events\n(topic exchange)" { class: exch }

  Q_clin: "clinical.events" { class: queue }
  Q_pharm: "pharmacy.clinical.events" { class: queue }
  Q_lab: "laboratory.clinical.events" { class: queue }
  Q_bill_c: "billing.clinical.events" { class: queue }
  Q_bill_l: "billing.laboratory.events" { class: queue }
  Q_saga: "saga.all.events\n(wildcard #)" { class: queue }
  DLX: "smartclinic.events.dlx\n(retry TTL + parking lot)" {
    shape: queue
    style: { fill: "#fef2f2"; stroke: "#dc2626"; stroke-dash: 4 }
  }
}

# ───── Consumers (right side) ─────
consumers: Consumers {
  style: { fill: "#f8fafc"; stroke: "#94a3b8"; stroke-dash: 3 }
  C_CLIN: Clinical { class: core }
  C_PHARM: Pharmacy { class: svc }
  C_LAB: Laboratory { class: svc }
  C_BILL: Billing { class: svc }
  C_SAGA: Saga Orchestrator {
    shape: hexagon
    style: { fill: "#ede9fe"; stroke: "#7c3aed"; stroke-width: 3; font-color: "#4c1d95" }
  }
}

# Publishing (via Outbox relay)
producers.PI    -> broker.EX: "patient.*.v1\n(via outbox)"      { style.stroke: "#f59e0b" }
producers.SCH   -> broker.EX: "scheduling.*.v1\n(via outbox)"    { style.stroke: "#f59e0b" }
producers.CLIN  -> broker.EX: "clinical.*.v1\n(via outbox)"      { style.stroke: "#dc2626"; style.stroke-width: 3 }
producers.PHARM -> broker.EX: "pharmacy.*.v1\n(via outbox)"      { style.stroke: "#16a34a" }
producers.LAB   -> broker.EX: "laboratory.*.v1\n(via outbox)"    { style.stroke: "#16a34a" }
producers.BILL  -> broker.EX: "billing.*.v1\n(via outbox)"       { style.stroke: "#16a34a" }

# Bindings
broker.EX -> broker.Q_clin: "scheduling.*.v1\npatient.*.v1"
broker.EX -> broker.Q_pharm: "clinical.encounter.prescription_issued.v1"
broker.EX -> broker.Q_lab: "clinical.encounter.lab_ordered.v1"
broker.EX -> broker.Q_bill_c: "clinical.encounter.finalised.v1"
broker.EX -> broker.Q_bill_l: "laboratory.result.recorded.v1\npharmacy.dispensing.completed.v1"
broker.EX -> broker.Q_saga: "# (wildcard)"

# Deliveries (idempotent via Inbox)
broker.Q_clin   -> consumers.C_CLIN:  "Inbox (idempotent)"
broker.Q_pharm  -> consumers.C_PHARM: "Inbox"
broker.Q_lab    -> consumers.C_LAB:   "Inbox"
broker.Q_bill_c -> consumers.C_BILL:  "Inbox"
broker.Q_bill_l -> consumers.C_BILL:  "Inbox"
broker.Q_saga   -> consumers.C_SAGA:  "Inbox"

# Dead-letter path
broker.Q_clin -> broker.DLX: "nack" { style: { stroke: "#dc2626"; stroke-dash: 4 } }
broker.DLX -> broker.EX: "retry" { style: { stroke: "#dc2626"; stroke-dash: 4 } }

footer: |md
  **Reliability:** transactional outbox + inbox = at-least-once delivery · exactly-once effect.
  **Routing key format:** `<context>.<entity>.<event>.v<N>`.
| {
  near: bottom-center
  shape: text
  style.font-size: 13
}
```

---

## 3 · Patient Visit Saga — `03-patient-visit-saga.d2`

```d2
# SmartClinic — Patient Visit Saga (Process Manager)
# Use D2's native sequence diagram (Diagramotion can animate step-by-step).

shape: sequence_diagram
title: Patient Visit Saga — Happy Path + Compensation Branch {
  near: top-center
  style.font-size: 22
}

R: Receptionist UI
SCH: Scheduling
SAGA: Saga Orchestrator
CLIN: Clinical
PHARM: Pharmacy
LAB: Laboratory
BILL: Billing

R -> SCH: 1. check-in appointment
SCH -> SAGA: "2. scheduling.appointment.checked_in.v1"
SAGA -> CLIN: 3. StartEncounter command
CLIN -> SAGA: "4. clinical.encounter.started.v1"

doctor_records: Doctor records encounter {
  CLIN -> CLIN: "5. record vitals / diagnosis / prescriptions / lab orders"
  CLIN -> PHARM: "6. clinical.encounter.prescription_issued.v1"
  CLIN -> LAB: "7. clinical.encounter.lab_ordered.v1"
}

happy: Happy path {
  PHARM -> SAGA: "8. pharmacy.dispensing.completed.v1"
  LAB -> SAGA: "9. laboratory.result.recorded.v1"
  CLIN -> BILL: "10. clinical.encounter.finalised.v1 → auto-invoice"
  BILL -> SAGA: "11. billing.invoice.issued.v1"
  BILL -> SAGA: "12. billing.invoice.paid.v1"
  SAGA -> SAGA: "13. saga.patient_visit.completed.v1 ✓"
}

compensation: "Compensation branch — drug out of stock" {
  PHARM -> SAGA: "8'. pharmacy.dispensing.rejected.v1\n(reason: out_of_stock)"
  SAGA -> CLIN: "9'. CompensateNotifyDoctor (substitute)"
  CLIN -> PHARM: "10'. clinical.encounter.prescription_issued.v1 (substituted)"
  PHARM -> SAGA: "11'. pharmacy.dispensing.completed.v1 (retry)"
}
```

---

## 4 · AWS Production Deployment — `04-aws-deployment.d2`

```d2
# SmartClinic — AWS production topology
# Diagramotion: reveal layers bottom-up: data → compute → edge.

direction: down

classes: {
  aws: {
    style: {
      fill: "#fff7ed"
      stroke: "#ff9900"
      stroke-width: 2
      font-color: "#7c2d12"
    }
  }
  data: {
    shape: cylinder
    style: { fill: "#eff6ff"; stroke: "#1e40af"; stroke-width: 2 }
  }
  compute: {
    style: { fill: "#ecfdf5"; stroke: "#047857"; stroke-width: 2 }
  }
  edge: {
    style: { fill: "#fef3c7"; stroke: "#ca8a04"; stroke-width: 2 }
  }
  security: {
    style: { fill: "#fce7f3"; stroke: "#be185d"; stroke-width: 2 }
  }
  obs: {
    style: { fill: "#f5f3ff"; stroke: "#6d28d9"; stroke-width: 2 }
  }
}

title: AWS Production Deployment — SmartClinic {
  near: top-center
  shape: text
  style: { font-size: 26; bold: true; font-color: "#0f172a" }
}

users: End Users {
  shape: person
  style.font-color: "#334155"
}

AWS: "AWS Cloud (af-south-1)" {
  class: aws

  # ── Edge ──
  edge: Edge {
    R53: Route 53 { class: edge; shape: cloud }
    CF: CloudFront { class: edge }
    WAF: "WAF\n(OWASP top-10)" { class: security }
    ACM: "ACM\nTLS certs" { class: security }
  }

  # ── Application VPC ──
  vpc: "VPC · smartclinic-prod" {
    style: { fill: "#fafafa"; stroke: "#64748b"; stroke-dash: 3 }

    public: Public subnets {
      ALB: "Application Load Balancer\npath routing" { class: edge }
    }

    private_app: Private app subnets {
      style: { fill: "#f0fdf4"; stroke: "#14532d"; stroke-dash: 2 }

      ECS: "ECS Fargate Cluster" { class: compute }

      T_PI: "Task · patient_identity" { class: compute }
      T_SCH: "Task · scheduling" { class: compute }
      T_CLIN: "Task · clinical\n(hash-chain ES+CQRS)" {
        class: compute
        style.bold: true
        style.stroke-width: 3
      }
      T_PHARM: "Task · pharmacy\n(ACL → RxNav)" { class: compute }
      T_LAB: "Task · laboratory" { class: compute }
      T_BILL: "Task · billing" { class: compute }
      T_SAGA: "Task · saga_orchestrator" { class: compute }
      T_FE: "Task · frontend (nginx)" { class: compute }

      ECR: "ECR\ncontainer images" { class: compute; shape: cylinder }
    }

    private_data: Private data subnets {
      style: { fill: "#eff6ff"; stroke: "#1e3a8a"; stroke-dash: 2 }

      RDS: "RDS PostgreSQL\nmulti-AZ · PITR\n(one DB per context)" { class: data }
      MQ: "Amazon MQ\n(RabbitMQ engine)" { class: data }
      SM: "Secrets Manager\nrotated creds" { class: security }
      KMS: "KMS\nenvelope encryption\ncrypto-shred keys" { class: security }
    }
  }

  # ── Off-VPC managed services ──
  obs: Observability {
    CW: "CloudWatch\nlogs + alarms" { class: obs }
    SNS: "SNS\n→ PagerDuty" { class: obs }
  }
  SES: "SES\ninvoice emails" { class: edge }
  IAM: "IAM\nOIDC trust · GitHub" { class: security }
}

ExtAPI: "External APIs" {
  RxNav: "RxNav / RxNorm" { shape: cloud; style.stroke-dash: 3 }
  Anthropic: "Anthropic API\nclaude-haiku-4-5" { shape: cloud; style.stroke-dash: 3 }
}

# ── Traffic ──
users -> AWS.edge.R53: "https://smartclinic.health"
AWS.edge.R53 -> AWS.edge.CF
AWS.edge.R53 -> AWS.vpc.public.ALB
AWS.edge.CF -> AWS.edge.WAF: OWASP
AWS.edge.CF -> AWS.vpc.private_app.T_FE: "origin (SPA)"

AWS.vpc.public.ALB -> AWS.vpc.private_app.T_PI: "/api/patients/*"
AWS.vpc.public.ALB -> AWS.vpc.private_app.T_SCH: "/api/appointments/*"
AWS.vpc.public.ALB -> AWS.vpc.private_app.T_CLIN: "/api/encounters/*"
AWS.vpc.public.ALB -> AWS.vpc.private_app.T_PHARM: "/api/prescriptions/*"
AWS.vpc.public.ALB -> AWS.vpc.private_app.T_LAB: "/api/lab/*"
AWS.vpc.public.ALB -> AWS.vpc.private_app.T_BILL: "/api/invoices/*"
AWS.vpc.public.ALB -> AWS.vpc.private_app.T_SAGA: "/api/saga/*"

# ── Data ──
AWS.vpc.private_app.T_PI -> AWS.vpc.private_data.RDS: db=patient_identity
AWS.vpc.private_app.T_SCH -> AWS.vpc.private_data.RDS: db=scheduling
AWS.vpc.private_app.T_CLIN -> AWS.vpc.private_data.RDS: "db=clinical_write + clinical_read"
AWS.vpc.private_app.T_PHARM -> AWS.vpc.private_data.RDS: db=pharmacy
AWS.vpc.private_app.T_LAB -> AWS.vpc.private_data.RDS: db=laboratory
AWS.vpc.private_app.T_BILL -> AWS.vpc.private_data.RDS: db=billing
AWS.vpc.private_app.T_SAGA -> AWS.vpc.private_data.RDS: db=saga

AWS.vpc.private_app.T_PI <-> AWS.vpc.private_data.MQ: AMQP
AWS.vpc.private_app.T_SCH <-> AWS.vpc.private_data.MQ
AWS.vpc.private_app.T_CLIN <-> AWS.vpc.private_data.MQ
AWS.vpc.private_app.T_PHARM <-> AWS.vpc.private_data.MQ
AWS.vpc.private_app.T_LAB <-> AWS.vpc.private_data.MQ
AWS.vpc.private_app.T_BILL <-> AWS.vpc.private_data.MQ
AWS.vpc.private_app.T_SAGA <-> AWS.vpc.private_data.MQ

# ── Security wiring ──
AWS.vpc.private_app.T_CLIN -> AWS.vpc.private_data.SM: rotated creds
AWS.vpc.private_app.T_CLIN -> AWS.vpc.private_data.KMS: per-record DEK

# ── External integrations ──
AWS.vpc.private_app.T_PHARM -> ExtAPI.RxNav: "HTTPS (via ACL)"
AWS.vpc.private_app.T_CLIN -> ExtAPI.Anthropic: "HTTPS (via Copilot Port)"
AWS.vpc.private_app.T_BILL -> AWS.SES: email

# ── Observability ──
AWS.vpc.private_app.ECS -> AWS.obs.CW: container logs + metrics
AWS.obs.CW -> AWS.obs.SNS: SLO breach
```

---

## 5 · CI/CD Pipeline — `05-cicd-pipeline.d2`

```d2
# SmartClinic — CI/CD pipeline
# A left-to-right pipeline. Animate by revealing each job sequentially.

direction: right

classes: {
  stage: {
    style: {
      fill: "#eff6ff"
      stroke: "#2563eb"
      stroke-width: 2
      font-color: "#1e3a8a"
      border-radius: 8
    }
  }
  gate: {
    shape: diamond
    style: { fill: "#fef3c7"; stroke: "#f59e0b"; stroke-width: 2 }
  }
  aws: {
    style: { fill: "#fff7ed"; stroke: "#ff9900"; stroke-width: 2 }
  }
  trigger: {
    shape: circle
    style: { fill: "#ede9fe"; stroke: "#7c3aed"; stroke-width: 2 }
  }
  fit: {
    style: { fill: "#ecfdf5"; stroke: "#10b981"; stroke-width: 3; bold: true }
  }
}

title: CI/CD Pipeline — GitHub Actions → AWS (blue/green on ECS) {
  near: top-center
  shape: text
  style: { font-size: 24; bold: true }
}

# ───── Source ─────
dev: Developer { shape: person }
repo: "GitHub Repo\n(push / PR)" { class: trigger }
wf: ".github/workflows/ci.yml" { class: trigger }

# ───── CI jobs ─────
ci: CI Jobs {
  style.fill: "#f8fafc"
  j1: "1. Lint\nruff" { class: stage }
  j2: "2. Typecheck\nmypy --strict" { class: stage }
  j3: "3. Unit tests\npytest" { class: stage }
  j4: "4. Architecture\nFitness Functions\n(no x-context imports)" { class: fit }
  j5: "5. Integration\ntestcontainers\nPostgres + RabbitMQ" { class: stage }
  j6: "6. Docker build\nmatrix × 8 images\nbuildx cache" { class: stage }
  j7: "7. Stack smoke\n`docker compose up`\nreadiness probes" { class: stage }
}

# ───── Gate ─────
gate: "Branch = main?\n(protected)" { class: gate }

# ───── CD ─────
cd: CD to AWS {
  style.fill: "#fff7ed"
  oidc: "OIDC federation\nGitHub → AWS IAM\n(no long-lived keys)" { class: aws }
  ecr: "ECR push\ntagged images" { class: aws }
  cdep: "CodeDeploy\nblue/green rollout" { class: aws }
  ecs: "ECS Fargate\nhealth-checked tasks" { class: aws }
  rollback: "Auto-rollback on\nALB health / CW alarm" { class: gate }
}

# ───── Observability feedback ─────
obs: "Grafana live\ntrace + metric + log\ncorrelated" {
  style: { fill: "#f5f3ff"; stroke: "#6d28d9"; stroke-width: 3 }
}

# Flow
dev -> repo: commit / PR
repo -> wf: trigger
wf -> ci.j1 -> ci.j2 -> ci.j3 -> ci.j4 -> ci.j5 -> ci.j6 -> ci.j7
ci.j7 -> gate
gate -> cd.oidc: main only
cd.oidc -> cd.ecr -> cd.cdep -> cd.ecs
cd.ecs -> cd.rollback: "canary window"
cd.rollback -> cd.ecs: green ✓ / blue ✗
cd.ecs -> obs: telemetry
obs -> dev: SLO breach → alert { style.stroke-dash: 4; style.stroke: "#dc2626" }

footer: |md
  **9 required checks** block merge. Deploys only from `main`. Zero long-lived cloud secrets — GitHub OIDC assumes a short-lived AWS IAM role.
| {
  near: bottom-center
  shape: text
  style.font-size: 13
}
```

---

## Tips for Diagramotion animation

1. **One SVG per diagram** — upload each of the five files separately and build five short animations, then chain them in your presentation.
2. **Use D2's `elk` layout** (`d2 --layout=elk …`) when compiling locally — it produces orthogonal edges that are much easier to trace with Diagramotion's "draw edge" animation.
3. **Keep container labels meaningful** — Diagramotion surfaces the SVG `<g>` IDs (D2 auto-derives them from your node names like `AWS.vpc.private_app.T_CLIN`). Descriptive names = easier layer selection.
4. **For sequence diagrams** (file 3) — Diagramotion animates each message arrow as its own layer, so the happy path + compensation branch become a natural step-through animation.
5. **Export with `--theme=0`** — the neutral palette animates better than dark themes. Our per-node colours come through regardless.
6. **Before uploading**, run the SVG through [svgomg](https://jakearchibald.github.io/svgomg/) with *Prettify code* ON and *Remove IDs* OFF — this keeps Diagramotion's layer detection working while shaving ~40 % off file size.

## Presentation ordering

If you're pairing these with the Ilograph animations, run **Ilograph** for the live interactive walkthrough and **Diagramotion** for the cinematic intro/transitions. Concretely:

- **Opening slide** → Diagramotion animation of *01-context-map*
- **Zoom into runtime** → Ilograph *Perspective 5* (event bus)
- **Storytelling transitions between sections** → Diagramotion clips of *03-patient-visit-saga* and *05-cicd-pipeline*
- **Deep technical Q&A** → Ilograph (interactive, zoomable, selectable)
