# Design Decision Record — LinguaChat messaging

```yaml
design_decision:
  assumption: LinguaChat is a focused multilingual DM product with real-time translation.
  archetype: focused_dm
  shell: adaptive_workspace
  primary_navigation: conversation_index
  conversation_index: grouped_sections
  message_presentation: speaker_blocks
  message_grouping: consecutive_sender
  metadata_visibility: contextual
  composer: expandable
  secondary_context: on_demand
  density: balanced
  geometry: sharp
  surface_model: tonal_layers
  hierarchy_method: mixed_restrained
  visual_character: editorial
  accent_strategy: unread_and_status
  intentionally_avoided:
    - icon rail
    - permanent right panel
    - card-based conversation rows
    - bubbles for every message
    - floating pill composer
```

The primary product-specific behavior is inline source/translation pairing. Desktop uses a conversation ledger beside an edge-to-edge reading canvas; mobile becomes a list-to-conversation navigation stack.
