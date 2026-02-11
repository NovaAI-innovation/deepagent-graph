# Docker Operations

## Local Full Stack
Run API + Redis + Qdrant + Postgres:

```bash
docker compose up --build -d
```

Health check:

```bash
curl http://localhost:8000/health
```

Run a playbook:

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d "{\"playbook\":\"build\",\"runtime\":\"langgraph\",\"request\":{}}"
```

The app uses `team/config/system_profile.docker.yaml` in Docker and persists run state to `team/state_broker/`.

## Deploy Stack
Use the deploy compose file with a prebuilt image:

```bash
docker build -t deepagent-graph:latest .
DEEPAGENT_IMAGE=deepagent-graph:latest docker compose -f docker-compose.deploy.yml up -d
```

Environment overrides:
- `APP_PORT`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DEEPAGENT_IMAGE`

## Memory Backend
Docker profile enables Mem0 with local Qdrant (`host: qdrant`, `port: 6333`).
If needed, edit `team/config/system_profile.docker.yaml` to change memory settings.
