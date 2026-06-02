# Config vs Runtime Drift

Compose failures often come from drift between what the repo says should run and what the
live container is actually running.

## Check these layers separately

1. **Compose config** - `docker compose config`
2. **Built image** - image ID, build date, installed dependencies, bundled assets
3. **Running container** - environment, mounts, process command, network attachment
4. **Observed behavior** - logs, HTTP responses, exit codes

## Typical drift patterns

- compose file changed but container was only restarted
- `.env` changed but container was not recreated
- bind mount hides newly built image content
- image was rebuilt from stale cache
- running container uses a different command than expected

## Useful checks

```bash
docker compose config
docker compose ps
docker inspect <container>
docker compose exec <service> env | sort
docker compose exec <service> sh -lc 'pwd && ls'
```

If the runtime still does not match the checked-in config after the correct recreate or
rebuild path, investigate live-environment drift outside Compose as a separate problem.
