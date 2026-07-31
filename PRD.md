# PRD: The Lenny Growth Assistant

## 1. Problem

Product managers and founders want fast, trustworthy answers to product and
growth questions — grounded specifically in the tactical advice shared on
Lenny's Podcast, not generic LLM knowledge. They also want to turn that
knowledge into publishable content without doing the reformatting work
themselves.

## 2. Target user

A single user (demo context: a solo PM or founder) who wants to:
- Ask grounded product/growth questions and get cited answers
- Convert those answers into a specific, skimmable essay format
- Generate and preview standalone documents or UI snippets without leaving
  the app
- Choose between a cloud model (quality) or a local model (privacy/cost/offline)

## 3. User stories

1. As a user, I can start a new chat session, and each session keeps its
   own independent context (like ChatGPT's "New Chat").
2. As a user, I can ask a product/growth question and receive an answer
   grounded strictly in Lenny's Podcast transcripts, with the guest and
   episode cited.
3. As a user, I can ask the assistant to reformat an answer into a
   Ship30for30-style essay (~1250 words, strong hook, bolded/bulleted for
   skimmability, clear takeaway).
4. As a user, I can ask for a markdown document or an HTML/CSS snippet and
   see it rendered live in a side-by-side Artifact Viewer — not as raw
   text in the chat.
5. As a user, I can switch the underlying LLM (cloud OpenAI vs. local
   Ollama) per session, and the system continues working (or fails
   gracefully) regardless of which is active.
6. As a user, if a required API key is missing or Ollama isn't running,
   I get a clear, actionable error — not a crash or silent hang.

## 4. Scope (v1 — this submission)

- Single-user, no auth
- RAG over the 269 pre-downloaded Lenny's Podcast transcripts
  (pre-embedded at ingestion time, not fetched live per query)
- Two skills: grounded Q&A, Ship30for30 essay generation
- Artifact types: markdown, HTML/CSS (rendered in a sandboxed viewer)
- LLM toggle: OpenAI (cloud, e.g. `gpt-4o-mini`) + Ollama (local),
  configurable per session
- Agent orchestration via Pi Coding Agent (RPC subprocess), custom tools
  only (`search_transcripts`, `generate_ship30_essay`, `create_artifact`);
  default file-editing tools (read/write/edit/bash) disabled
- Hybrid retrieval: topic-tag pre-filter (from the repo's own AI-generated
  index) + pgvector semantic search, with fallback to full-corpus search
- Embeddings: a single local model (`all-MiniLM-L6-v2`) used for both
  cloud and local chat modes, decoupled from the chat LLM toggle (see
  ARCHITECTURE.md for reasoning)

## 5. Non-scope (v1)

- Multi-user accounts / authentication
- Live re-ingestion of new transcripts from the source repo
- Artifact editing UI beyond "regenerate" (versioning is stored, not
  edited in-place)
- Guaranteed streaming parity for every local Ollama model (tool-calling
  reliability varies by model; documented as a known tradeoff)

## 6. Success criteria

- New session persists across page reload with independent history
- Q&A answers cite guest + episode for claims drawn from transcripts
- Ship30for30 output is ~1250 words, has a hook, bolded/bulleted
  structure, and a clear closing takeaway
- Artifact panel opens automatically on generation, renders live
  (no raw code dump), HTML is sandboxed
- Switching LLM provider takes effect on the next message without
  restarting the app
- Missing API key on startup, or Ollama unreachable at request time,
  produces a clear user-facing error, not a 500 or hang

## 7. Key engineering decisions (and why)

| Decision | Reasoning |
|---|---|
| Pi Coding Agent (RPC subprocess) over Claude Agent SDK | Need multi-provider (OpenAI/local, extensible to others) flexibility; Pi is provider-agnostic by design |
| Supabase Postgres + pgvector | Single database for both relational data and vector search — simpler ops for a solo build |
| Hybrid retrieval (topic filter + vector search) | The transcript repo ships pre-built topic tags; using them as a cheap pre-filter avoids full-corpus search on every query and reduces irrelevant retrieval |
| Sandboxed iframe for HTML artifacts | AI-generated HTML/CSS/JS must never run in the main app frame — real XSS surface otherwise |
| One persistent Pi subprocess, not per-request | Spawning a Node process per chat turn would add unacceptable latency; a long-lived RPC server amortizes startup cost |
| Single local embedding model (MiniLM) for both cloud and local chat modes | Keeps the local/offline demo path fully free of cloud calls, and guarantees ingestion-time and query-time vectors always live in the same space |

## 8. Open risks

- **Pi RPC integration is the least-documented piece of this stack.**
  If it's not working reliably after a focused time-boxed spike, the
  fallback is a direct OpenAI SDK client with an equivalent manual tool
  router — same tool contracts, no subprocess. This decision point is
  documented in ARCHITECTURE.md.
- **Tool-calling reliability on small local models** may require a
  simpler JSON-directive fallback instead of native function calling.
