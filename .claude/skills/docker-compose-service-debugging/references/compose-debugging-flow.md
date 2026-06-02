# Compose Debugging Flow

## Start with evidence

Preferred sequence:

```bash
docker compose ps
docker compose logs --tail 200 <service>
docker compose logs --tail 200 <service> | grep -i "error\\|exception\\|failed"
docker compose exec <service> sh
```

Use service names first. Discover generated container names only when you need lower-level
inspection through plain `docker` commands.

## Action selection

### Restart

Use `docker compose restart <service>` when:

- the process is stuck and the container definition is unchanged
- no image, env, command, mount, or service-definition input changed

### Recreate

Use `docker compose up -d --force-recreate <service>` when:

- `environment:` or `env_file:` values changed
- `command`, `entrypoint`, `ports`, `volumes`, `depends_on`, or networks changed
- the container must be re-created to pick up config changes

### Rebuild and recreate

Use `docker compose build --no-cache --pull <service>` followed by `docker compose up -d <service>`
when:

- Dockerfile inputs changed
- dependency files changed
- built assets changed inside the image
- cached layers may be hiding the real state

If the repo documents a stricter canonical rebuild path, follow that instead.
