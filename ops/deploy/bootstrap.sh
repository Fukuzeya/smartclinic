#!/usr/bin/env bash
# SmartClinic - one-time Linode/Ubuntu bootstrap.
#
# Run ONCE on a fresh Ubuntu 22.04 / 24.04 server as root (or via sudo).
# Idempotent - safe to re-run; will skip steps that are already done.
#
#   curl -fsSL https://raw.githubusercontent.com/<OWNER>/<REPO>/main/ops/deploy/bootstrap.sh | sudo bash
# or:
#   sudo ./ops/deploy/bootstrap.sh

set -euo pipefail

# --- Config (override via environment) ------------------------------------
APP_USER="${APP_USER:-smartclinic}"
APP_DIR="${APP_DIR:-/opt/smartclinic}"
REPO_URL="${REPO_URL:-https://github.com/CHANGE-ME/SmartClinic.git}"
SSH_PORT="${SSH_PORT:-22}"
TIMEZONE="${TIMEZONE:-Africa/Harare}"

log()  { printf "\n\e[1;34m>> %s\e[0m\n" "$*"; }
warn() { printf "\n\e[1;33m!! %s\e[0m\n" "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root (use sudo)." >&2
  exit 1
fi

# --- 1. System update + baseline packages ---------------------------------
log "Updating APT and installing baseline packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y \
  ca-certificates curl gnupg lsb-release \
  git ufw fail2ban unattended-upgrades \
  jq htop tmux vim rsync logrotate cron \
  postgresql-client-16 || apt-get install -y postgresql-client

timedatectl set-timezone "$TIMEZONE"

# --- 2. Docker Engine + Compose plugin (official repo) --------------------
if ! command -v docker &>/dev/null; then
  log "Installing Docker Engine"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "Docker already installed - skipping"
fi

# --- 3. Deploy user -------------------------------------------------------
if ! id "$APP_USER" &>/dev/null; then
  log "Creating deploy user: $APP_USER"
  useradd --create-home --shell /bin/bash --groups docker "$APP_USER"
  # No password login; SSH keys only
  passwd -l "$APP_USER"
else
  log "User $APP_USER already exists - ensuring docker group membership"
  usermod -aG docker "$APP_USER"
fi

install -d -o "$APP_USER" -g "$APP_USER" -m 0750 /home/"$APP_USER"/.ssh

# --- 4. Firewall (ufw) ----------------------------------------------------
log "Configuring ufw"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT"/tcp comment 'SSH'
ufw allow 80/tcp  comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS (future)'
ufw --force enable

# --- 5. SSH hardening -----------------------------------------------------
log "Hardening sshd"
SSHD="/etc/ssh/sshd_config.d/smartclinic.conf"
cat > "$SSHD" <<EOF
PasswordAuthentication no
PermitRootLogin prohibit-password
KbdInteractiveAuthentication no
UsePAM yes
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers root $APP_USER
EOF

# Validate config before applying - never risk locking ourselves out.
if ! sshd -t; then
  warn "sshd config test failed; removing $SSHD"
  rm -f "$SSHD"
  exit 1
fi

# Ubuntu 24.04 uses socket activation (ssh.socket -> ssh@.service per-connection);
# 22.04 and older run ssh.service as a long-lived daemon. Some distros still use
# the legacy sshd.service name. Handle all three without aborting.
if systemctl cat ssh.socket &>/dev/null; then
  systemctl restart ssh.socket
  log "Restarted ssh.socket (socket-activated sshd; new connections pick up config)"
fi
if systemctl is-active --quiet ssh; then
  systemctl reload ssh
elif systemctl is-active --quiet sshd; then
  systemctl reload sshd
else
  log "No long-lived ssh service running; relying on socket activation"
fi

# --- 6. fail2ban ----------------------------------------------------------
log "Enabling fail2ban for sshd"
cat > /etc/fail2ban/jail.d/smartclinic.conf <<EOF
[sshd]
enabled = true
port    = $SSH_PORT
maxretry = 5
bantime = 1h
findtime = 10m
EOF
systemctl enable --now fail2ban

# --- 7. Unattended security upgrades --------------------------------------
log "Enabling unattended-upgrades"
dpkg-reconfigure -f noninteractive unattended-upgrades

# --- 8. Application directory + repo clone -------------------------------
if [[ ! -d "$APP_DIR/.git" ]]; then
  log "Cloning $REPO_URL to $APP_DIR"
  git clone --depth 50 "$REPO_URL" "$APP_DIR"
  chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
else
  log "Repo already present at $APP_DIR - skipping clone"
fi
git config --global --add safe.directory "$APP_DIR"
sudo -u "$APP_USER" git config --global --add safe.directory "$APP_DIR"

# --- 9. Secrets scaffolding -----------------------------------------------
ENV_FILE="$APP_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  log "Copying env template (edit $ENV_FILE before first deploy!)"
  cp "$APP_DIR/ops/deploy/.env.prod.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  chown "$APP_USER":"$APP_USER" "$ENV_FILE"
  warn "You MUST edit $ENV_FILE now and fill in every CHANGE_ME value."
fi

# --- 10. Backups ----------------------------------------------------------
log "Installing nightly Postgres backup"
BACKUP_DIR="/var/backups/smartclinic"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$BACKUP_DIR"
install -m 0755 "$APP_DIR/ops/deploy/backup.sh" /usr/local/bin/smartclinic-backup
cat > /etc/cron.d/smartclinic-backup <<EOF
# Nightly backup at 01:30 server time
30 1 * * * $APP_USER /usr/local/bin/smartclinic-backup >> /var/log/smartclinic-backup.log 2>&1
EOF
touch /var/log/smartclinic-backup.log
chown "$APP_USER":"$APP_USER" /var/log/smartclinic-backup.log
cat > /etc/logrotate.d/smartclinic <<'EOF'
/var/log/smartclinic-backup.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}
EOF

# --- 11. Docker daemon: log caps + live-restore ---------------------------
log "Tuning Docker daemon (log caps, live-restore)"
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "5" },
  "live-restore": true,
  "default-ulimits": { "nofile": { "Name": "nofile", "Hard": 65536, "Soft": 65536 } }
}
EOF
systemctl restart docker

# --- Done -----------------------------------------------------------------
log "Bootstrap complete."
cat <<EOF

---------------------------------------------------------------------------
NEXT STEPS

1. Fill in production secrets:
     sudo -u $APP_USER nano $ENV_FILE

2. Log this server into GHCR so it can pull private images
   (skip if your images are public):
     sudo -u $APP_USER bash -c 'echo <PAT> | docker login ghcr.io -u <USER> --password-stdin'

3. First deploy (manual):
     sudo -u $APP_USER $APP_DIR/ops/deploy/deploy.sh

4. From now on, pushing to main will build images on GitHub Actions,
   push them to GHCR, SSH in here, and run deploy.sh automatically.

5. Browse to: http://172.236.3.27
---------------------------------------------------------------------------
EOF
