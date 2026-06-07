# CairnBooks — Backup & Restore Runbook

This document covers the nightly backup strategy, manual backup procedures,
and step-by-step restore instructions for the CairnBooks staging deployment.

---

## Architecture Overview

```
LXC container (staging)
│
├── infra/backups/backup.sh           ← backup script
├── infra/backups/restore.sh          ← restore script
├── infra/backups/backup.env          ← secrets (not committed)
│
├── /var/backups/cairnbooks/          ← local compressed dumps (7-day rolling)
│    └── cairnbooks_YYYYMMDD_HHMMSS.sql.gz
│
└── docker-compose stack
     ├── postgres:16  ← pg_dump source
     └── minio        ← local S3-compatible backup bucket
          └── cairnbooks-backups/    ← backups mirrored here

Off-LXC (optional)
└── Remote MinIO / S3 endpoint        ← off-host copy for DR
     └── cairnbooks-backups/
```

**Backup flow**

1. `pg_dump` runs inside the postgres container and pipes through `gzip` to a
   timestamped file in `/var/backups/cairnbooks/`.
2. The file is uploaded to the local MinIO service (`cairnbooks-backups` bucket).
3. If `REMOTE_ENDPOINT` is configured, the file is also copied to the off-LXC
   S3/MinIO endpoint.
4. Files older than `RETAIN_DAYS` (default 7) are pruned from the local directory.
   MinIO does **not** auto-prune — apply a lifecycle policy if needed (see below).

---

## Prerequisites

### MinIO client (`mc`)

The `mc` binary must be present on the LXC host.

```bash
# Install mc
curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc \
  -o /usr/local/bin/mc
chmod +x /usr/local/bin/mc

# Verify
mc --version
```

---

## Initial Setup

### 1. Place scripts in the deployment directory

After cloning the repository on the LXC container:

```bash
cd /opt/cairnbooks
# The scripts are already in infra/backups/
chmod +x infra/backups/backup.sh
chmod +x infra/backups/restore.sh
```

### 2. Create `backup.env`

```bash
cp /opt/cairnbooks/infra/backups/backup.env.example \
   /opt/cairnbooks/infra/backups/backup.env
chmod 600 /opt/cairnbooks/infra/backups/backup.env
# Edit and fill in PG_PASSWORD, remote credentials, etc.
$EDITOR /opt/cairnbooks/infra/backups/backup.env
```

> **Security**: `backup.env` contains database credentials.  
> Ensure it is readable only by root (`chmod 600`) and never committed to git.

### 3. Install and enable the systemd timer

```bash
# Copy unit files
cp /opt/cairnbooks/infra/backups/cairnbooks-backup.service \
   /etc/systemd/system/cairnbooks-backup.service
cp /opt/cairnbooks/infra/backups/cairnbooks-backup.timer \
   /etc/systemd/system/cairnbooks-backup.timer

# Reload and enable
systemctl daemon-reload
systemctl enable --now cairnbooks-backup.timer

# Confirm timer is active
systemctl list-timers cairnbooks-backup.timer
```

Expected output shows the timer scheduled for the next 02:00 run.

### 4. Run a manual test backup

```bash
bash /opt/cairnbooks/infra/backups/backup.sh
```

Check the output and confirm:
- A `.sql.gz` file appears in `/var/backups/cairnbooks/`
- The file is visible in MinIO:  
  `mc ls cairnbooks-local/cairnbooks-backups/`

---

## Verifying Scheduled Backups

```bash
# Check timer status and last run time
systemctl status cairnbooks-backup.timer
systemctl status cairnbooks-backup.service

# View recent backup logs
journalctl -u cairnbooks-backup.service -n 50 --no-pager

# List local backup files
ls -lh /var/backups/cairnbooks/

# List backups in local MinIO
mc ls cairnbooks-local/cairnbooks-backups/
```

---

## Remote (Off-LXC) Storage

To send backups to a second MinIO instance or any S3-compatible service
(AWS S3, Wasabi, Backblaze B2, etc.), set these variables in `backup.env`:

```bash
REMOTE_ENDPOINT=https://s3.example.com   # or https://s3.amazonaws.com
REMOTE_ACCESS_KEY=AKIAXXXXXXXXXXXXXXXX
REMOTE_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
REMOTE_BUCKET=cairnbooks-backups-dr
```

The backup script will copy each dump to the remote bucket immediately
after the local MinIO upload.

### MinIO Lifecycle Policy (optional — auto-prune remote bucket)

```bash
# Keep objects for 30 days in the remote bucket
mc ilm rule add \
  --expiry-days 30 \
  cairnbooks-remote/cairnbooks-backups
```

---

## Restore Runbook

> **Read the entire section before starting a restore.**  
> The restore process will **drop and recreate** the database.
> Make sure you have identified the correct backup file first.

### Step 1 — Identify the backup to restore

```bash
# List local files
ls -lht /var/backups/cairnbooks/

# List local MinIO
mc ls cairnbooks-local/cairnbooks-backups/ | sort

# List remote MinIO (if configured)
bash /opt/cairnbooks/infra/backups/restore.sh --list-remote
```

### Step 2 — Stop write traffic (recommended)

Stop or scale down anything that writes to the database:

```bash
cd /opt/cairnbooks
docker compose stop backend
```

### Step 3 — Restore

**Option A — Restore from local file**

```bash
bash /opt/cairnbooks/infra/backups/restore.sh \
  /var/backups/cairnbooks/cairnbooks_20240101_020000.sql.gz
```

**Option B — Restore the latest backup from local MinIO**

```bash
bash /opt/cairnbooks/infra/backups/restore.sh --latest
```

**Option C — Restore a named backup from local MinIO**

```bash
# First list available backups
bash /opt/cairnbooks/infra/backups/restore.sh --list

# Then restore by filename
bash /opt/cairnbooks/infra/backups/restore.sh \
  --from-minio cairnbooks_20240101_020000.sql.gz
```

**Option D — Restore from the remote (off-LXC) endpoint**

```bash
bash /opt/cairnbooks/infra/backups/restore.sh --list-remote
bash /opt/cairnbooks/infra/backups/restore.sh \
  --from-remote cairnbooks_20240101_020000.sql.gz
```

The restore script will:
1. Prompt for confirmation (type `yes`).
2. Stop the backend container (if running).
3. Drop and recreate the `cairnbooks` database.
4. Stream the decompressed dump through `psql`.
5. Restart the backend container.

### Step 4 — Verify the restore

```bash
# Check backend is healthy
docker compose ps
curl -s http://localhost:8000/health

# Spot-check row counts
docker exec -e PGPASSWORD=cairnbooks \
  "$(docker ps --filter name=postgres --format '{{.Names}}')" \
  psql -U cairnbooks -d cairnbooks \
  -c "\dt; SELECT COUNT(*) FROM accounts;"
```

### Non-interactive restore (CI/scripts)

Set `CAIRNBOOKS_RESTORE_CONFIRM=yes` to skip the interactive prompt:

```bash
CAIRNBOOKS_RESTORE_CONFIRM=yes \
  bash /opt/cairnbooks/infra/backups/restore.sh --latest
```

---

## Tested Restore Procedure

The following sequence was used to validate the restore path during initial
deployment:

```bash
# 1. Take a manual backup
bash /opt/cairnbooks/infra/backups/backup.sh

# 2. Verify backup file exists
LATEST=$(ls -t /var/backups/cairnbooks/*.sql.gz | head -1)
echo "Backup: $LATEST ($(du -sh "$LATEST" | cut -f1))"

# 3. Seed a canary row so we can confirm restore worked
docker exec -e PGPASSWORD=cairnbooks \
  "$(docker ps --filter name=postgres --format '{{.Names}}')" \
  psql -U cairnbooks -d cairnbooks \
  -c "CREATE TABLE IF NOT EXISTS restore_test (id serial, ts timestamptz DEFAULT now()); INSERT INTO restore_test DEFAULT VALUES;"

# 4. Restore from the backup (this will drop the canary row)
CAIRNBOOKS_RESTORE_CONFIRM=yes \
  bash /opt/cairnbooks/infra/backups/restore.sh "$LATEST"

# 5. Confirm restore_test table is gone (was created after backup)
docker exec -e PGPASSWORD=cairnbooks \
  "$(docker ps --filter name=postgres --format '{{.Names}}')" \
  psql -U cairnbooks -d cairnbooks \
  -c "\dt restore_test"
# Expected: "Did not find any relation named restore_test."
```

---

## Cron Alternative (without systemd)

If systemd timers are not available, add a crontab entry instead:

```bash
# Edit root crontab
crontab -e
```

Add:

```cron
# CairnBooks nightly backup — 02:00 local time
0 2 * * * /bin/bash /opt/cairnbooks/infra/backups/backup.sh >> /var/log/cairnbooks-backup.log 2>&1
```

Check last run:

```bash
tail -50 /var/log/cairnbooks-backup.log
```

---

## Troubleshooting

### `pg_dump` fails: "could not connect"

The postgres container may not be running:

```bash
docker compose -f /opt/cairnbooks/docker-compose.yml ps postgres
docker compose -f /opt/cairnbooks/docker-compose.yml start postgres
```

### `mc: command not found`

Install the MinIO client:

```bash
curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc \
  -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc
```

### MinIO upload fails: "Access Denied"

Check that the credentials in `backup.env` match those in `docker-compose.yml`
(`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`).

### Remote sync fails but local backup succeeded

By default `REMOTE_FAIL_FATAL=false`, so the script exits 0 and the local backup
is preserved. Check the logs:

```bash
journalctl -u cairnbooks-backup.service -n 100
```

Set `REMOTE_FAIL_FATAL=true` if you require remote sync to succeed for the backup
job to be considered healthy.

### Timer not running

```bash
systemctl list-timers --all | grep cairnbooks
systemctl status cairnbooks-backup.timer
# If "inactive (dead)":
systemctl enable --now cairnbooks-backup.timer
```

---

## File Reference

| File | Purpose |
|------|---------|
| `infra/backups/backup.sh` | Main backup script (pg_dump → gzip → MinIO → remote) |
| `infra/backups/restore.sh` | Restore script (local file, MinIO, or remote) |
| `infra/backups/backup.env.example` | Configuration template |
| `infra/backups/backup.env` | Live configuration (not committed — copy from example) |
| `infra/backups/cairnbooks-backup.service` | systemd service unit |
| `infra/backups/cairnbooks-backup.timer` | systemd timer unit (nightly 02:00) |
| `docs/deployment/backups.md` | This document |
