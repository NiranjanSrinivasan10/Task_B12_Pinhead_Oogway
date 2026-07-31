# AGENTS.md — The Lenny Growth Assistant

Read this file before starting any work on this project.

## Hard Constraints

1. **Python venv** — All backend deps install into `backend/venv/`. Never install globally.
   Activate: `backend\venv\Scripts\activate` (Windows) or `source backend/venv/bin/activate` (Unix).
2. **No re-scaffolding** — `frontend/vue-project/` is an existing Vue 3 + TS project. Inspect before editing.
3. **No secrets in code** — All API keys go in `backend/.env` (git-ignored). Provide `backend/.env.example` with placeholders.
4. **Follow ARCHITECTURE.md** — Do not substitute your own design without flagging the deviation and explaining why.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vue 3 + TypeScript (Vite) |
| Backend | Python — FastAPI |
| Database | Supabase Postgres + pgvector |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384 dims, local, used for both ingestion & query) |
| Agent | Pi Coding Agent (Node subprocess, JSON-RPC/stdio) |
| Cloud LLM | OpenAI (`gpt-4o-mini`) — key from `OPENAI_API_KEY` |
| Local LLM | Ollama (OpenAI-compat endpoint at `localhost:11434/v1`) |
| Streaming | SSE (`message_delta`, `artifact_created`, `error`) |

## Folder Map

```
project-root/
├── ARCHITECTURE.md          # Authoritative system design
├── PRD.md                   # Product requirements
├── AGENTS.md                # This file — read first
├── .gitignore
├── backend/                 # FastAPI app
│   ├── venv/                # Python virtual environment (git-ignored)
│   ├── .env                 # Secrets (git-ignored)
│   └── .env.example         # Placeholder secrets template
├── frontend/
│   └── vue-project/         # Vue 3 + TS (Vite) — pre-scaffolded
├── dataset/
│   └── lennys-podcast-transcripts-main/
│       ├── episodes/{guest}/transcript.md   # 303 transcripts w/ YAML frontmatter
│       └── index/{topic}.md                 # 88 AI-generated topic-tag files
├── agent-transcripts/       # Logs from coding agents
│   ├── antigravity/
│   ├── devin/
│   └── copilot/
└── docs/
    └── design.md            # Design notes (placeholder)
```

## Key Design Decisions (from ARCHITECTURE.md)

- **Hybrid retrieval**: topic-tag pre-filter (from `index/`) → pgvector cosine similarity on filtered chunks → full-corpus fallback.
- **Three tools only**: `search_transcripts`, `generate_ship30_essay`, `create_artifact`. Default file/bash tools disabled.
- **Embedding model is decoupled** from the chat LLM toggle — MiniLM runs locally for both cloud and local chat modes.
- **Pi RPC fallback**: if Pi subprocess proves unreliable, fall back to direct OpenAI/Anthropic SDK client with the same tool contracts.

## DB Schema (key tables)

`episodes` · `chunks` (w/ `embedding vector(384)`) · `sessions` · `messages` · `artifacts`

See ARCHITECTURE.md §2 for full column definitions.

## API Endpoints

`POST /sessions` · `GET /sessions` · `GET /sessions/{id}` · `PATCH /sessions/{id}/config` · `POST /sessions/{id}/messages` (SSE) · `GET /artifacts/{id}` · `GET /health`

## Dataset Quick Ref

- **303 guest folders** in `dataset/lennys-podcast-transcripts-main/episodes/`
- **Frontmatter fields**: `guest`, `title`, `youtube_url`, `video_id`, `publish_date`, `description`, `duration_seconds`, `duration`, `view_count`, `channel`, `keywords[]`
- **88 topic index files** in `dataset/lennys-podcast-transcripts-main/index/` (markdown bullet lists linking episodes to topics)
