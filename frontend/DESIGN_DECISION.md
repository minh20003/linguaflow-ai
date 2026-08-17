# Design Decision Record: LinguaChat Frontend

Status: accepted · Version: 2.0

```yaml
product: multilingual real-time focused messaging
archetype: focused_dm
shell: adaptive_workspace
navigation: conversation_index
messages: speaker_blocks / consecutive_sender
composer: compact_docked
context: on_demand
density: balanced
geometry: soft
surface: tonal_layers
hierarchy: mixed_restrained
character: calm_social_editorial
```

Decisions:

- Use a two-surface desktop workspace: ledger + reading canvas.
- Keep secondary actions contextual and avoid a permanent right rail.
- Use ChatScope for message anatomy, but own the product tokens and hierarchy.
- Keep auth/chat code under feature folders and primitives/API/session code under
  `shared`.
- Use semantic tokens, restrained borders and tonal surfaces; avoid gradients,
  glassmorphism and generic dashboard cards.
- Treat Vietnamese-first labels, readable metadata and keyboard access as product
  requirements, not polish.

Rejected defaults:

- Slack/Discord/WhatsApp/Telegram/Mattermost visual cloning;
- icon-rail + rounded-sidebar + right-details dashboard shell;
- reaction trays, permanent action chrome and oversized floating composers;
- color-only unread, delivery or error states.

Change rule: update this record when shell topology, message model, density,
composer behavior or navigation changes materially.
