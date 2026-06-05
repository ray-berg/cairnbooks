# CairnBooks Staging — LXC Provisioning

> Last updated: 2026-06-05  
> Branch: `ops/staging-lxc`  
> Status: **⚠ Pending manager approval — see §3a**

> ### Action required before merge
> The NOCOS VMID 300 clone is **gated** (outside agent auto-approve range).
> A manager must approve it at **https://dashboard.nocos.ai/dashboard**
> (approval ID: `bd9404f0-7f5e-4c5f-8c26-872bcd83e95b`, correlation `mcp-d650df028c25`).
> Once approved, run `docker_install(host="cairnbooks-staging")` to complete the setup
> and flip the status line above to ✅.

---

## 1. Host Summary

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| Container name     | `cairnbooks-staging`                         |
| Proxmox VMID       | 300                                          |
| Proxmox node       | `quito`                                      |
| Resource pool      | `sysadmin-lab`                               |
| Template cloned    | CT 120 — `ub2404-tmplt` (Ubuntu 24.04 LTS)   |
| vCPU               | 2                                            |
| RAM                | 2 048 MB                                     |
| Storage            | `nas1-vm-ssd` (NFS, shared)                  |
| Container runtime  | Docker Engine + Docker Compose               |

---

## 2. Stable Hostname & Dynamic DNS

### 2a. Internal hostname

The container's static internal hostname is `cairnbooks-staging`. It resolves on the Proxmox/LAN network and is the authoritative name for service-to-service calls inside the cluster.

### 2b. Public / dynamic DNS

| Record type | Name                              | Target               | TTL  | Provider   |
|-------------|-----------------------------------|----------------------|------|------------|
| A           | `staging.cairnbooks.tiftontech.com` | `<container LAN IP>` | 60 s | Cloudflare |

> **Note:** the container IP is assigned via the Proxmox DHCP bridge on `quito`. Because this is a private IP exposed through a Cloudflare Tunnel (or via NAT), the TTL can be set as low as 60 s without affecting reliability.

#### Keeping the record fresh

The container runs `cloudflare-ddns` (or equivalent) as a systemd timer that re-publishes its IP to Cloudflare every 5 minutes. Configure it with:

```bash
# /etc/cloudflare-ddns.conf  (inside the container)
CF_API_TOKEN=<token with Zone.DNS:Edit>
ZONE=tiftontech.com
RECORD=staging.cairnbooks.tiftontech.com
```

Start the timer:

```bash
systemctl enable --now cloudflare-ddns.timer
```

Alternatively, a Cloudflare Tunnel (`cloudflared`) can replace the DDNS approach for zero-port-forwarding access — see §5 below.

---

## 3. Provisioning Steps (reproducible)

These steps are idempotent and can be re-run after a template refresh.

### 3a. Clone the template

```bash
# Via NOCOS MCP tool (sysadmin-lab profile):
proxmox_clone_container(
  node       = "quito",
  new_vmid   = 300,
  hostname   = "cairnbooks-staging",
  template_vmid = 120,          # ub2404-tmplt
  cores      = 2,
  memory_mb  = 2048,
  pool       = "sysadmin-lab",
  start      = true,
  description = "CairnBooks staging — Docker host"
)
```

> The clone call is gated (NOCOS VMID 300 is outside the agent's auto-approve range).  
> Approval token reference: `bd9404f0-7f5e-4c5f-8c26-872bcd83e95b` (correlation `mcp-d650df028c25`).  
> Approve at: https://dashboard.nocos.ai/dashboard

### 3b. Install Docker

Once the container has booted and obtained an IP, install Docker Engine + Compose:

```bash
# Via NOCOS MCP tool (sysadmin-lab profile):
docker_install(
  host             = "cairnbooks-staging",
  install_compose  = true,
  configure_nvidia = false
)
```

Or manually inside the container:

```bash
curl -fsSL https://get.docker.com | bash
apt-get install -y docker-compose-plugin
systemctl enable --now docker
docker --version          # should print Docker 27+
docker compose version    # should print v2.x
```

### 3c. Verify

```bash
docker run --rm hello-world
docker compose version
```

---

## 4. Service Deployment

The staging environment runs the CairnBooks Docker Compose stack:

```bash
git clone git@github.com:ray-berg/CairnBooks.git /srv/cairnbooks
cd /srv/cairnbooks
cp deploy/.env.example deploy/.env
# Edit deploy/.env — set POSTGRES_PASSWORD, SECRET_KEY, etc.
docker compose -f deploy/docker-compose.yml up -d
```

Exposed ports:

| Service  | Container port | Host port |
|----------|---------------|-----------|
| backend  | 8000          | 8000      |
| frontend | 3000          | 3000      |
| db       | 5432          | (internal)|

---

## 5. Optional: Cloudflare Tunnel (no port-forwarding)

If direct IP exposure is not desired, use a Cloudflare Tunnel instead of DDNS:

```bash
# Inside the container:
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/cloudflared any main" \
  > /etc/apt/sources.list.d/cloudflared.list
apt-get update && apt-get install -y cloudflared
cloudflared tunnel login
cloudflared tunnel create cairnbooks-staging
cloudflared tunnel route dns cairnbooks-staging staging.cairnbooks.tiftontech.com
systemctl enable --now cloudflared
```

With a tunnel, no A record or DDNS client is needed — the `staging.cairnbooks.tiftontech.com` CNAME is managed entirely by `cloudflared`.

---

## 6. Cluster Context

| Node        | Status | RAM used / total   | Uptime     |
|-------------|--------|--------------------|------------|
| quito       | online | 12.4 GB / 27.3 GB  | 81 d 5 h   |
| anchorage   | online | — (standby)        | —          |
| oslo        | online | — (standby)        | —          |
| reykjavik   | online | — (standby)        | —          |

Storage on `quito`: `nas1-vm-ssd` — 654 GB used / 743 GB total (89 GB free). The staging LXC root disk is 8 GB (inherited from template).

---

## 7. References

- Proxmox cluster: https://quito:8006
- NOCOS dashboard: https://dashboard.nocos.ai/dashboard
- Docker install script: https://get.docker.com
- Cloudflare Tunnel docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- CairnBooks Docker Compose: [`deploy/docker-compose.yml`](../../deploy/docker-compose.yml) *(m0-docker-compose-skeleton branch)*
