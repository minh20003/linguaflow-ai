# Production deployment

## Architecture

The Compose stack runs Caddy as the only public service. It terminates HTTPS and
routes `/api/*`, `/health`, `/docs` and `/openapi.json` to FastAPI; all other
paths go to Next.js. PostgreSQL, Redis and the application containers remain on
the private Docker network.

Redis publishes realtime events between Uvicorn workers/replicas. It is a
required production dependency: FastAPI refuses startup if Redis cannot be
pinged and subscribed, and `/health` returns 503 if publishing/subscribing is
not healthy. The subscriber reconnects with bounded exponential backoff after a
runtime interruption. A client that misses an event reconnects and reloads the
durable REST conversation history.
Attachments use S3-compatible storage in production; supported providers are
AWS S3, Cloudflare R2 and MinIO.

Translation lifecycle metrics are collected in-process without high-cardinality
`message_id` or `user_id` labels. They cover throughput, duration/first-token
latency, fallback/failure/stale outcomes, language-detection LLM use, and outbox
queue/active/retry state. The current deployment exposes them to an application
export adapter through `TranslationMetrics.snapshot()`; adding a Prometheus or
OTel exporter is a deployment integration, not a dependency requirement here.

`OutboxDispatcher` runs inside the FastAPI lifespan. Each application replica may
poll the same PostgreSQL outbox: row claiming uses `FOR UPDATE SKIP LOCKED`, a
lease, attempt fencing, and idempotent translation claims. `APP_ENV=production`
rejects any `DATABASE_URL` that is not `postgresql+asyncpg://...`; SQLite remains
a development/test single-process database. Shutdown waits for the bounded
current batch before closing realtime connections.

`REDIS_URL` must be set in production. A Redis publish failure raises to the
outbox dispatcher so the durable event is retried; it is never silently reduced
to process-local delivery. Configure container orchestration to restart a
backend instance whose `/health` returns 503.

Active translation work heartbeats its lease every one third of the configured
lease duration. A healthy slow provider call therefore remains owned; after a
process crash the heartbeat stops, the lease expires, and the next attempt
reclaims the same logical translation with a new fenced job id.

Outbox delivery is at-least-once. A crash after the transport accepts an event
but before the outbox row is marked `processed` causes a retry. Consumers must
deduplicate original messages by `message.id`, translations by
`message_id + message_revision + target_language`, and live chunks by
`translation_job_id + sequence`.

CI provisions PostgreSQL 16 and runs `tests/test_postgres_outbox_locking.py`
against it. The test holds a row lock on one connection and proves a concurrent
`FOR UPDATE SKIP LOCKED` claim returns a different pending row.

## Required deployment inputs

Do **not** commit a populated `.env`. Supply these through your hosting
provider's secret manager or a Docker/Kubernetes secret volume:

- `POSTGRES_PASSWORD`
- `JWT_SECRET` (generate a new 32+ byte random value)
- the selected LLM provider key (`GROQ_API_KEY`, `OPENAI_API_KEY`, etc.)
- `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`
- `REDIS_URL`
- optional observability keys (`LANGFUSE_*`, `LANGCHAIN_API_KEY`, `AI_LOG_API_KEY`)

`Settings` reads standard environment variables and, when present, files under
`/run/secrets` named after the lower-case setting (for example
`/run/secrets/jwt_secret`). This works with Docker secrets and Kubernetes secret
volumes. Cloud services should inject the same names from their own secret
manager rather than creating `.env` on the host.

## Deploy

1. Point the `DOMAIN` DNS A/AAAA record to the VPS/load balancer and open ports
   80 and 443. Caddy obtains and renews TLS certificates automatically.
2. Inject required secrets using the platform secret manager.
3. Build and start the stack:

   ```bash
   docker compose up --build -d
   ```

4. Verify external health:

   ```bash
   curl --fail https://chat.example.com/health
   ```

## Before public launch

- Rotate previously exposed AI-log keys and any key ever committed to history.
- Use managed PostgreSQL backup and S3/R2 lifecycle policies.
- Persist Caddy volumes so TLS certificates survive container recreation.
- For multiple hosts, use managed PostgreSQL and Redis instead of Compose
  volumes.
