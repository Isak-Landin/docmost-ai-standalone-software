## Commands (Container general, External)
```bash
docker image rm {docmost_ai_git-backend:latest,docmost_ai_git-docmost-fetcher:latest,docmost_ai_git-ui:latest}
```

### Docker down, remove images, pull git, rebuild, start containers
```bash
docker compose down && \
docker image rm {docmost_ai_git-backend:latest,docmost_ai_git-docmost-fetcher:latest,docmost_ai_git-ui:latest} && \
git pull origin && \
docker compose build --no-cache && \
docker compose up -d
```