---
name: remote-server-ssh
description: >
  Connect to the known remote servers over SSH to inspect runtime state, read logs, and
  run one-off commands. Use when a task needs shell access to a remote host — checking a
  running container, tailing logs, or inspecting the proxy/TLS edge. General-fleet servers
  are catalogued by role with real connection values; project-scoped servers (e.g. the
  Forgejo host) are listed separately and only apply to their named project. Deeper
  per-server detail lives in references/. Repo-neutral: this skill is about reaching the
  hosts, not about any one application or project.
---

# Remote Server SSH Access

Use this skill when you need a shell on a remote host to **observe** runtime state —
running containers, logs, process/port checks, one-off inspection commands.

The remote hosts are for observation and operational inspection. They are **not** an
authoring location: do not edit source files or rsync code onto them. Where a host runs
an application, that application's source arrives through its own delivery path, not
through this skill.

## Key storage (local machine)

- The SSH private key for every target below lives on the **local machine** at
  `~/.ssh/id_ed25519` (confirmed present).
- All `ssh`/`scp` invocations reference that key explicitly with `-i ~/.ssh/id_ed25519`
  and `-o IdentitiesOnly=yes`, so the agent does not offer other loaded keys instead.

## Server types (each described shortly)

Two general-fleet roles exist today. Each has a full entry under `references/`.

### 1. Webserver — container runtime host
Runs the Docker container stack (application services + a host-side nginx container).
The workload host. Not directly internet-facing; sits behind the TLS edge.
- `ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes isakadmin@64.112.126.69`
- Detail: [references/webserver-host.md](references/webserver-host.md)

### 2. Nginx Proxy Manager — TLS / public-entry / proxy upstream
The internet-facing edge that sits **in front of any webserver application**. Terminates
public HTTPS, holds the TLS certificates, and proxies decrypted HTTP inward to a
webserver host's nginx. Exception: `git.isaklandin.com` is being moved off this edge onto
the dedicated Forgejo server, because git-SSH cannot be routed by domain through a shared
proxy.
- `ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes isakadmin@206.168.214.170`
- Detail: [references/nginx-proxy-manager.md](references/nginx-proxy-manager.md)

## Project-scoped servers (not general fleet)

These hosts belong to one specific project. They are **not** part of the general fleet
above — never reach them, or treat them as available, unless the current task is part of
the named project.

### Forgejo server — *forgejo project only*
Belongs to the `forgejo` project (`general_docs/forgejo`); out of scope for any other
work. Dedicated host serving `git.isaklandin.com` directly (no NPM in path); an nginx
container fronts it and owns host port 22 for git-SSH, while admin SSH is on **2222**.
- `ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -p 2222 isakadmin@78.109.17.18`
- Detail: [references/forgejo-server.md](references/forgejo-server.md)

## Topology orientation

```
Internet
  -> TLS edge / NPM (206.168.214.170, HTTPS 443)        [TLS termination]
  -> webserver host nginx (64.112.126.69, HTTP)         [virtual-host routing]
  -> upstream application containers

git.isaklandin.com (being moved off NPM)
  -> Forgejo host nginx (host port 22 = git-SSH; HTTP/HTTPS for web)
  -> Forgejo container (built-in SSH, web on :3000)
  admin SSH to the Forgejo host itself: port 2222
```

The TLS edge sets `X-Forwarded-For` with the real client IP before forwarding; the
webserver host's nginx unwraps it (`set_real_ip_from 206.168.214.170`), so the workload
sees the real client IP rather than the edge's address.

## When to use this skill

- Checking a running container or tailing logs on the webserver host.
- Inspecting the proxy/TLS edge for `502/503`, cert, or method-gate behavior.
- Reaching the Forgejo host to inspect the git front, built-in SSH, or local TLS.
- Any one-off remote inspection where the source of truth stays local.

## Adding a server later

This catalogue is meant to grow. To add a new server, follow
[references/adding-a-server.md](references/adding-a-server.md): add a short role blurb plus
a one-line connect command here, and a full grounded entry under `references/`. Never
invent connection values — record only documented ones, and mark anything unconfirmed as
pending.
