# Local infrastructure

Start PostgreSQL and Redis from the repository root:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Configure credentials through the root `.env` file. Do not commit secrets.
