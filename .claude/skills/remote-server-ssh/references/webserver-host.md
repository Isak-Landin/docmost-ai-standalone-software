# Webserver — Container Runtime Host

The workload host. Runs the Docker container stack: application services plus a host-side
nginx container that does virtual-host routing. Not directly internet-facing for
application traffic — it sits behind the TLS edge (Nginx Proxy Manager).

## Connection

| Field | Value |
|---|---|
| Role | Container runtime host (Docker stack + host nginx) |
| IP | `64.112.126.69` |
| SSH user | `isakadmin` |
| SSH key | `~/.ssh/id_ed25519` (local machine) |
| Admin SSH port | 22 (default) |

```bash
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes isakadmin@64.112.126.69
```

## Place in the topology

```
TLS edge / NPM (206.168.214.170) --HTTP--> this host's nginx --> upstream app containers
```

This host's nginx unwraps the edge's forwarded client IP
(`set_real_ip_from 206.168.214.170`), so application logs show the real client IP rather
than the edge's address.

## Runtime inspection notes

- **Do not assume container or compose-project names.** Discover the live surface after
  connecting:
  ```bash
  docker ps
  docker logs <name>
  docker logs -f <name>
  ```
- A public `502/503` with a quiet application log points upstream at the **edge**, not
  here — inspect the NPM host instead (see its reference).
- This is an observation surface only. Application source changes arrive through the
  app's own delivery path, never by editing files here.
