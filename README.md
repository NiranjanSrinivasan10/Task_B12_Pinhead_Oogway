# The Lenny Growth Assistant

A full-stack RAG chatbot and agentic growth assistant grounded strictly in **300+ Lenny's Podcast transcripts**. Supports both Cloud LLM (OpenAI `gpt-4o-mini` / Anthropic) and Local LLM (Ollama `llama3.1:8b`) with multi-provider model switching, hybrid topic-tag + pgvector retrieval, and live sandboxed artifact rendering.

## Project Overview

The Lenny Growth Assistant is a single-user RAG application that lets product managers and founders ask grounded questions about growth tactics, convert answers into Ship30for30-style essays, and generate live-rendered markdown or HTML artifacts. It features a dual-path LLM architecture: cloud providers (OpenAI/Anthropic) use the Pi Coding Agent via JSON-RPC, while the local Ollama path integrates directly via the OpenAI SDK to bypass Pi's provider limitations. All retrieval uses a single local embedding model (`sentence-transformers/all-MiniLM-L6-v2`) for vector-space consistency across both modes.

## Architecture Overview

The system uses a three-tier architecture with a deliberate dual-path design for LLM providers:

```
Vue 3 + TS Frontend  <--REST/SSE-->  FastAPI Backend  <--JSON-RPC/stdio-->  Pi Subprocess (Node)
  (Vite + Tailwind)                      |                                       |
                                         v                                       v
                                Supabase Postgres                   OpenAI / Anthropic (cloud)
                                  (+ pgvector)                         (via Pi RPC)
                                                                             |
                                                                             v
                                                                      Ollama (local)
                                                                   (direct integration,
                                                                    bypasses Pi)
```

**Key architectural decisions:**

- **Dual-path LLM integration**: Cloud providers (OpenAI, Anthropic) use the Pi Coding Agent subprocess for agentic tool-calling. Local Ollama integrates directly via the OpenAI Python SDK pointed at Ollama's OpenAI-compatible endpoint. This bypasses Pi's `getModel` limitation (it only supports built-in providers, not custom ones like Ollama) while reusing the same tool contracts.

- **Single local embedding model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dims) is used for both ingestion and query-time retrieval, regardless of which chat LLM is active. This keeps the local/offline demo path fully free of cloud dependencies and guarantees vector-space consistency.

- **Hybrid retrieval**: Topic-tag pre-filter (from the repo's pre-built index files) → pgvector cosine similarity on filtered chunks → full-corpus fallback if needed.

- **Three tools only**: `search_transcripts`, `generate_ship30_essay`, `create_artifact`. Default Pi file/bash tools are explicitly disabled.

For full architectural details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Local Setup Instructions

### 1. Clone the Repository

```powershell
git clone <repository-url>
cd task_assessment_for_pinhead_b12_and_oogway
```

### 2. Backend Setup

```powershell
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Database Setup (Supabase)

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Open the SQL Editor in your Supabase dashboard
3. Run the migration script located at `backend/migrations/001_init.sql`

**Note**: Supabase will show a warning about RLS (Row Level Security) being disabled. This is safe to ignore for this single-user local application—the app never uses Supabase's public anon/authenticated API, only the direct connection string.

### 4. Environment Configuration

```powershell
# Copy the example environment file
copy .env.example .env
```

Edit `backend/.env` with your actual values:

```env
# Required: Supabase database connection string
SUPABASE_DB_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres

# Required for cloud OpenAI path
OPENAI_API_KEY=sk-proj-YOUR_OPENAI_KEY

# Optional: Anthropic API key (if using Anthropic provider)
ANTHROPIC_API_KEY=sk-ant-YOUR_ANTHROPIC_KEY

# Ollama configuration (local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

**Important**: Do not commit `.env` to version control—it contains sensitive API keys and is already git-ignored.

### 5. Build Pi Runtime Subprocess

The Pi Coding Agent is a Node.js subprocess used for cloud provider tool-calling:

```powershell
cd backend\pi-runtime
npm install
npm run build
```

### 6. Ollama Setup (Local LLM)

```powershell
# Pull the default model
ollama pull llama3.1:8b

# Start the Ollama service
ollama serve
```

**Windows CUDA Driver Issue**: If Ollama crashes with exit code `0xc0000409` and a CUDA "shared object initialization failed" error, this indicates a broken or incompatible NVIDIA driver. Force CPU-only inference by setting:

```powershell
# Set CUDA_VISIBLE_DEVICES=-1 as a persistent user environment variable
[System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '-1', 'User')

# Restart your terminal for the change to take effect, then start Ollama
ollama serve
```

### 7. Run Data Ingestion

Load the Lenny's Podcast transcripts into Supabase and generate embeddings:

```powershell
cd backend
.\venv\Scripts\python.exe -m app.ingestion.run_ingestion
```

**Note**: This uses the local `sentence-transformers/all-MiniLM-L6-v2` model for embeddings. This single model is used for both cloud and local chat modes—a deliberate architectural decision to keep the local demo path fully offline and guarantee vector-space consistency.

### 8. Start the Backend

```powershell
cd backend
.\venv\Scripts\python.exe run.py
```

**Critical Windows Note**: You must use `python run.py` from inside the `backend/` directory, NOT `uvicorn app.main:app --reload`. On Windows, uvicorn's `--reload` spawns worker processes in a separate subprocess that does not inherit the parent's `WindowsProactorEventLoopPolicy`, which is required for the Pi RPC subprocess to spawn correctly. Using `--reload` will cause Pi subprocess spawning to fail with an unhelpful `NotImplementedError`.

Since reload is disabled, code changes require manually restarting the backend (Ctrl+C, confirm clean shutdown, then restart).

### 9. Start the Frontend

```powershell
cd frontend\vue-project
npm install
npm run dev
```

Open your browser at `http://localhost:5173/`.

## Environment Variables Reference

| Variable | Purpose | Required |
|----------|---------|----------|
| `SUPABASE_DB_URL` | Async Postgres connection string for Supabase | Yes |
| `OPENAI_API_KEY` | OpenAI API key for cloud LLM path | Yes (for OpenAI provider) |
| `ANTHROPIC_API_KEY` | Anthropic API key for cloud LLM path | Optional |
| `OLLAMA_BASE_URL` | Base URL for Ollama's OpenAI-compatible API | Optional (defaults to `http://localhost:11434`) |
| `OLLAMA_MODEL` | Default Ollama model to use | Optional (defaults to `llama3.1:8b`) |

## Known Limitations

### From PRD Scope (§5)

- **No authentication/multi-user support**: This is a single-user local application by design per PRD scope.
- **Session deletion is hard delete**: Sessions are permanently deleted (not soft deleted) by design decision, given assignment time constraints.
- **Live re-ingestion not supported**: New transcripts cannot be ingested live from the source repo; this is out of scope for v1.

### Discovered During Development

- **Local model tool-calling reliability**: Ollama's tool-calling reliability is lower than cloud models for complex, multi-part artifact requests (e.g., full interactive HTML/JS tools). Grounded Q&A and simpler markdown artifacts are reliable, but complex generation is best-effort.
- **Ollama single-chunk rendering**: Ollama responses render as a single chunk rather than token-by-token streamed, due to how the direct-integration tool-calling loop is structured in `app/ollama_agent.py`.
- **Cloud/OpenAI streaming rendering issue**: Cloud/OpenAI chat responses may not render incrementally in the chat bubble during active streaming in some cases due to a frontend Vue reactivity issue affecting message_delta accumulation. The final content is always correctly persisted and viewable by reloading/reselecting the session. This is a known frontend rendering issue under active investigation (diagnostic logging present in `session.ts`).

## Links

- [ARCHITECTURE.md](ARCHITECTURE.md) — Authoritative system design and database schema
- [PRD.md](PRD.md) — Product requirements and success criteria
- [docs/design.md](docs/design.md) — UI/UX reasoning and design decisions
- [agent-transcripts/](agent-transcripts/) — Logs from coding agents used during development
