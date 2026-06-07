# CairnBooks — Proxmox LXC Deployment

This guide covers provisioning a Proxmox LXC container, installing Docker,
registering a dynamic DNS hostname, and deploying the CairnBooks stack.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Proxmox VE 7.x / 8.x | Script uses `pct`, `pvesm`, `pveam` |
| Root access on the Proxmox host | `sudo` or direct root shell |
| Internet-reachable Proxmox host | Template download + Docker install |
| Dynamic DNS account (optional) | Cloudflare, DuckDNS, or No-IP |

## Quick Start

```bash
# 1. Clone the repository on the Proxmox host (or copy the script there)
git clone https://github.com/ray-berg/CairnBooks /opt/cairnbooks

# 2. Run the provisioning script as root
sudo bash /opt/cairnbooks/infra/proxmox/provision.sh
```

By default the script creates container **200** named **cairnbooks.example.com**
using DHCP.  Override settings with environment variables (see below).

## Configuration Reference

All variables can be set in the environment before running the script.
No file editing is required.

### Container identity

| Variable | Default | Description |
|----------|---------|-------------|
| `CTID` | `200` | Proxmox container ID |
| `HOSTNAME` | `cairnbooks` | Short hostname |
| `DOMAIN` | `example.com` | DNS domain; combined → `HOSTNAME.DOMAIN` |

### Resources

| Variable | Default | Description |
|----------|---------|-------------|
| `CORES` | `2` | vCPU count |
| `MEMORY` | `2048` | RAM in MiB |
| `SWAP` | `512` | Swap in MiB |
| `DISK` | `20` | Root disk in GiB |
| `STORAGE` | `local-lvm` | Proxmox storage pool |
| `BRIDGE` | `vmbr0` | Proxmox network bridge |

### Networking

| Variable | Default | Description |
|----------|---------|-------------|
| `IPADDR` | _(empty)_ | Static IP in CIDR, e.g. `192.168.1.50/24`; leave empty for DHCP |
| `GATEWAY` | _(empty)_ | Default gateway; required when `IPADDR` is set |
| `DNS_SERVER` | `1.1.1.1` | Nameserver injected into the container |

### LXC template

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPLATE_STORAGE` | `local` | Proxmox storage that holds templates |
| `OSTEMPLATE` | `ubuntu-22.04-standard_22.04-1_amd64.tar.zst` | Template filename; must exist in the Proxmox appliance list |

To list available Ubuntu templates:
```bash
pveam available --section system | grep ubuntu
```

### Dynamic DNS

| Variable | Default | Description |
|----------|---------|-------------|
| `DDNS_PROVIDER` | `cloudflare` | `cloudflare` \| `duckdns` \| `noip` |
| `DDNS_ZONE` | `$DOMAIN` | DNS zone (Cloudflare only) |
| `DDNS_TOKEN` | _(empty)_ | API token / password; **leave empty to skip DDNS** |

Set `DDNS_TOKEN` to trigger automatic `ddclient` installation and configuration.

### SSH

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_PUBKEY` | `~/.ssh/id_rsa.pub` | Public key injected into `root`'s `authorized_keys` |

## Example: static IP + Cloudflare DDNS

```bash
CTID=201 \
HOSTNAME=cairnbooks \
DOMAIN=mycompany.com \
IPADDR=192.168.10.20/24 \
GATEWAY=192.168.10.1 \
STORAGE=data \
DDNS_PROVIDER=cloudflare \
DDNS_ZONE=mycompany.com \
DDNS_TOKEN=<cloudflare-api-token> \
sudo -E bash infra/proxmox/provision.sh
```

## Example: DuckDNS DHCP

```bash
HOSTNAME=cairnbooks \
DDNS_PROVIDER=duckdns \
DDNS_TOKEN=<duckdns-token> \
sudo -E bash infra/proxmox/provision.sh
```

With DuckDNS the public hostname will be `cairnbooks.duckdns.org` (the script
handles the `.duckdns.org` suffix automatically).

## What the Script Does

1. **Template check** — downloads the Ubuntu 22.04 LXC template from the
   Proxmox appliance list if not already cached.
2. **Container creation** — `pct create` with nesting enabled (required for
   Docker), sets resources, network, and SSH key.
3. **Container start** — starts the container and waits up to 60 s for
   internet connectivity.
4. **Docker CE** — installs via the official Docker apt repository; enables the
   `docker` and `containerd` systemd services; verifies the Compose plugin.
5. **Dynamic DNS** — installs `ddclient`, writes `/etc/ddclient.conf`, and runs
   a one-shot update to register the current public IP immediately.
6. **UFW firewall** — opens ports 22, 80, 443, 8000, and 5173; all other
   inbound traffic is denied.
7. **Hardening** — installs `fail2ban` and enables `unattended-upgrades`.

The script is **idempotent**: re-running it on an existing container skips the
creation step and only repeats the in-guest configuration steps.

## Verifying Hostname Resolution

After provisioning, verify that the hostname resolves from an external machine:

```bash
# DNS A record lookup
dig +short cairnbooks.example.com

# Or with host
host cairnbooks.example.com

# Confirm round-trip to the API
curl -s http://cairnbooks.example.com:8000/health
```

DNS propagation can take a few minutes depending on the provider and TTL.

To check `ddclient` status inside the container:

```bash
# From the Proxmox host
pct exec 200 -- systemctl status ddclient
pct exec 200 -- ddclient -daemon=0 -verbose -noquiet
```

## Deploying CairnBooks

Once the container is running, SSH in and start the stack:

```bash
# SSH into the container (use the IP shown at end of provision script)
ssh root@<container-ip>

# Clone the repository
git clone https://github.com/ray-berg/CairnBooks /opt/cairnbooks
cd /opt/cairnbooks

# Create a .env file from the example and customise secrets
cp .env.example .env
$EDITOR .env

# Start all services
docker compose up -d

# Check service health
docker compose ps
```

Service endpoints:

| Service | URL |
|---------|-----|
| API (FastAPI + Swagger) | `http://<host>:8000` |
| Frontend (React) | `http://<host>:5173` |
| MinIO console | `http://<host>:9001` |

## Firewall Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (reverse proxy) |
| 443 | TCP | HTTPS (reverse proxy) |
| 8000 | TCP | CairnBooks API |
| 5173 | TCP | CairnBooks Frontend |

## Troubleshooting

### Template download fails

```bash
# Refresh the template list and check available names
pveam update
pveam available --section system | grep ubuntu
# Then set OSTEMPLATE to a name from the list
```

### Container has no internet access

- Verify that the bridge (`vmbr0`) has internet access from other containers.
- Check if NAT/masquerade is configured on the Proxmox host:
  ```bash
  iptables -t nat -L POSTROUTING -n
  ```
- If using a static IP, confirm `GATEWAY` is correct.

### Docker fails to start inside LXC

The container is created with `--features nesting=1` and `--unprivileged 0`
(privileged). If you need an unprivileged container, you must additionally set
`keyctl=1` and ensure your Proxmox kernel supports user namespaces:

```bash
# Proxmox host
pct set <CTID> --features nesting=1,keyctl=1
```

### ddclient not updating

```bash
# Run in foreground debug mode inside the container
ddclient -daemon=0 -debug -verbose -noquiet
# Check /etc/ddclient.conf is correct
cat /etc/ddclient.conf
```

### Checking container status from Proxmox host

```bash
pct status <CTID>
pct exec <CTID> -- docker ps
pct exec <CTID> -- docker compose -f /opt/cairnbooks/docker-compose.yml ps
```
