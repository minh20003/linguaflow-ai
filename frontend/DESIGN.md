# LinguaChat Frontend Design Contract

Version: 2.0 · Owner: Frontend team · Scope: `frontend/src`

This document is binding for UI implementation and review. Product requirements
override it; record any conflict in `DESIGN_DECISION.md`.

## 1. Product intent

LinguaChat is a focused, multilingual real-time messaging application. The UI
must make conversation identity, chronology, authorship, delivery state and
composer actions obvious while remaining calm at high message density.

Primary outcomes:

- read and send messages with minimal visual noise;
- understand unread, failed, offline and reconnecting states;
- attach files, search conversations and create group chats;
- support keyboard, touch and narrow screens;
- preserve a distinctive LinguaChat identity without cloning a reference app.

## 2. Design genome

```yaml
archetype: focused_dm
shell: adaptive_workspace
navigation: conversation_index
conversation_index: metadata_rich
message_model: speaker_blocks
message_grouping: consecutive_sender
metadata: contextual
composer: compact_docked
context: on_demand
density: balanced
geometry: soft
surface: tonal_layers
hierarchy: mixed_restrained
character: calm_social_editorial
accent: unread_and_status
```

Structural decisions come before color. Do not copy the pane count, navigation,
message model, composer and density of one existing product as a set. ChatScope
is used only for message anatomy; Chatscope, Teams, Slack, Discord, WhatsApp,
Telegram and Mattermost are not visual templates.

## 3. UX invariants

The user must always be able to identify:

- active conversation and participants;
- unread/mention state and chronological order;
- sender, timestamp and delivery status;
- edited, deleted, failed and uploading messages;
- search, attachment, send, reply/edit and recovery actions;
- offline/reconnecting state and the path back to the newest messages.

Use progressive disclosure for secondary actions. Do not add a permanent right
panel without a concrete workflow requirement.

## 4. Information architecture

```text
app/                         route composition only
features/auth/components/    login, registration, password recovery, auth guard
features/chat/components/    messaging workspace and chat-specific styles
shared/ui/                   framework-independent visual primitives
shared/lib/                  API client, session, i18n and constants
```

Rules:

- routes import feature entry components; they do not own business logic;
- feature code may import `shared`, never the reverse;
- colocate a component's CSS module with that component;
- keep backend transport types in `shared/lib/api.ts`;
- keep browser session persistence in `shared/lib/auth-session.ts`;
- avoid barrel files until the public surface is stable.

## 5. Visual tokens

Use semantic tokens from `globals.css` and feature CSS modules. Never introduce
one-off hex values or arbitrary spacing when a token exists.

```css
/* spacing: 4, 8, 12, 16, 20, 24, 32px */
/* roles: surface, text, border, accent, status, focus */
```

Token roles:

| Role | Meaning |
| --- | --- |
| `surface-ground` | application background |
| `surface-label` | primary workspace surface |
| `surface-sunken` | input/secondary tonal surface |
| `ink` | primary readable text |
| `ink-secondary` / `ink-muted` | supporting metadata |
| `rule` / `rule-strong` | structural separators |
| `indigo` / `indigo-weak` | action, selected and focus state |
| `koke` | positive/read state |
| `bengara` / `bengara-weak` | warning/error state |

Use borders, spacing and typography before shadows. Use elevation only for a
modal, menu, popover or other actual floating layer. Pills are reserved for
filters and compact status controls. Avoid gradients, glassmorphism, oversized
hero copy and card-wrapped messaging surfaces.

## 6. Component and interaction rules

### Auth

- labels are explicit and inputs use native autocomplete;
- validation explains the correction, not just the rule;
- registration, login, refresh, logout and password reset use the backend API;
- chat is unavailable without a valid restored session;
- icon-only controls have an accessible name.

### Chat

- conversation list is keyboard navigable and shows unread state;
- messages group consecutive senders and show date/time context;
- message actions are contextual, not permanently noisy;
- composer keeps text entry, attachment and send actions visually related;
- file selection uses a native file input and exposes progress, cancel and send;
- group creation is a modal with search, selection, focus and Escape handling.

## 7. State matrix

Every state below must have a visible, testable treatment before being called
complete:

```yaml
app: [loading, ready, reconnecting, offline, fatal_error]
list: [loading, normal, unread, empty, search_no_results]
conversation: [loading_history, normal, empty, loading_older, new_messages]
message: [sending, delivered, read, failed, edited, deleted, selected, hovered]
composer: [empty, typing, multiline, replying, editing, attaching, uploading, disabled, offline]
auth: [idle, submitting, invalid, server_error, restored, expired]
```

## 8. Responsive contract

- wide desktop: conversation index and active conversation are both available;
- laptop: prioritize index, active conversation and composer;
- narrow screens: use a list → conversation navigation stack;
- touch targets should be at least 44px where practical;
- long names, URLs, CJK text, Vietnamese diacritics and multiline content must
  wrap or truncate without shifting the primary layout.

## 9. Accessibility contract

Target WCAG 2.2 AA. Provide visible `:focus-visible` styles, semantic controls,
labels, status announcements, keyboard-complete primary flows, modal focus
behavior, non-color status cues and reduced-motion support. Prefer native HTML
semantics before ARIA.

## 10. Review gates

Before merging a UI change:

1. Read this contract and update `DESIGN_DECISION.md` if the genome changes.
2. Verify desktop, narrow/mobile, long content, empty, error and offline states.
3. Run keyboard checks for auth, search, conversation selection, composer,
   attachment and modal flows.
4. Run `npm run build` and relevant tests.
5. Complete the anti-convergence review: no generic AI dashboard shell,
   gratuitous cards, gradients, shadows or pills; structure is justified by the
   messaging workflow.

## Definition of done

The implementation is done when the selected genome is visible in the UI, all
invariants and required states are implemented, routes use the feature/shared
structure, keyboard and responsive behavior work, and build/test checks pass.
