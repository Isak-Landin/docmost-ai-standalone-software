# Forgejo Server — Self-Hosted GitHub Alternative

Dedicated host serving `git.isaklandin.com` directly, with NPM removed from this
subdomain's path. An nginx container fronts the stack and owns host port 22 for git-SSH;
Forgejo uses its **built-in** SSH server (not the host sshd). To free port 22 for that
front, the host's own **admin** SSH is relocated to port **2222**.

> Status: the dedicated server is described in the project notes under *"Known intent"* —
> the target architecture — while `git.isaklandin.com` currently still transits the NPM
> edge. Connection values below reflect the intended dedicated endpoint.

## Connection (admin SSH to the host)

| Field | Value |
|---|---|
| Role | Forgejo dedicated host (git.isaklandin.com) |
| IP | `78.109.17.18` |
| SSH user | `isakadmin` |
| SSH key | `~/.ssh/id_ed25519` (local machine) |
| Admin SSH port | **2222** (relocated off 22; from `forgejo-server.ssh.socket`) |

```bash
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -p 2222 isakadmin@78.109.17.18
```

The `forgejo-server.ssh.socket` unit binds admin sshd to `0.0.0.0:2222` (and `[::]:2222`).
Connecting to port 22 of this host reaches the **nginx git-SSH front / Forgejo built-in
SSH**, not an admin shell.

## Stack shape (for inspection)

- Containers: `forgejo` (Forgejo, web on internal `:3000`, built-in SSH), a Postgres
  database, and an `nginx` proxy container as the front.
- nginx front config requires `merge_slashes off` — Forgejo needs URL-encoded slashes
  preserved.
- TLS for `git.isaklandin.com` is to be terminated locally on this host (Let's Encrypt),
  since the subdomain no longer passes through NPM.
- The front is intended to serve only `git.isaklandin.com` and reject all other hosts
  (a `return 444` catch-all), currently disabled until local TLS is in place.

## Inspection notes

- Reach the **admin shell** on port 2222; reach **git-SSH** (clone/push) on port 22.
- Don't assume container names — discover with `docker ps`, then
  `docker logs <name>` / `docker logs -f <name>`.
- Public git-SSH clone URLs are intended to be portless:
  `ssh://git@git.isaklandin.com/...` (the front owning host port 22 is what makes this
  work without a custom port).

## Pending / not-yet-determined

- Whether to preserve real client IPs through the SSH stream (requires matching settings
  on both nginx and Forgejo) or accept the proxy's address in logs.
