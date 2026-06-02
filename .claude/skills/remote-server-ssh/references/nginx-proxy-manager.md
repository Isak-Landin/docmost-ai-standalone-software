# Nginx Proxy Manager — TLS / Public-Entry / Proxy Upstream

The only internet-facing point for proxied applications. It sits **in front of any
webserver application**: terminates public HTTPS, holds the TLS certificates, and proxies
decrypted HTTP inward to a webserver host's nginx. Built on OpenResty (an `openresty`
`Server:` header is the edge answering, not the workload).

## Connection

| Field | Value |
|---|---|
| Role | Nginx Proxy Manager (TLS edge, public entry, proxy upstream) |
| IP | `206.168.214.170` |
| SSH user | `isakadmin` |
| SSH key | `~/.ssh/id_ed25519` (local machine) |
| Admin SSH port | 22 (default) |

```bash
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes isakadmin@206.168.214.170
```

## Place in the topology

```
Internet --HTTPS 443--> this host (TLS termination) --HTTP--> webserver host nginx (64.112.126.69)
```

This edge sets `X-Forwarded-For` with the real client IP before forwarding inward.

**Exception — `git.isaklandin.com`:** being moved off this edge onto the dedicated Forgejo
server. git-SSH carries no hostname/SNI, so an L4 proxy can route it only by destination
IP and port, never by domain — a shared proxy cannot multiplex git-SSH by domain, which is
why Forgejo needs a dedicated endpoint.

## Inspection notes

- NPM's custom nginx snippets live under `/data/nginx/custom/` on this host (e.g.
  `http_top.conf`, `server_proxy.conf`) — inspect there for proxy / method-gate behavior.
- A public `502/503` with a quiet application log, or a `Server: openresty` response,
  points at **this edge** rather than the workload.
- A `405` on `/` at the NPM admin app (port `81`) is the admin UI, not the forwarding
  proxy gate — don't confuse the two.
