# Design Notes: Lenny Growth Assistant UI

## Chat UX Decisions

### Streaming Behavior
The chat interface supports server-sent events (SSE) for real-time streaming of assistant responses. Cloud providers (OpenAI/Anthropic via Pi RPC) stream token-by-token, while the local Ollama path renders responses as a single chunk due to the direct-integration tool-calling loop structure. This is a known tradeoff documented in the README.

### Model Toggle Placement
The LLM provider toggle (OpenAI vs. Ollama) is positioned in the session header for immediate accessibility. This placement follows the principle that mode switches should be visible where they affect the current context, not buried in settings. The toggle uses a dropdown pattern familiar from ChatGPT/Claude, reducing learning curve.

### Message Bubble Design
User messages use a right-aligned indigo bubble with a rounded-br-sm corner. Assistant messages use a left-aligned slate-900 bubble with a rounded-bl-sm corner. This asymmetric corner treatment creates visual distinction while maintaining a cohesive aesthetic. A streaming indicator (animated ping dot) appears in empty assistant bubbles during retrieval/generation.

### Session Management Patterns
- **New Chat**: Primary action button in the session sidebar header, following ChatGPT's convention
- **Rename**: Inline edit pattern on session titles (double-click or edit icon), avoiding modal dialogs for quick edits
- **Delete**: Confirmation dialog before deletion to prevent accidental data loss, following standard destructive action patterns

These patterns were chosen because they match established conventions from ChatGPT, Claude, and Slack, reducing user learning curve for a demo application.

## Layout Decisions — Three-Pane Structure

The app uses a persistent three-column horizontal layout that fills the full viewport height:

```
┌─────────────────┬──────────────────────────────────┬─────────────────────┐
│  SessionSidebar │         ChatPane (flex-1)         │   ArtifactViewer    │
│     w-64        │                                   │   w-96 / collapsible│
│  • Brand mark   │  • Chat history                  │  • Preview tab      │
│  • New Chat btn │  • SSE-streamed messages          │  • Code tab         │
│  • Session list │  • Input form                    │  • Multi-artifact   │
│  • Health status│  • System error banners          │    switcher         │
└─────────────────┴──────────────────────────────────┴─────────────────────┘
```

**Why three panes?**

The three-pane layout mirrors established patterns from Notion, Linear, and Slack, where users expect left-nav for navigation, center for content, and right-panel for context/details. For a RAG assistant that generates structured documents, keeping artifacts in a persistent right panel lets the user keep reading the chat while simultaneously reviewing rendered output — they're complementary views of the same answer.

The center pane (`flex-1 min-w-0`) absorbs all leftover width. The right panel collapses to zero when no artifact is active, restoring full-width chat for plain Q&A sessions.

---

## Typography & Color Choices

### Color Palette

| Role | Token | Hex |
|---|---|---|
| App background | `slate-950` | `#020617` |
| Surface (cards, headers) | `slate-900` | `#0f172a` |
| Raised surface | `slate-800` | `#1e293b` |
| Border / divider | `slate-800` | `#1e293b` |
| Body text | `slate-100` | `#f1f5f9` |
| Dimmed text | `slate-400` | `#94a3b8` |
| Accent (interactive) | `indigo-600` | `#4f46e5` |
| Local model indicator | `emerald-500` | `#22c55e` |
| Error / warning | `rose-500` / `amber-500` | `#f43f5e` / `#f59e0b` |

The palette is built on `slate-*` grays, chosen deliberately over `gray-*` or `zinc-*` because slate has a subtle cool-blue cast that reads as technical/data-oriented without feeling clinical. The single accent color (indigo) is used exclusively for interactive elements (buttons, focus rings, selected states) and the user-message chat bubble — nowhere else. This avoids the "purple gradient everywhere" pattern Impeccable calls out as the canonical AI-slop aesthetic.

### Typography

The app uses the system sans-serif stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`) rather than a loaded Google Font, for two reasons:

1. **No FOUT / no layout shift** — system fonts render immediately.
2. **Neutral feel** — the content comes from Lenny's Podcast transcripts; the typography shouldn't compete with or over-brand the reading experience.

### Type Scale (after Impeccable audit)

In the Artifact Viewer's markdown preview, the original type scale had 7 sizes between 12px and 21.6px at a ratio of only 1.08× — Impeccable flagged this as `[flat-type-hierarchy]`. The scale was consolidated to three clear steps:

| Step | Size | Used for |
|---|---|---|
| Base | `0.8rem` (12.8px) | Body, code, table cells |
| Step 1 | `1rem` (16px) | H3 (distinguished by weight, not size) |
| Step 2 | `1.25rem` (20px) | H2 |
| Step 3 | `1.5rem` (24px) | H1 |

Ratio between steps: 1.25× (the standard "Major Third" typographic scale).

---

## Artifact Viewer Design

### Why Tabs (Preview/Code)
The PRD explicitly requires (§3 User Story 4): *"see it rendered live in a side-by-side Artifact Viewer — not as raw text in the chat."* The tab design (`Preview` / `Code`) solves two distinct needs that a single view cannot satisfy:

1. **Preview tab** — the rendered output is what the user cares about. For markdown it shows a properly typeset document (headings, tables, bullet lists, bold). For HTML it shows the actual running UI in a sandboxed iframe so the user sees the artifact *as an artifact*, not as source code.

2. **Code tab** — raw source access is essential for a RAG tool where grounding and transparency matter. Users should be able to inspect exactly what the model wrote, catch hallucinations in citations, copy the raw content, or paste it into another tool.

Keeping them in tabs rather than a split-view preserves panel width for either mode — the rendered markdown and the raw code both need horizontal space to be readable.

### HTML iframe Security
The PRD explicitly calls out (§7 Key Engineering Decisions): *"AI-generated HTML/CSS/JS must never run in the main app frame."* The `<iframe>` uses `sandbox="allow-scripts"` and renders via `srcdoc` (no `src` URL, no cookies, no same-origin access). Raw `v-html` is never used for HTML artifact content.

### Multi-Artifact Switcher
When a session generates more than one artifact (e.g., a Q&A grounded summary followed by a Ship30 essay), the most recent is shown automatically, with a horizontal scrollable tab row appearing above the content area to switch between them. This avoids forcing the user to scroll the chat to re-open a previous artifact. This pattern is inspired by Claude's artifact strip.

---

## Typography & Color Choices

### Color Palette

| Role | Token | Hex |
|---|---|---|
| App background | `slate-950` | `#020617` |
| Surface (cards, headers) | `slate-900` | `#0f172a` |
| Raised surface | `slate-800` | `#1e293b` |
| Border / divider | `slate-800` | `#1e293b` |
| Body text | `slate-100` | `#f1f5f9` |
| Dimmed text | `slate-400` | `#94a3b8` |
| Accent (interactive) | `indigo-600` | `#4f46e5` |
| Local model indicator | `emerald-500` | `#22c55e` |
| Error / warning | `rose-500` / `amber-500` | `#f43f5e` / `#f59e0b` |

The palette is built on `slate-*` grays, chosen deliberately over `gray-*` or `zinc-*` because slate has a subtle cool-blue cast that reads as technical/data-oriented without feeling clinical. The single accent color (indigo) is used exclusively for interactive elements (buttons, focus rings, selected states) and the user-message chat bubble — nowhere else. This avoids the "purple gradient everywhere" pattern Impeccable calls out as the canonical AI-slop aesthetic.

### Typography

The app uses the system sans-serif stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`) rather than a loaded Google Font, for two reasons:

1. **No FOUT / no layout shift** — system fonts render immediately.
2. **Neutral feel** — the content comes from Lenny's Podcast transcripts; the typography shouldn't compete with or over-brand the reading experience.

### Type Scale (after Impeccable audit)

In the Artifact Viewer's markdown preview, the original type scale had 7 sizes between 12px and 21.6px at a ratio of only 1.08× — Impeccable flagged this as `[flat-type-hierarchy]`. The scale was consolidated to three clear steps:

| Step | Size | Used for |
|---|---|---|
| Base | `0.8rem` (12.8px) | Body, code, table cells |
| Step 1 | `1rem` (16px) | H3 (distinguished by weight, not size) |
| Step 2 | `1.25rem` (20px) | H2 |
| Step 3 | `1.5rem` (24px) | H1 |

Ratio between steps: 1.25× (the standard "Major Third" typographic scale).

---

## How Impeccable Was Used in This Process

Impeccable (v3.5.0) was run as a deterministic static analysis step — **no LLM, no API key, no network calls** — directly against the four highest-visibility component files:

```bash
npx impeccable@3.5.0 detect \
  src/components/ChatPane.vue \
  src/components/SessionSidebar.vue \
  src/components/LlmToggle.vue \
  src/components/ArtifactViewer.vue
```

**Scan results — 2 anti-patterns found in `ArtifactViewer.vue`:**

### 1. `[side-tab]` — line 277
> `border-left: 3px solid #6366f1` on blockquotes.
> "Thick colored border on one side of a card — the most recognizable tell of AI-generated UIs."

**Fix applied:** Removed the `border-left` entirely. Replaced with a dark background tint (`background-color: #111827`) and `border-radius`, which achieves visual separation without the AI-slop left-accent pattern.

**Before:**
```css
.markdown-body blockquote {
  border-left: 3px solid #6366f1;
  padding-left: 1rem;
  color: #94a3b8;
  font-style: italic;
}
```

**After:**
```css
.markdown-body blockquote {
  background-color: #111827;
  border-radius: 0.375rem;
  padding: 0.6rem 1rem;
  color: #94a3b8;
  font-style: italic;
}
```

### 2. `[flat-type-hierarchy]` — line 91
> Font sizes 12px / 12.8px / 13.2px / 14px / 16px / 18.4px / 21.6px (ratio 1.08:1).
> "No clear visual hierarchy. Use fewer sizes with more contrast (aim for at least 1.25 ratio between steps)."

**Fix applied:** Collapsed 7 near-identical sizes to 4 clear steps at 1.25× ratio: `0.8rem` → `1rem` → `1.25rem` → `1.5rem`. Table headers were given uppercase `letter-spacing` treatment instead of size inflation to add hierarchy without breaking the scale. H3 headings were promoted to `font-weight: 700` (vs the previous `600`) so they read as distinctly heavier than body text at the same size.

**Post-fix scan result: 0 anti-patterns found** across all four components.

---

## Before / After Summary

| Component | Change | Impeccable Flag |
|---|---|---|
| `ArtifactViewer.vue` — blockquote | `border-left: 3px solid indigo` → dark bg + border-radius | `[side-tab]` |
| `ArtifactViewer.vue` — type scale | 7 micro-stepped sizes (ratio 1.08) → 4 clean steps (ratio 1.25) | `[flat-type-hierarchy]` |
| `ArtifactViewer.vue` — table headers | Added `text-transform: uppercase; letter-spacing: 0.06em` | Part of scale fix |
| `ArtifactViewer.vue` — code font | `monospace` → `ui-monospace, 'Cascadia Code', monospace` | Polish |
| `ChatPane.vue` | No changes needed — scan clean | — |
| `SessionSidebar.vue` | No changes needed — scan clean | — |
| `LlmToggle.vue` | No changes needed — scan clean | — |
