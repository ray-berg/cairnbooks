# AGENTS.md

## This repository has moved to Forgejo

The canonical home of this repository is now **Forgejo**, in the `atrium`
organization. It was migrated from `github.com/ray-berg/cairnbooks` on 2026-06-13.

- **Source of truth (clone & push here):** https://forge.nocos.dev/atrium/cairnbooks
- **GitHub (read-only mirror):** https://github.com/ray-berg/cairnbooks

> Forgejo is authoritative. GitHub is a one-way mirror that Forgejo
> force-pushes on every change. **Do not push to GitHub** - any commits you
> make there are overwritten on the next sync. Always clone from and push to
> Forgejo.

## How to access (HTTPS + token - works today)

```
git clone https://forge.nocos.dev/atrium/cairnbooks.git
```

Authenticate with a Forgejo personal access token:

1. Create one at https://forge.nocos.dev/user/settings/applications
   (scope `write:repository`, or `read:repository` for read-only access).
2. Use it as the HTTP password when prompted, or embed it in the URL:
   `https://<user>:<token>@forge.nocos.dev/atrium/cairnbooks.git`

Never commit the token or write its value into any file.

### Repoint an existing GitHub clone

```
git remote set-url origin https://forge.nocos.dev/atrium/cairnbooks.git
```

## SSH (preferred once enabled - not reachable yet)

Forgejo advertises SSH at `ssh://git@forge.nocos.dev:2222/atrium/cairnbooks.git`,
but as of 2026-06-13 port 2222 is not reachable through the Cloudflare-proxied
hostname and your key may not be registered. Once SSH is enabled (open port
2222 / Cloudflare Spectrum or a DNS-only host, and register your public key at
https://forge.nocos.dev/user/settings/keys), prefer:

```
git clone ssh://git@forge.nocos.dev:2222/atrium/cairnbooks.git
```
