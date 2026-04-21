# SmartClinic — Local Setup Guide

This guide walks you through running the complete SmartClinic stack on your local machine using Docker Compose. Everything — Postgres, RabbitMQ, Keycloak, all seven microservices, the Angular SPA, and the observability stack — starts with a single command.

---

## Prerequisites

| Tool | Minimum version | Check |
|---|---|---|
| Docker Desktop | 4.25+ (Engine 25+) | `docker --version` |
| Docker Compose | v2 (bundled with Docker Desktop) | `docker compose version` |
| Git | any | `git --version` |
| RAM | **8 GB free** | Grafana + Keycloak + 7 services is ~6 GB peak |
| Disk | 4 GB free | Images + volumes |

> **Windows users:** Ensure WSL 2 integration is enabled in Docker Desktop → Settings → Resources → WSL Integration.

---

## 1. Clone the repository

```bash
git clone <your-repo-url> SmartClinic
cd SmartClinic
```

---

## 2. Copy the environment template

```bash
cp .env.example .env
```

The defaults in `.env.example` are pre-wired for local Docker — no changes needed for a first run. Edit only if you want non-default passwords.

---

## 3. Start the full stack

```bash
docker compose up -d
```

Docker will:
1. Pull all images (~2–3 min on first run)
2. Build the seven Python service images and the Angular SPA image
3. Start every container in dependency order

Monitor startup progress:

```bash
docker compose ps          # shows health status for every container
docker compose logs -f     # stream all logs (Ctrl-C to exit)
```

### Expected startup time

| Phase | Duration |
|---|---|
| Postgres + RabbitMQ healthy | ~15 s |
| Keycloak ready (imports realm) | ~45–90 s |
| All services healthy | ~90–120 s |
| Angular build (first time) | ~3–5 min |

> **Tip:** The Angular image is only rebuilt when `frontend/` source files change. Subsequent `docker compose up` starts in seconds.

---

## 4. Verify everything is running

```bash
docker compose ps
```

All containers should show `healthy` or `running`:

| Container | Status | URL |
|---|---|---|
| smartclinic-postgres | healthy | — |
| smartclinic-rabbitmq | healthy | http://localhost:15672 |
| smartclinic-keycloak | healthy | http://localhost:8080 |
| smartclinic-frontend | healthy | **http://localhost:4200** |
| smartclinic-patient_identity | running | http://localhost:8001/docs |
| smartclinic-scheduling | running | http://localhost:8002/docs |
| smartclinic-clinical | running | http://localhost:8003/docs |
| smartclinic-pharmacy | running | http://localhost:8004/docs |
| smartclinic-laboratory | running | http://localhost:8005/docs |
| smartclinic-billing | running | http://localhost:8006/docs |
| smartclinic-saga | running | http://localhost:8007/docs |
| smartclinic-jaeger | running | http://localhost:16686 |
| smartclinic-prometheus | healthy | http://localhost:9090 |
| smartclinic-grafana | healthy | http://localhost:3000 |
| smartclinic-loki | healthy | — |
| smartclinic-mailhog | running | http://localhost:8025 |

---

## 5. Open the application

Navigate to **http://localhost:4200**

The splash screen appears while Keycloak authenticates. You will be redirected to the Keycloak login page automatically.

### Seeded test users

| Username | Password | Role | What they can do |
|---|---|---|---|
| `doctor1` | `doctor1` | Doctor | Start encounters, record vitals/SOAP/diagnoses, issue prescriptions and lab orders, close encounters |
| `recep1` | `recep1` | Receptionist | Register patients, book/manage appointments |
| `pharm1` | `pharm1` | Pharmacist | View and dispense/reject prescriptions |
| `acct1` | `acct1` | Accounts | Manage invoices, record payments |
| `lab1` | `lab1` | Lab Technician | Collect samples, record results, complete lab orders |

---

## 6. Typical demo flow

Follow this sequence to exercise the full Patient Visit Saga across all bounded contexts:

```
Receptionist                  Doctor                    Lab Tech            Accounts
     │                           │                          │                   │
  Register                  Start Encounter             Collect              Record
  Patient  ──────────────►  (Clinical BC)               Sample   ─────────►  Payment
     │                           │                          │                   │
  Book                       Record Vitals,             Record              Visit
  Appointment  ──────────►   SOAP Note,                 Result   ─────────►  Complete
                              Diagnoses                    │                   │
                               │                       Complete               │
                          Place Lab Order  ─────────►  Order                  │
                               │                                              │
                          Close Encounter  ──────────────────────────────►  Invoice
                               │                                            Issued
                          Issue Prescription
```

### Step by step

1. **Register patient** → Patients → Register Patient
   - Fill name, date of birth, national ID, phone
2. **Book appointment** → Appointments → Book Appointment
   - Select the registered patient, choose a doctor, pick a date/time
3. **Check in** → Appointments → open the booking → Check In
4. **Start encounter** → Encounters → Start Encounter → select the patient
5. **Record vitals** → on the encounter detail, fill in temperature/pulse/BP/SpO₂
6. **Record SOAP note** → Subjective / Objective / Assessment / Plan
7. **Add diagnosis** → enter ICD-10 code (e.g. `J06.9`) and description
8. **Place lab order** → use the "View Lab Orders" link → *(or the Clinical API endpoint)*
9. **Lab work** → log in as `lab1` → Lab Orders → open the order → Collect Sample → Record Result → Mark Complete
10. **Close encounter** → log in as `doctor1` → Encounters → open encounter → Close & Sign
11. **Dispense prescription** → log in as `pharm1` → Prescriptions → Dispense
12. **Pay invoice** → log in as `acct1` → Invoices → open invoice → Issue → Record Payment
13. **Track journey** → Visit Tracker (visible to all roles)

---

## 7. Observability

### Distributed traces — Jaeger

Open **http://localhost:16686**

Select a service from the dropdown (e.g. `clinical`) and click **Find Traces** to see request spans across microservices.

### Metrics — Grafana

Open **http://localhost:3000** (login: `admin` / `admin`)

The pre-provisioned **SmartClinic Overview** dashboard shows RED signals (Request rate, Error rate, Duration) per service and RabbitMQ queue depths.

### Logs — Loki (via Grafana)

In Grafana → Explore → select **Loki** datasource → query:

```logql
{service_name="clinical"} | json | line_format "{{.message}}"
```

Every log line includes `trace_id`, `correlation_id`, and structured fields — cross-link from a Jaeger trace directly to its logs.

### RabbitMQ management

Open **http://localhost:15672** (login: `smartclinic` / `smartclinic`)

Watch queue depths and message rates on the `smartclinic.events` topic exchange in real time.

### Email (MailHog)

Open **http://localhost:8025** to see notification emails sent by the Billing service (invoice issued, payment confirmed).

---

## 8. FastAPI interactive docs

Every service exposes Swagger UI and ReDoc at its own port:

```
http://localhost:8001/docs   — Patient Identity
http://localhost:8002/docs   — Scheduling
http://localhost:8003/docs   — Clinical
http://localhost:8004/docs   — Pharmacy
http://localhost:8005/docs   — Laboratory
http://localhost:8006/docs   — Billing
http://localhost:8007/docs   — Saga Orchestrator
```

To call a protected endpoint directly from Swagger UI, you need a Bearer token:

```bash
# Get a token for doctor1
TOKEN=$(curl -s \
  -d "client_id=smartclinic-api" \
  -d "client_secret=smartclinic-api-secret" \
  -d "username=doctor1" \
  -d "password=doctor1" \
  -d "grant_type=password" \
  http://localhost:8080/realms/smartclinic/protocol/openid-connect/token \
  | python3 -m json.tool | grep access_token | awk -F'"' '{print $4}')

echo $TOKEN   # paste into Swagger UI → Authorize → Bearer <token>
```

---

## 9. Development (without Docker)

To run a service locally against the Docker-hosted infrastructure:

```bash
# 1. Start only infrastructure (skip services and frontend)
docker compose up -d postgres rabbitmq keycloak otel-collector

# 2. Navigate into a service
cd services/clinical

# 3. Create a local .env (copy from .env.example, point to localhost)
cp ../../.env.example .env
# Edit DATABASE_URL, RABBITMQ_URL, OIDC_ISSUER, etc. to use localhost ports

# 4. Run with uv
uv run uvicorn clinical.main:app --reload --port 8003
```

For the Angular dev server:

```bash
cd frontend
npm install
npm start          # serves at http://localhost:4200 with HMR
```

The dev server proxies nothing — it uses `environment.ts` which points directly to `localhost:8001-8007`.

---

## 10. Common commands

```bash
# Rebuild and restart everything
docker compose down && docker compose up -d --build

# Rebuild only the Angular SPA (after frontend changes)
docker compose build frontend && docker compose up -d frontend

# Rebuild only one service
docker compose build clinical && docker compose up -d clinical

# View logs for a specific service
docker compose logs -f clinical

# Stop everything (preserves volumes/data)
docker compose down

# Stop everything AND wipe all data volumes (clean slate)
docker compose down -v

# Run tests for a service
docker compose exec clinical uv run pytest tests/ -q

# Open a psql shell
docker compose exec postgres psql -U postgres
```

---

## 11. Ports quick-reference

| Port | Service |
|---|---|
| **4200** | Angular SPA (nginx) |
| 5432 | PostgreSQL |
| 5672 | RabbitMQ AMQP |
| **8001** | Patient Identity API |
| **8002** | Scheduling API |
| **8003** | Clinical API |
| **8004** | Pharmacy API |
| **8005** | Laboratory API |
| **8006** | Billing API |
| **8007** | Saga Orchestrator API |
| **8025** | MailHog UI |
| **8080** | Keycloak |
| 9000 | Keycloak management |
| 9090 | Prometheus |
| **15672** | RabbitMQ Management UI |
| **16686** | Jaeger UI |
| **3000** | Grafana |
| 3100 | Loki |
| 4317 | OTLP gRPC (collector) |

---

## 12. Troubleshooting

### Keycloak takes too long to start

```bash
docker compose logs keycloak | tail -30
```

Keycloak imports the realm on first boot, which takes 60–90 seconds on slower machines. Wait for the log line:
```
Keycloak 25.0.x ... started in ...
```

### Service fails with "authentication not configured"

The `OIDC_JWKS_URL` env var is not set. Verify all services in `docker-compose.yml` have:
```yaml
OIDC_ISSUER: http://localhost:8080/realms/smartclinic
OIDC_JWKS_URL: http://keycloak:8080/realms/smartclinic/protocol/openid-connect/certs
```

### JWT validation fails ("token rejected: Invalid audience")

The `smartclinic-web` Keycloak client must have the `smartclinic-api-audience` protocol mapper. This is included in the realm import file (`ops/keycloak/smartclinic-realm.json`). If you have a stale Keycloak volume, wipe it:

```bash
docker compose down -v
docker compose up -d
```

### Angular blank page (no spinner)

Open browser DevTools → Console. If you see a Keycloak CORS error, ensure the `smartclinic-web` client has `http://localhost:4200` in its **Web Origins** list. This is pre-configured in the realm JSON.

### Port conflict

```bash
# Find which process uses port 4200
netstat -ano | findstr :4200    # Windows
lsof -i :4200                   # macOS/Linux
```

Stop the conflicting process or change the host port in `docker-compose.yml`.

### Out of memory

Reduce resource limits in `docker-compose.yml` or add a lean profile:

```bash
# Start only infrastructure without observability stack
docker compose up -d postgres rabbitmq keycloak
```

---

## Architecture overview

```
Browser (localhost:4200)
   │
   ├── Keycloak PKCE login ──────────────────► localhost:8080 (Keycloak)
   │
   └── nginx (frontend container)
         ├── /                    → Angular SPA (index.html)
         ├── /api/patients/*      → patient_identity:8000
         ├── /api/scheduling/*    → scheduling:8000
         ├── /api/clinical/*      → clinical:8000
         ├── /api/pharmacy/*      → pharmacy:8000
         ├── /api/laboratory/*    → laboratory:8000
         ├── /api/billing/*       → billing:8000
         └── /api/saga/*          → saga_orchestrator:8000

All services → postgres (per-context DB) + rabbitmq (event bus)
Events → otel-collector → Jaeger (traces) + Prometheus (metrics) + Loki (logs)
```

The **Patient Visit Saga** orchestrates the cross-context lifecycle:
`Appointment checked-in → Encounter open → Lab orders → Encounter closed → Invoice issued → Invoice paid → Saga completed`
