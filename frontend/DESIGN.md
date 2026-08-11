# DESIGN.md — AI Design Contract for a Real-Time Messaging Web App

> Version: 1.0
> Research date: 2026-08-11
> Purpose: Guide AI coding/design agents to create a production-quality messaging interface **without collapsing into the usual AI-generated UI look**.

---

## 0. How to use this file

This file is a **binding design contract** for any AI agent generating, modifying, or reviewing the frontend.

The agent must:

1. Read this file before writing UI code.
2. Preserve the UX invariants in this document.
3. Select a **Design Genome** before implementation.
4. Make structural decisions before styling decisions.
5. Avoid copying any single reference product.
6. Treat reference repositories as a pattern library, not a template.
7. Verify actual implementation states instead of merely describing good UX.
8. Prefer a coherent design system over decorative novelty.

If a product requirement conflicts with this document, the explicit product requirement wins, but the agent must note the conflict in a short Design Decision Record.

---

# 1. Design objective

Build a real-time messaging product that feels:

- deliberate rather than generated,
- recognizable as this product rather than as a generic AI dashboard,
- efficient for frequent use,
- legible under high message volume,
- coherent across empty, loading, error, offline, unread, reply, editing, and mobile states,
- accessible by keyboard and pointer,
- visually distinct without breaking familiar messaging semantics.

**Do not optimize for “looking modern” as an abstract goal.**

Optimize for:

1. communication clarity,
2. information hierarchy,
3. conversation continuity,
4. speed of repeated actions,
5. state visibility,
6. low visual noise,
7. product-specific character.

---

# 2. Why anti-convergence rules exist

Generative UI systems often produce interfaces with similar visual appearance and layout organization even when colors vary. Therefore, changing palette, gradients, or border radius alone does not create meaningful design diversity.

The design process in this project must vary **structure, density, grouping, hierarchy, navigation and message presentation** before varying decoration.

Never use this strategy:

```text
same layout
+ different color
+ different gradient
= "different design"
```

Use this strategy:

```text
product use case
→ UX invariants
→ layout topology
→ information hierarchy
→ interaction model
→ Design Genome
→ visual tokens
→ components
→ implementation
→ state verification
```

---

# 3. Reference gene pool

The following open-source projects are references for **different UX ideas**. Do not reproduce their screens one-to-one.

## 3.1 Zulip — topic-first communication

Repository:
https://github.com/zulip/zulip

Study for:

- topic-based threading,
- blending live and asynchronous conversation,
- high-information-density communication,
- unread navigation,
- grouping messages by conversational context,
- rigorous visual/state testing.

Do not copy:

- exact sidebar arrangement,
- exact navigation labels,
- exact topic styling,
- exact colors or dimensions.

---

## 3.2 Mattermost — team/channel workspace

Repository:
https://github.com/mattermost/mattermost

Study for:

- channel-oriented collaboration,
- operational/team communication,
- thread/context side panels,
- message actions,
- dense workspace behavior,
- search and unread workflows.

Do not copy the familiar “Slack clone” shell by default.

---

## 3.3 Element Web — room/space communication

Repository:
https://github.com/element-hq/element-web

Design system:
https://github.com/element-hq/compound
https://github.com/element-hq/compound-web

Study for:

- room/space mental models,
- identity and membership states,
- secure messaging states,
- complex conversation context,
- tokenized design systems,
- component-level visual testing.

Do not reproduce Element navigation or visual identity.

---

## 3.4 Chatwoot — inbox / support messaging

Repository:
https://github.com/chatwoot/chatwoot

Study for:

- conversation triage,
- inbox mental model,
- customer/contact context,
- assignment/status actions,
- omnichannel message handling,
- high-value metadata around a conversation.

Useful when the product behaves more like an inbox than a social messenger.

---

## 3.5 Rocket.Chat — communication platform + design system

Repository:
https://github.com/RocketChat/Rocket.Chat

Design system:
https://github.com/RocketChat/fuselage

Study Fuselage for:

- separation of layout, tokens and components,
- reusable communication components,
- form/accessibility wrappers,
- design-token organization.

Do not import the complete visual system unless explicitly required.

---

## 3.6 ChatScope Chat UI Kit — component anatomy

Repository:
https://github.com/chatscope/chat-ui-kit-react

Study for the minimum chat anatomy:

- MainContainer
- ChatContainer
- MessageList
- Message
- MessageInput
- ConversationList
- Avatar / status
- typing states

Use this as an anatomy checklist, **not** as the final visual language.

---

# 4. UX invariants

These semantics should remain familiar even when the visual design changes.

The user must always be able to understand:

- which conversation is active,
- which conversations contain unread activity,
- who sent each message,
- message chronological order,
- reply/thread relationships,
- message sending status,
- failed-send state and recovery action,
- edited/deleted/system-message state,
- presence/availability when the product supports it,
- where to type a message,
- how to send,
- how to attach content,
- how to search,
- how to return to newest messages,
- whether the application is offline or reconnecting.

Creativity must not obscure these semantics.

---

# 5. Design Genome — mandatory before coding

Before generating components, select one value for each dimension.

Do **not** choose values independently at random. Values must fit the product use case.

```yaml
design_genome:
  archetype:
    # focused_dm | team_workspace | topic_stream |
    # support_inbox | community_rooms | command_workspace
    value: null

  shell:
    # single_pane | dual_pane | tri_pane |
    # rail_plus_canvas | adaptive_workspace
    value: null

  primary_navigation:
    # sidebar | icon_rail | topbar | command_palette |
    # conversation_index | contextual
    value: null

  conversation_index:
    # dense_rows | relaxed_rows | grouped_sections |
    # edge_to_edge | metadata_rich
    value: null

  message_presentation:
    # flat_timeline | grouped_bubbles | speaker_blocks |
    # topic_timeline | event_feed
    value: null

  message_grouping:
    # per_message | consecutive_sender |
    # time_cluster | topic_cluster
    value: null

  metadata_visibility:
    # persistent | contextual | hover_enhanced
    value: null

  composer:
    # docked | compact_docked | expandable |
    # command_aware
    value: null

  secondary_context:
    # none | thread | member_info | contact_profile |
    # channel_info | task_context
    value: null

  density:
    # compact | balanced | relaxed
    value: null

  geometry:
    # sharp | soft | rounded
    value: null

  surface_model:
    # flat | border_driven | tonal_layers | restrained_elevation
    value: null

  hierarchy_method:
    # typography | spacing | tonal | border |
    # mixed_restrained
    value: null

  visual_character:
    # neutral_productivity | editorial | technical |
    # calm_social | operational | utilitarian
    value: null

  accent_strategy:
    # actions_only | unread_and_status | navigation |
    # identity | restrained_mixed
    value: null
```

---

# 6. Archetype rules

Choose **one primary archetype**. A secondary influence is allowed, but never combine every pattern.

## A. `focused_dm`

Best for personal/private messaging.

Typical characteristics:

- conversation list + focused conversation,
- minimal secondary metadata,
- generous message-reading area,
- presence and media may be more prominent.

Avoid automatically adding a permanent right sidebar.

---

## B. `team_workspace`

Best for teams/channels/projects.

Typical characteristics:

- efficient navigation,
- compact information density,
- thread/context panel may appear on demand,
- strong unread and mention hierarchy,
- keyboard-friendly repeated workflows.

Do not automatically imitate Slack/Mattermost geometry.

---

## C. `topic_stream`

Inspired by the idea of Zulip-style topical organization.

Typical characteristics:

- topic is a first-class navigation/context object,
- messages can be read live or asynchronously,
- high emphasis on unread/topic continuity,
- subject/context can be more important than decorative bubbles.

---

## D. `support_inbox`

Inspired by customer-support inbox products such as Chatwoot.

Typical characteristics:

- queue/inbox first,
- conversation metadata is operationally important,
- assignment, status and priority may outrank presence,
- contact/context panel can be valuable.

Message UI should not look like a consumer messenger if the work is triage-oriented.

---

## E. `community_rooms`

Best for spaces, rooms, communities or multi-group membership.

Typical characteristics:

- room identity matters,
- membership/context can be prominent,
- navigation may need grouping,
- events and system messages may be common.

---

## F. `command_workspace`

Best for expert users and high-frequency operators.

Typical characteristics:

- compact chrome,
- keyboard shortcuts,
- command palette/search as a primary navigation tool,
- contextual disclosure instead of permanently visible panels.

Do not make important functions undiscoverable for new users.

---

# 7. Structural diversity rules

Meaningful variation must happen in this order:

1. shell topology,
2. navigation model,
3. conversation indexing,
4. message model,
5. context-panel behavior,
6. density,
7. visual hierarchy,
8. geometry,
9. color.

When generating a new concept, changing only items 8–9 is insufficient.

## Required anti-copy rule

A concept may borrow principles from multiple references, but must not reproduce all of these from one product at the same time:

- same pane count,
- same navigation position,
- same message grouping,
- same composer placement,
- same context-panel placement,
- same density,
- same visual geometry.

If too many align with one reference, alter at least two structural dimensions.

---

# 8. Anti-convergence / anti-“AI look” rules

The following patterns are not globally forbidden, but **must never be used as defaults without a product reason**.

## 8.1 Do not wrap every section in a card

Bad default:

```text
sidebar card
conversation card
message card
composer card
profile card
settings card
```

Prefer hierarchy through:

- typography,
- spacing,
- alignment,
- separators,
- tonal regions,
- grouped rows.

Cards are for content that is genuinely a bounded object.

---

## 8.2 Do not use large radii everywhere

Never apply `rounded-xl`, `rounded-2xl`, or pill shapes indiscriminately.

Use a small radius scale tied to the selected geometry.

Example:

```yaml
sharp:
  control: 2px
  surface: 4px
  overlay: 6px

soft:
  control: 4px
  surface: 8px
  overlay: 12px

rounded:
  control: 8px
  surface: 14px
  overlay: 18px
```

Even in `rounded`, not every object must have a filled background.

---

## 8.3 Do not use gradients as identity by default

Avoid default:

- blue-to-purple gradients,
- neon glows,
- rainbow borders,
- glassmorphism panels.

Use gradients only when the brand/art direction explicitly needs them.

---

## 8.4 Do not add shadows to every surface

Prefer:

- border,
- tonal separation,
- spatial separation.

Elevation should communicate an actual layer:

- popover,
- modal,
- floating menu,
- drag layer.

---

## 8.5 Do not create dashboard-style hero areas inside a messaging app

Avoid oversized headings, marketing copy and decorative KPI cards in the core messaging workspace unless the product actually requires them.

---

## 8.6 Do not default to the canonical AI dashboard shell

Do not automatically generate:

```text
64px icon rail
+ 280px rounded sidebar
+ giant white canvas
+ floating rounded composer
+ right details card
```

This topology is allowed only if justified by the selected archetype.

---

## 8.7 Do not use pills for every button/status/tab

Reserve pill geometry for semantics that benefit from compact grouping:

- filters,
- small statuses,
- segmented options,
- tags.

Primary actions do not need to be pills.

---

## 8.8 Do not make color carry all hierarchy

Unread, selected, active, error, mention and disabled states must also differ through at least one of:

- weight,
- icon,
- border,
- shape,
- position,
- label,
- typography.

---

## 8.9 Do not decorate before solving density

For a messaging product, first verify:

- how many conversations fit in viewport,
- how many messages remain readable,
- composer footprint,
- unread visibility,
- long names,
- long messages,
- file messages,
- reply previews.

Only then add decorative treatment.

---

# 9. Visual system

## 9.1 Spacing

Use a consistent base scale.

Recommended starting scale:

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
```

Do not use every value everywhere.

Compact interfaces should rely more on 4/8/12.
Relaxed interfaces may rely more on 8/16/24.

---

## 9.2 Typography

Use typography to create hierarchy before adding boxes.

At minimum define:

```text
body
message
metadata
label
section label
conversation title
workspace title
```

Rules:

- message text is the reading priority,
- timestamps and delivery metadata are subordinate,
- avoid excessive all-caps labels,
- avoid a large heading scale typical of landing pages,
- long names must truncate safely,
- text expansion must not break layout.

---

## 9.3 Color

Define semantic roles rather than ad-hoc hex values:

```text
surface.base
surface.subtle
surface.selected
text.primary
text.secondary
text.muted
border.default
border.strong
accent.primary
status.online
status.warning
status.error
state.unread
state.mention
focus.ring
```

Do not use accent color for every interactive object.

---

# 10. Messaging component anatomy

The design must account for the following components, even if some are not visible on the first screen.

## Navigation

- workspace/account switcher if required
- search / command entry
- conversation/channel/room index
- unread indicators
- mentions
- favorites/pinned
- filters when needed

## Conversation header

Potential elements:

- conversation identity
- status/presence
- topic/channel description
- participants
- search
- call/video actions
- context/thread toggle

Do not display all possible actions at once. Use progressive disclosure.

## Message timeline

Support:

- normal text message
- consecutive sender grouping
- reply preview
- thread indicator
- edited message
- deleted message
- failed message
- sending state
- reactions
- mention
- file
- image
- link preview
- system/event message
- unread divider
- date divider
- typing indicator
- “jump to newest” affordance

## Composer

Must support a clear relationship between:

- text entry,
- send action,
- attachment,
- reply/edit mode,
- disabled/offline state,
- multiline expansion.

Do not make the composer visually heavier than the conversation.

## Context panel

Context is optional.

Possible roles:

- thread,
- member/contact profile,
- channel info,
- shared files,
- task/ticket context.

A context panel should appear because it improves the current workflow, not because a three-column layout looks “professional”.

---

# 11. Message presentation rules

Choose one dominant message model.

## `flat_timeline`

Messages are primarily text in a shared timeline.

Good for:

- teams,
- technical discussion,
- high density.

Use alignment and sender grouping instead of large bubbles.

## `grouped_bubbles`

Bubble grouping emphasizes conversational turns.

Good for:

- private messaging,
- social chat,
- lower-density interaction.

Avoid giving each bubble excessive shadow/radius.

## `speaker_blocks`

A sender identity anchors a group of consecutive messages.

Good for:

- collaboration,
- readable long-form discussion.

Repeated avatar/name metadata should be reduced.

## `topic_timeline`

Topic/context is a visible structural unit.

Good for:

- asynchronous team discussion,
- dense topic navigation.

## `event_feed`

Messages coexist with structured events.

Good for:

- operations,
- support,
- incident workflows.

Reserve card-like treatment for structured objects, not every plain text message.

---

# 12. Responsive behavior

Do not merely shrink desktop columns.

## Wide desktop

Possible:

- multiple panes,
- persistent context,
- high message width control.

## Standard laptop

Prioritize:

1. conversation navigation,
2. active conversation,
3. composer.

Secondary context can become collapsible.

## Tablet / narrow desktop

Use:

- overlay or temporary conversation index,
- contextual thread panel,
- reduced chrome.

## Mobile

Prefer a navigation stack:

```text
conversation list
→ conversation
→ thread/details
```

not three squeezed columns.

Core touch actions should have comfortable hit areas. Follow WCAG 2.2 minimum target-size requirements and use larger targets where touch interaction warrants it.

---

# 13. State matrix — required

A design is incomplete until these states are considered.

```yaml
states:
  app:
    - loading
    - ready
    - reconnecting
    - offline
    - fatal_error

  conversation_list:
    - loading
    - normal
    - unread
    - mention
    - empty
    - search_no_results

  conversation:
    - loading_history
    - normal
    - no_messages
    - loading_older
    - new_messages_below

  message:
    - sending
    - sent
    - delivered
    - read
    - failed
    - edited
    - deleted
    - selected
    - hovered

  composer:
    - empty
    - typing
    - multiline
    - replying
    - editing
    - attaching
    - uploading
    - disabled
    - offline
```

Do not claim a state is supported unless it is visibly implemented.

---

# 14. Accessibility contract

Target WCAG 2.2 AA unless project requirements state otherwise.

Required:

- complete keyboard path for primary workflows,
- visible focus,
- semantic buttons instead of clickable generic containers,
- accessible names for icon-only controls,
- correct labels for search/composer inputs,
- no color-only status communication,
- reasonable target sizes,
- dialogs/menus/comboboxes follow established keyboard interaction patterns,
- reduced-motion preference respected,
- status changes announced when appropriate,
- logical focus restoration after modal/popover closure.

Prefer native HTML semantics before adding ARIA.

---

# 15. Internationalization and content stress

The UI must survive:

- Vietnamese names and messages,
- long English strings,
- strings approximately 1.5× normal label length,
- very long usernames,
- emoji-only names,
- mixed Latin/CJK text,
- long URLs,
- multiline code/text,
- timestamps of different widths,
- RTL layout if future requirements include it.

Do not hard-code layout around short placeholder text.

Use realistic messaging data during design validation.

---

# 16. AI implementation workflow

The AI must follow this order.

## Phase 1 — Read requirements

Identify:

- primary user,
- messaging use case,
- expected conversation volume,
- dominant desktop/mobile environment,
- required features,
- brand constraints.

Do not start with CSS.

## Phase 2 — Select Design Genome

Fill the Design Genome.

## Phase 3 — Produce a short Design Decision Record

Output only concise decisions, not hidden reasoning.

Example:

```yaml
design_decision:
  archetype: topic_stream
  shell: dual_pane
  navigation: conversation_index
  message_presentation: speaker_blocks
  density: compact
  geometry: sharp
  surface_model: border_driven
  primary_reference_ideas:
    - Zulip: topic continuity
    - Element: contextual room identity
  intentionally_avoided:
    - permanent right panel
    - card-based conversation rows
    - floating pill composer
```

## Phase 4 — Define tokens

Create tokens before styling components.

## Phase 5 — Implement structure

Build:

1. shell,
2. navigation,
3. conversation timeline,
4. composer,
5. context behavior.

Do not polish before structure works.

## Phase 6 — Implement states

Use the state matrix.

## Phase 7 — Visual QA

Verify at minimum:

- wide desktop,
- laptop,
- narrow/mobile,
- long text,
- empty state,
- loading,
- unread,
- failed message,
- keyboard focus,
- light/dark if both themes exist.

## Phase 8 — Anti-convergence review

Ask:

- Does this look like a generic AI dashboard?
- Is every region unnecessarily a rounded card?
- Did decoration change more than structure?
- Is the layout nearly identical to one reference product?
- Are there unnecessary gradients/shadows/pills?
- Is the right sidebar present without a workflow reason?
- Is the composer oversized or floating only for aesthetics?
- Could typography/alignment replace some containers?

If yes, revise before completion.

---

# 17. Candidate-generation protocol

When asked to produce multiple design options, do not make color variants.

Each candidate must differ in **at least four** of:

- shell,
- primary navigation,
- conversation index,
- message presentation,
- context-panel strategy,
- density,
- surface model,
- hierarchy method.

Example:

```yaml
candidate_A:
  archetype: focused_dm
  shell: dual_pane
  nav: conversation_index
  messages: grouped_bubbles
  context: none
  density: balanced
  surface: flat

candidate_B:
  archetype: topic_stream
  shell: adaptive_workspace
  nav: contextual
  messages: speaker_blocks
  context: thread_on_demand
  density: compact
  surface: border_driven

candidate_C:
  archetype: support_inbox
  shell: tri_pane
  nav: inbox_filters
  messages: event_feed
  context: contact_profile
  density: compact
  surface: tonal_layers
```

Changing only palette does not count as a new candidate.

---

# 18. Design seed

For repeatable variation, the task may provide:

```text
DESIGN_SEED=42
```

Use the seed to select among valid alternatives **after** requirements and compatibility rules are satisfied.

A seed must never:

- break accessibility,
- randomly change raw CSS values,
- change UX semantics,
- introduce inconsistent spacing,
- override product requirements.

Use seeds for conceptual choices, not noise.

---

# 19. Definition of done

A generated messaging UI is complete only when:

- [ ] Design Genome is specified.
- [ ] The selected archetype matches the product use case.
- [ ] The design does not clone a reference app.
- [ ] Structural variation is intentional.
- [ ] Conversation identity and active state are obvious.
- [ ] Unread and mention states are obvious.
- [ ] Message authorship and chronology are clear.
- [ ] Composer is easy to find and use.
- [ ] Sending/failed/offline states exist.
- [ ] Long content does not break layout.
- [ ] Desktop and mobile behaviors are designed, not merely scaled.
- [ ] Keyboard focus is visible.
- [ ] Icon-only controls have accessible names.
- [ ] Cards, pills, radii and shadows have semantic reasons.
- [ ] No gratuitous gradient/glassmorphism is present.
- [ ] The UI has a product-specific visual character.
- [ ] Visual claims made by the AI are actually implemented.

# 20. Research sources

## Messaging / collaboration repositories

- Zuliphttps://github.com/zulip/zulip
- Mattermosthttps://github.com/mattermost/mattermost
- Element Webhttps://github.com/element-hq/element-web
- Element Compound design systemhttps://github.com/element-hq/compoundhttps://github.com/element-hq/compound-web
- Chatwoothttps://github.com/chatwoot/chatwoot
- Rocket.Chathttps://github.com/RocketChat/Rocket.Chat
- Rocket.Chat Fuselagehttps://github.com/RocketChat/fuselage
- ChatScope Chat UI Kit React
  https://github.com/chatscope/chat-ui-kit-react

## AI / UI research

- Design Theater: Evaluating the Gap Between User-Facing Design Reasoning
  and Implementation in Generative UI Toolshttps://arxiv.org/abs/2607.22928
- Bridging Gulfs in UI Generation through Semantic Guidance
  https://arxiv.org/abs/2601.19171

## Accessibility

- WCAG 2.2https://www.w3.org/TR/WCAG22/
- WAI-ARIA Authoring Practices Guide
  https://www.w3.org/WAI/ARIA/apg/

---

# 21. Final principle

**Familiar semantics, distinctive structure, restrained styling.**

The goal is not to make a messaging interface strange.

The goal is to prevent the AI from repeatedly choosing the same high-probability
layout and decorative vocabulary.

Preserve what users need to recognize.
Vary what the product has a reason to make its own.
