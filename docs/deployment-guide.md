# SmartClinic — Linode Deployment Guide (HTTP @ `http://172.236.3.27`)

> Copy-paste walkthrough for deploying SmartClinic to an Ubuntu VPS on
> Linode with an auto-deploy pipeline from GitHub Actions.
>
> **This guide configures plain HTTP on a public IP — no domain, no
> Let's Encrypt.** Appropriate for the academic demo; not appropriate
> for real patient data. The two files that change if you later attach
> a domain + TLS are `ops/caddy/Caddyfile` and `ops/deploy/.env.prod.example`.

## What you'll end up with

```
┌─ GitHub push to main ─────────────────────────────────┐
│                                                       │
│  .github/workflows/ci.yml       ← lint / test / build │
│  .github/workflows/deploy.yml   ← push → GHCR → SSH   │
│                                                       │
└───────────────┬───────────────────────────────────────┘
                │  (1) OIDC + GITHUB_TOKEN
                ▼
       ┌──────────────────┐
       │   GHCR (ghcr.io) │   8 images tagged :<sha> + :latest
       └────────┬─────────┘
                │  (2) SSH appleboy/ssh-action
                ▼
       ┌──────────────────────────────────────────┐
       │  Linode Ubuntu 24.04 · 172.236.3.27      │
       │                                          │
       │  Caddy (port 80) ─► Angular SPA          │
       │                    ├► 7 FastAPI services │
       │                    └► Keycloak (/auth/)  │
       │  Postgres · RabbitMQ · Keycloak          │
       │  (optional: Jaeger · Prom · Loki · Graf) │
       │                                          │
       │  ufw · fail2ban · nightly pg_dump        │
       └──────────────────────────────────────────┘
```

---

## Prerequisites

- A Linode instance at **172.236.3.27** running **Ubuntu 24.04 LTS**
  (22.04 also works). Minimum size: `g6-standard-2` (4 GB RAM,
  2 vCPU, 80 GB SSD). The observability profile adds ~1.2 GB RAM —
  leave it disabled if your instance is smaller.
- The SmartClinic repo on GitHub (your fork or this repo).
- Terminal with `ssh` + `ssh-keygen` installed locally.

---

## Step 1 — Generate a deploy SSH key (on your laptop)

This key is used *only* by GitHub Actions to SSH into the Linode.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/smartclinic_deploy -C "github-actions-deploy" -N ""
```

You now have:
- `~/.ssh/smartclinic_deploy`      ← **private** (goes into GitHub Secrets)
- `~/.ssh/smartclinic_deploy.pub`  ← public (goes onto the server)

Print them so you can copy when prompted:

```bash
cat ~/.ssh/smartclinic_deploy.pub   # copy this now (for server)
cat ~/.ssh/smartclinic_deploy       # copy this later (for GitHub Secrets)
```

---

## Step 2 — Bootstrap the server (one-time)

```bash
# ── From your laptop ─────────────────────────────────────
ssh root@172.236.3.27

# Add the deploy public key to root (bootstrap creates `smartclinic` next)
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys <<'PASTE_PUBLIC_KEY'
<paste the contents of ~/.ssh/smartclinic_deploy.pub here>
PASTE_PUBLIC_KEY
chmod 600 ~/.ssh/authorized_keys
```

Now run the one-time bootstrap. **Edit `REPO_URL` to point at your fork**
(the repo GitHub Actions will publish images from):

```bash
# still on the server, as root
export REPO_URL="https://github.com/<YOUR_GITHUB_USER>/SmartClinic.git"
export APP_USER="smartclinic"
export TIMEZONE="Africa/Harare"

curl -fsSL "$REPO_URL/raw/main/ops/deploy/bootstrap.sh" | bash
```

What bootstrap does:

1. APT update + base packages (git, ufw, fail2ban, cron, …).
2. Installs Docker Engine + Compose plugin from Docker's official repo.
3. Creates a non-root `smartclinic` user in the `docker` group.
4. Opens ports **22, 80** with `ufw`; everything else denied inbound.
   (Port 443 is not opened — no TLS yet.)
5. Hardens sshd, enables fail2ban on sshd, enables unattended upgrades.
6. Clones the repo to `/opt/smartclinic`.
7. Copies `ops/deploy/.env.prod.example` → `/opt/smartclinic/.env` (mode 600).
8. Installs the nightly Postgres backup cron + log rotation.
9. Tunes the Docker daemon (log caps, live-restore).

Copy the deploy public key to the `smartclinic` user so CI can SSH as it:

```bash
install -d -o smartclinic -g smartclinic -m 700 /home/smartclinic/.ssh
cp ~/.ssh/authorized_keys /home/smartclinic/.ssh/authorized_keys
chown smartclinic:smartclinic /home/smartclinic/.ssh/authorized_keys
chmod 600 /home/smartclinic/.ssh/authorized_keys
```

---

## Step 3 — Fill in production secrets

```bash
sudo -u smartclinic nano /opt/smartclinic/.env
```

Minimum edits:

| Variable | Value |
|---|---|
| `DEPLOY_HOST` | `172.236.3.27` |
| `IMAGE_OWNER` | your GitHub username/org (**lowercase**) |
| `POSTGRES_PASSWORD` | long random password |
| `RABBITMQ_DEFAULT_PASS` | long random password |
| `KEYCLOAK_ADMIN_PASSWORD` | long random password |
| `GRAFANA_BASICAUTH_HASH` | bcrypt hash (command below) |
| `ANTHROPIC_API_KEY` | (optional) for the AI copilot |

Generate strong passwords & the bcrypt hash:

```bash
# strong random password
openssl rand -base64 36

# bcrypt hash for Grafana basicauth
docker run --rm caddy:2.8-alpine caddy hash-password --plaintext 'your-plain-password'
```

---

## Step 4 — Log the server into GHCR (pull images)

If your repo is **public**, skip this — GHCR images will be public.
If your repo is **private**, create a GitHub PAT with `read:packages`
scope (**Settings → Developer settings → Personal access tokens →
Tokens (classic)**) and:

```bash
sudo -u smartclinic bash -c \
  'echo <YOUR_PAT> | docker login ghcr.io -u <YOUR_GITHUB_USER> --password-stdin'
```

---

## Step 5 — Wire up GitHub Actions secrets

In your GitHub repo → **Settings → Secrets and variables → Actions →
New repository secret**:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | `172.236.3.27` |
| `DEPLOY_USER` | `smartclinic` |
| `DEPLOY_PORT` | `22` |
| `DEPLOY_SSH_KEY` | **entire contents** of `~/.ssh/smartclinic_deploy` (the private key, including the BEGIN/END lines) |

No AWS secrets needed. `GITHUB_TOKEN` is auto-provided for GHCR push.

Also in the same settings → **Environments → New environment →
`production`**. Optional: require a reviewer for deploys.

---

## Step 6 — First deploy

```bash
# from your laptop
git push origin main
```

Watch **GitHub → Actions → Deploy to Linode**. In ~10 minutes:

1. ✅ 8 `build-push` jobs green (7 services + frontend).
2. ✅ `deploy` job green (SSH in, `git pull`, `docker compose pull`,
   rolling restart, wait-for-health).
3. ✅ Smoke-test `http://172.236.3.27/health` returns `ok`.

Open `http://172.236.3.27/` in a browser — Angular SPA should load.

Endpoints after deploy:

| URL | What |
|---|---|
| `http://172.236.3.27/` | Angular SPA |
| `http://172.236.3.27/health` | Caddy aggregate health (200 "ok") |
| `http://172.236.3.27/auth/` | Keycloak admin console |
| `http://172.236.3.27/api/patients/health/live` | Per-service health |
| `http://172.236.3.27/grafana/` | (if obs profile enabled) |

---

## Step 7 — Routine operations

### Deploy a new version
Push to `main`. CI runs, then the deploy workflow runs automatically.

### Roll back
**GitHub → Actions → Deploy to Linode → Run workflow →
`image_tag = <old-sha>`**. Server pulls that tag and restarts.

### Tail logs
```bash
ssh smartclinic@172.236.3.27
cd /opt/smartclinic
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f clinical
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### Shell into a service
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec clinical bash
```

### Enable the observability stack (Grafana/Jaeger/Prometheus/Loki)
Edit `/opt/smartclinic/ops/deploy/deploy.sh`, uncomment:

```bash
# PROFILES=("--profile" "default" "--profile" "obs")
```

Then:

```bash
/opt/smartclinic/ops/deploy/deploy.sh
```

Grafana at `http://172.236.3.27/grafana/` behind basicauth.

### Restore a backup
```bash
ls /var/backups/smartclinic/daily/
gunzip -c /var/backups/smartclinic/daily/<STAMP>_clinical_write.dump.gz | \
  docker exec -i smartclinic-postgres pg_restore -U postgres -d clinical_write --clean --if-exists
```

### Verify the Clinical hash-chain against a restored dump
```bash
curl -X POST http://172.236.3.27/api/encounters/verify-chain \
  -H "Authorization: Bearer <doctor_token>" \
  -d '{"aggregate_id": "<encounter_uuid>"}'
```

### Wipe and re-seed (demo reset)
```bash
cd /opt/smartclinic
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
./ops/deploy/deploy.sh
docker compose --profile seed run --rm seeder
```

---

## Architecture of the pipeline (recap)

| File | Purpose |
|---|---|
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | lint · typecheck · unit · fitness · integration · build · smoke |
| [.github/workflows/deploy.yml](../.github/workflows/deploy.yml) | build 8 images · push to GHCR · SSH deploy · smoke-test |
| [docker-compose.yml](../docker-compose.yml) | full dev stack (builds from Dockerfiles) |
| [docker-compose.prod.yml](../docker-compose.prod.yml) | prod override: GHCR images, Caddy on :80, no public DB/broker ports |
| [ops/caddy/Caddyfile](../ops/caddy/Caddyfile) | HTTP reverse proxy, security headers, path routing, basicauth on Grafana |
| [ops/deploy/bootstrap.sh](../ops/deploy/bootstrap.sh) | idempotent server bootstrap |
| [ops/deploy/deploy.sh](../ops/deploy/deploy.sh) | server-side pull + rolling restart + health-wait + prune |
| [ops/deploy/backup.sh](../ops/deploy/backup.sh) | nightly pg_dump + hash-chain anchor + rotation + optional S3 |
| [ops/deploy/.env.prod.example](../ops/deploy/.env.prod.example) | production env template |

## Troubleshooting

**Nothing loads at http://172.236.3.27/**
Check ufw (`sudo ufw status` — 80 must be open), that Caddy is running
(`docker ps | grep caddy`), and that port 80 isn't held by something else
(`sudo ss -tlnp | grep :80`).

**`docker compose pull` returns 401 unauthorized.**
Server isn't logged into GHCR. Re-run the `docker login ghcr.io` from
Step 4, then re-run `deploy.sh`.

**Services restart-loop.**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs <service>
```
Usually a typo in `.env` or a wrong `OIDC_ISSUER`. Confirm it reads
`http://172.236.3.27/auth/realms/smartclinic` exactly (no trailing slash).

**Keycloak "Invalid redirect URI" on login.**
Keycloak's realm import lists allowed redirect URIs. In the Keycloak
admin console (`http://172.236.3.27/auth/`) open the `smartclinic`
realm → Clients → your SPA client → Valid Redirect URIs — add
`http://172.236.3.27/*`.

**`/api/...` returns 502 from Caddy.**
Caddy came up before the service was healthy. Re-run `deploy.sh` — it
now waits for health before returning.

**Ran out of disk.**
```bash
docker image prune -a -f
```
Or shorten `RETAIN_DAYS` in `/usr/local/bin/smartclinic-backup`.

---

## Security notes — HTTP on a public IP

- **Keycloak tokens ride over HTTP.** Anyone sniffing your network path
  can replay them. Rotate passwords after the demo; never paste real
  PII into this deployment.
- **No HSTS / no `Secure` cookies.** The hardening headers Caddy still
  sets (X-Content-Type-Options, X-Frame-Options, Referrer-Policy) give
  partial defence in depth but do not substitute for TLS.
- **ufw still blocks** Postgres / RabbitMQ / Keycloak direct ports —
  those services are only reachable inside the Docker network.
- **Nightly backups + hash-chain anchor** still run exactly as designed
  (ADR-0012); the integrity guarantee is cryptographic and does not
  depend on TLS.

## Upgrading to HTTPS later

When you attach a domain (e.g. `smartclinic.example.com`):

1. Point an A record at `172.236.3.27`.
2. Open port 443 in ufw: `sudo ufw allow 443/tcp && sudo ufw allow 443/udp`.
3. Replace `ops/caddy/Caddyfile` with the HTTPS variant (remove
   `auto_https off` and the `:80 { … }` block; replace with
   `{$DEPLOY_DOMAIN} { … }`).
4. In `/opt/smartclinic/.env` set `DEPLOY_HOST=smartclinic.example.com`
   and add `ACME_EMAIL=ops@example.com`.
5. In Keycloak admin, change `KC_HOSTNAME_STRICT_HTTPS` to `true`.
6. Update the `OIDC_ISSUER` to `https://…`.
7. Re-run `./ops/deploy/deploy.sh`. Caddy provisions the cert on first
   request.
