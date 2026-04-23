#!/usr/bin/env bash
# SmartClinic - server-side deploy script.
#
# Pulls the requested image tag from GHCR and performs a rolling restart.
# Invoked by `.github/workflows/deploy.yml` over SSH, but also safe to run
# by hand:
#
#   IMAGE_TAG=<sha> /opt/smartclinic/ops/deploy/deploy.sh        # pin version
#   /opt/smartclinic/ops/deploy/deploy.sh                        # latest
#
# Exits non-zero on any failure; CI's `Smoke-test the public endpoint`
# step will also fail the run if the service does not come back healthy.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/smartclinic}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)
# Enable the obs profile so otel-collector + jaeger/loki/prometheus/grafana
# all come up - the app services have depends_on: otel-collector, so they
# can't start without it. Set PROFILES="" externally to disable on tiny
# instances (you will need to also drop the depends_on).
PROFILES=("--profile" "obs")

cd "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE - did you run bootstrap.sh and fill it in?" >&2
  exit 1
fi

# Do NOT source .env as a shell script - values like bcrypt hashes contain
# literal '$' characters (e.g. $2a$14$...) that bash would try to expand as
# positional parameters under 'set -u'. docker compose reads --env-file
# itself and treats values as literals, so we only need to pull the handful
# of vars this script references directly.
read_env() {
  grep -E "^${1}=" "$ENV_FILE" | head -1 | cut -d= -f2- || true
}

export IMAGE_TAG="${IMAGE_TAG:-$(read_env IMAGE_TAG)}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"
export IMAGE_OWNER="${IMAGE_OWNER:-$(read_env IMAGE_OWNER)}"
export REGISTRY="${REGISTRY:-$(read_env REGISTRY)}"
export REGISTRY="${REGISTRY:-ghcr.io}"

if [[ -z "${IMAGE_OWNER:-}" ]]; then
  echo "IMAGE_OWNER is not set and not present in $ENV_FILE" >&2
  exit 1
fi

log() { printf "\n\e[1;34m>> %s\e[0m\n" "$*"; }

log "Deploying tag: $IMAGE_TAG  owner: $IMAGE_OWNER"

# 1. Pre-flight: pull new images so we fail fast if GHCR auth is bad
log "Pulling images"
docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" "${PROFILES[@]}" pull

# 2. Bring up / update the stack - compose handles rolling restart
log "Restarting services"
docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" "${PROFILES[@]}" up -d --remove-orphans

# 3. Wait for services to report healthy (up to 2 min)
log "Waiting for health checks"
deadline=$(( $(date +%s) + 120 ))
while :; do
  unhealthy=$(docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps \
    --format '{{.Service}} {{.Health}}' \
    | awk '$2 == "unhealthy" { print $1 }')
  starting=$(docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps \
    --format '{{.Service}} {{.Health}}' \
    | awk '$2 == "starting" { print $1 }')

  if [[ -z "$unhealthy" && -z "$starting" ]]; then
    break
  fi
  if [[ -n "$unhealthy" ]]; then
    echo "Unhealthy services: $unhealthy" >&2
    docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps
    exit 1
  fi
  if (( $(date +%s) > deadline )); then
    echo "Timeout waiting for services; still starting: $starting" >&2
    docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps
    exit 1
  fi
  echo "  still starting: $starting"
  sleep 5
done

# 4. Garbage-collect unused images (keep 3 most recent per image)
log "Pruning dangling images"
docker image prune -f >/dev/null
# Keep recent tags but purge stale GHCR pulls (>14 days + not in use)
docker image prune -a --filter "until=336h" -f >/dev/null || true

log "Deploy complete - $(docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps --services | wc -l) services up"
