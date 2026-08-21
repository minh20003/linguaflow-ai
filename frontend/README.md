# LinguaChat Frontend

Next.js App Router frontend for authentication and real-time multilingual chat.

## Commands

```bash
npm install
npm run dev
npm run lint
npx tsc --noEmit --incremental false
npm run build
```

The development app is available at `http://localhost:3000`; the chat route is
`/chat`.

## Source layout

```text
src/
  app/                 Route definitions and layouts
  config/              Public runtime configuration
  features/auth/       Authentication UI, API client and session helpers
  features/chat/       Chat UI, REST/WebSocket clients and styles
```

Keep route files thin. Feature-specific code belongs under its feature.

## Docker

The production image is a Next.js standalone server. Build and run it with:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 docker compose up --build
```

`NEXT_PUBLIC_API_URL` must point to the API address available from the visitor's
browser, not a Docker-only service hostname.
