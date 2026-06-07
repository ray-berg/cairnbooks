#!/usr/bin/env bash
# =============================================================================
# CairnBooks — Proxmox LXC Provisioning Script
#
# Usage: run this script ON the Proxmox host (or via SSH to it).
#
#   sudo bash infra/proxmox/provision.sh
#
# Override any variable via the environment:
#
#   CTID=201 HOSTNAME=cairnbooks DOMAIN=example.com \
#   DDNS_PROVIDER=cloudflare DDNS_TOKEN=<api-token> \
#   sudo -E bash infra/proxmox/provision.sh
#
# See docs/deployment/proxmox.md for full configuration reference.
# Version: 1.0.0
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

# Container identity
CTID="${CTID:-200}"
HOSTNAME="${HOSTNAME:-cairnbooks}"
DOMAIN="${DOMAIN:-example.com}"
FQDN="${HOSTNAME}.${DOMAIN}"

# LXC resources
CORES="${CORES:-2}"
MEMORY="${MEMORY:-2048}"          # MiB
SWAP="${SWAP:-512}"               # MiB
DISK="${DISK:-20}"                # GiB root disk
STORAGE="${STORAGE:-local-lvm}"   # Proxmox storage pool for disk
BRIDGE="${BRIDGE:-vmbr0}"         # Proxmox network bridge

# Network — leave IPADDR empty to use DHCP
IPADDR="${IPADDR:-}"              # e.g. "192.168.1.50/24"  (CIDR notation)
GATEWAY="${GATEWAY:-}"            # e.g. "192.168.1.1"
DNS_SERVER="${DNS_SERVER:-1.1.1.1}"

# LXC template (Ubuntu 22.04)
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
OSTEMPLATE="${OSTEMPLATE:-ubuntu-22.04-standard_22.04-1_amd64.tar.zst}"

# Dynamic DNS — set DDNS_TOKEN to enable; leave empty to skip
DDNS_PROVIDER="${DDNS_PROVIDER:-cloudflare}"   # cloudflare | duckdns | noip
DDNS_ZONE="${DDNS_ZONE:-${DOMAIN}}"
DDNS_TOKEN="${DDNS_TOKEN:-}"                   # Cloudflare API token / provider password

# SSH public key injected into root account (skip if file missing)
SSH_PUBKEY="${SSH_PUBKEY:-${HOME}/.ssh/id_rsa.pub}"

# ── Helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }
require_cmd() { command -v "$1" &>/dev/null || die "Required command '$1' not found — are you on a Proxmox host?"; }

# ── Preflight checks ──────────────────────────────────────────────────────────

log "=== CairnBooks LXC Provisioning ==="
log "CTID=${CTID}  HOSTNAME=${FQDN}"

[[ "${EUID}" -eq 0 ]] || die "This script must be run as root."

require_cmd pvesh
require_cmd pct
require_cmd pvesm
require_cmd pveam

# ── Ensure LXC template is available ─────────────────────────────────────────

log "Checking for LXC template: ${OSTEMPLATE}"
TMPL_PATH="$(pvesm path "${TEMPLATE_STORAGE}:vztmpl/${OSTEMPLATE}" 2>/dev/null || true)"

if [[ -z "${TMPL_PATH}" || ! -f "${TMPL_PATH}" ]]; then
    log "Template not cached — downloading from Proxmox appliance list..."
    pveam update
    pveam download "${TEMPLATE_STORAGE}" "${OSTEMPLATE}" || \
        die "Failed to download '${OSTEMPLATE}'. Run 'pveam available --section system' to find a valid name."
    TMPL_PATH="$(pvesm path "${TEMPLATE_STORAGE}:vztmpl/${OSTEMPLATE}")"
fi

log "Template ready: ${TMPL_PATH}"

# ── Create LXC container ──────────────────────────────────────────────────────

if pct status "${CTID}" &>/dev/null; then
    log "Container ${CTID} already exists — skipping creation."
else
    log "Creating LXC container ${CTID}..."

    # Build network string
    NETCFG="name=eth0,bridge=${BRIDGE},firewall=1"
    if [[ -n "${IPADDR}" ]]; then
        NETCFG+=",ip=${IPADDR}"
        [[ -n "${GATEWAY}" ]] && NETCFG+=",gw=${GATEWAY}"
    else
        NETCFG+=",ip=dhcp"
        log "No IPADDR set — using DHCP."
    fi

    # SSH key injection (optional)
    PUBKEY_ARGS=()
    if [[ -f "${SSH_PUBKEY}" ]]; then
        PUBKEY_ARGS=(--ssh-public-keys "${SSH_PUBKEY}")
    else
        log "WARNING: SSH public key '${SSH_PUBKEY}' not found — skipping key injection."
    fi

    pct create "${CTID}" \
        "${TEMPLATE_STORAGE}:vztmpl/${OSTEMPLATE}" \
        --hostname   "${FQDN}" \
        --cores      "${CORES}" \
        --memory     "${MEMORY}" \
        --swap       "${SWAP}" \
        --rootfs     "${STORAGE}:${DISK}" \
        --net0       "${NETCFG}" \
        --nameserver "${DNS_SERVER}" \
        --searchdomain "${DOMAIN}" \
        --features   nesting=1 \
        --unprivileged 0 \
        --onboot     1 \
        "${PUBKEY_ARGS[@]}"

    log "Container ${CTID} created."
fi

# ── Start container ───────────────────────────────────────────────────────────

CT_STATUS="$(pct status "${CTID}" | awk '{print $2}')"
if [[ "${CT_STATUS}" != "running" ]]; then
    log "Starting container ${CTID}..."
    pct start "${CTID}"
    sleep 6
fi

# ── Wait for network connectivity ─────────────────────────────────────────────

log "Waiting for container network (up to 60 s)..."
for i in $(seq 1 30); do
    if pct exec "${CTID}" -- ping -c1 -W2 1.1.1.1 &>/dev/null 2>&1; then
        log "Network OK."
        break
    fi
    sleep 2
    if [[ "${i}" -eq 30 ]]; then
        die "Container did not reach the internet after 60 s. Check bridge/NAT config."
    fi
done

# ── Install Docker CE ─────────────────────────────────────────────────────────

log "Installing Docker CE inside container ${CTID}..."
pct exec "${CTID}" -- bash -c '
set -euo pipefail

if command -v docker &>/dev/null; then
    echo "Docker already installed: $(docker --version)"
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -yq ca-certificates curl gnupg lsb-release

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -qq
apt-get install -yq \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

systemctl enable --now docker
echo "Docker installed: $(docker --version)"
echo "Compose plugin : $(docker compose version)"
'
log "Docker CE installed."

# ── Verify Docker Compose plugin ──────────────────────────────────────────────

pct exec "${CTID}" -- docker compose version \
    || die "docker compose plugin not available inside container."

# ── Configure dynamic DNS (ddclient) ─────────────────────────────────────────

if [[ -z "${DDNS_TOKEN}" ]]; then
    log "DDNS_TOKEN not set — skipping dynamic DNS registration."
else
    log "Installing ddclient (${DDNS_PROVIDER}) for ${FQDN}..."

    pct exec "${CTID}" -- bash -c '
export DEBIAN_FRONTEND=noninteractive
apt-get install -yq ddclient
systemctl stop ddclient 2>/dev/null || true
'

    # Build /etc/ddclient.conf for the chosen provider
    case "${DDNS_PROVIDER}" in
        cloudflare)
            DDCLIENT_CONF="# ddclient — Cloudflare — managed by CairnBooks provision.sh
daemon=300
syslog=yes
pid=/var/run/ddclient.pid
ssl=yes
use=web, web=ipinfo.io/ip

protocol=cloudflare
zone=${DDNS_ZONE}
login=token
password=${DDNS_TOKEN}
${FQDN}"
            ;;
        duckdns)
            DDCLIENT_CONF="# ddclient — DuckDNS — managed by CairnBooks provision.sh
daemon=300
syslog=yes
pid=/var/run/ddclient.pid
ssl=yes
use=web, web=ipinfo.io/ip

protocol=duckdns
login=${HOSTNAME}
password=${DDNS_TOKEN}
${HOSTNAME}.duckdns.org"
            ;;
        noip)
            DDCLIENT_CONF="# ddclient — No-IP — managed by CairnBooks provision.sh
daemon=300
syslog=yes
pid=/var/run/ddclient.pid
ssl=yes
use=web, web=ipinfo.io/ip

protocol=noip
server=dynupdate.no-ip.com
login=${HOSTNAME}
password=${DDNS_TOKEN}
${FQDN}"
            ;;
        *)
            die "Unknown DDNS_PROVIDER '${DDNS_PROVIDER}'. Choose: cloudflare | duckdns | noip"
            ;;
    esac

    # Push config into container and start ddclient
    printf '%s\n' "${DDCLIENT_CONF}" \
        | pct exec "${CTID}" -- bash -c 'cat > /etc/ddclient.conf && chmod 600 /etc/ddclient.conf'

    pct exec "${CTID}" -- bash -c '
systemctl enable --now ddclient
# Immediate one-shot update to register IP straight away
ddclient -daemon=0 -debug -verbose -noquiet 2>&1 | tail -20
echo "ddclient service enabled."
'
    log "Dynamic DNS registration complete → ${FQDN}"
fi

# ── UFW firewall ──────────────────────────────────────────────────────────────

log "Configuring UFW firewall..."
pct exec "${CTID}" -- bash -c '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get install -yq ufw
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment "SSH"
ufw allow 80/tcp   comment "HTTP"
ufw allow 443/tcp  comment "HTTPS"
ufw allow 8000/tcp comment "CairnBooks API"
ufw allow 5173/tcp comment "CairnBooks Frontend"
ufw --force enable
ufw status verbose
echo "UFW configured."
'
log "UFW configured."

# ── Miscellaneous hardening ───────────────────────────────────────────────────

log "Applying misc hardening..."
pct exec "${CTID}" -- bash -c '
export DEBIAN_FRONTEND=noninteractive
apt-get install -yq fail2ban unattended-upgrades
systemctl enable --now fail2ban
# Enable automatic security updates
dpkg-reconfigure -f noninteractive unattended-upgrades
echo "Hardening complete."
'

# ── Summary ───────────────────────────────────────────────────────────────────

CONTAINER_IP="$(pct exec "${CTID}" -- hostname -I 2>/dev/null | awk '{print $1}')"

log ""
log "================================================================"
log "  CairnBooks LXC provisioning complete!"
log "================================================================"
log "  Container ID : ${CTID}"
log "  Hostname     : ${FQDN}"
log "  IP address   : ${CONTAINER_IP}"
log ""
log "  Next steps:"
log "    1. SSH into container:"
log "         ssh root@${CONTAINER_IP}"
log "    2. Clone the repository:"
log "         git clone https://github.com/ray-berg/CairnBooks /opt/cairnbooks"
log "    3. Configure secrets:"
log "         cp /opt/cairnbooks/.env.example /opt/cairnbooks/.env && nano /opt/cairnbooks/.env"
log "    4. Start the stack:"
log "         cd /opt/cairnbooks && docker compose up -d"
if [[ -n "${DDNS_TOKEN}" ]]; then
    log ""
    log "  Public hostname: ${FQDN}"
    log "  (DNS propagation may take a few minutes)"
fi
log "================================================================"
