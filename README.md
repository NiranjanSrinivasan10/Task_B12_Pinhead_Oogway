# The Lenny Growth Assistant

A full-stack RAG chatbot and agentic growth assistant grounded strictly in **300+ Lenny's Podcast transcripts**. Supports both Cloud LLM (OpenAI `gpt-4o-mini` / Anthropic) and Local LLM (Ollama `llama3.1:8b`) with multi-provider model switching, hybrid topic-tag + pgvector retrieval, and live sandboxed artifact rendering.

---

## 🏗️ Architecture Overview

```
Vue 3 + TS Frontend  <--REST/SSE-->  FastAPI Backend  <--JSON-RPC/stdio-->  Pi Subprocess (Node)
  (Vite + Tailwind)                      |                                       |
                                         v                                       v
                                Supabase Postgres                   Anthropic / OpenAI / Ollama
                                  (+ pgvector)
```

- **Frontend**: Vue 3 + TypeScript + Tailwind CSS (v4) + Pinia store + `marked` (GFM markdown rendering) + Sandboxed `<iframe>` HTML viewer.
- **Backend**: FastAPI (Python 3.12) with SQLAlchemy async sessions and Pydantic validation.
- **Agent Orchestration**: Pi Coding Agent (Node.js JSON-RPC subprocess over stdio) executing 3 custom tools (`search_transcripts`, `generate_ship30_essay`, `create_artifact`).
- **Database & Vectors**: Supabase Postgres + `pgvector` (`vector(384)`) using local `sentence-transformers/all-MiniLM-L6-v2` embeddings for vector-space consistency across both cloud and local modes.

---

## 🚀 Quickstart Guide

### 1. Database Setup (Supabase)
Run the migration script in your Supabase SQL Editor:
```sql
-- Located in backend/migrations/001_init.sql
```
This enables `vector`, `uuid-ossp`, and creates `episodes`, `chunks`, `sessions`, `messages`, and `artifacts` tables.

### 2. Backend Setup
```powershell
cd backend

# Create & activate venv
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure .env
cp .env.example .env
```

Edit `backend/.env`:
```env
SUPABASE_DB_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
OPENAI_API_KEY=sk-proj-YOUR_KEY
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

### 3. Run Ingestion (Load Transcripts into Supabase)
```powershell
python -m app.ingestion.run_ingestion
```

### 4. Build Pi Runtime Subprocess
```powershell
cd backend/pi-runtime
npm install
npm run build
```

### 5. Launch Servers
- **Backend**: `python run.py` (from `backend/`)
- **Frontend**: `npm run dev` (from `frontend/vue-project/`)
- Open browser at `http://localhost:5173/`

---

## 🔍 Health Check Behavior & Lazy-Start Subprocess (PRD Scenario 8)

When calling `GET /health` immediately after launching the backend server:

```json
{
  "status": "degraded",
  "db": true,
  "ollama": true,
  "pi_subprocess": false,
  "details": {
    "ollama": "reachable",
    "pi": "not started",
    "ollama_base_url": "http://localhost:11434"
  }
}
```

### ℹ️ Expected Lazy-Start Behavior (Not a Bug)
- **Initial State**: `pi_subprocess: false` (`"not started"`). The Node.js Pi agent subprocess is intentionally **lazy-loaded** to minimize idle memory usage and avoid unnecessary process spawning on startup.
- **Transition**: The moment the first chat message is sent (`POST /sessions/{id}/messages`), `pi_client.py` automatically initializes and spawns the persistent Node.js subprocess.
- **Active State**: Subsequent calls to `GET /health` will report `pi_subprocess: true` (`"running"`) and `status: "ok"`.

---

## 🧪 PRD Success Criteria Scenario Testing Matrix

| Scenario | Requirement | Observed Empirical Result | Status |
|---|---|---|---|
| **1. Grounded Q&A** | Fresh session -> Ask grounded question -> Verify citations | Assistant retrieves vector chunks via `search_transcripts`, grounding answer strictly in transcript excerpts and citing guest & episode. | ✅ PASS |
| **2. Ship30 Essay** | Ask for Ship30for30 reformat -> Verify ~1250 words, hook, bullets, takeaway | Agent invokes `generate_ship30_essay` tool. Output contains a prominent hook, bolded/bulleted structure, and closing takeaway. | ✅ PASS |
| **3. Markdown Artifact** | Ask for markdown artifact -> Verify side-by-side rendering | Fires `artifact_created` SSE event. `ArtifactViewer.vue` panel auto-expands and renders GFM markdown via `marked.js` in Preview tab. | ✅ PASS |
| **4. HTML Artifact Sandbox** | Ask for HTML snippet artifact -> Verify sandboxed iframe | Renders inside `<iframe :srcdoc="..." sandbox="allow-scripts">`. Confirmed strict security boundary preventing parent DOM/cookie access. | ✅ PASS |
| **5. Ollama Disconnection** | Switch to Ollama mid-session, stop server, send message | `messages.py` catches `PiRPCError`, yielding structured SSE event `{"type": "error", "message": "Local model unavailable — is ollama serve running?"}` without hanging or crashing. | ✅ PASS |
| **6. Missing API Key** | Remove `OPENAI_API_KEY`, request cloud completion | `POST /sessions/{id}/messages` returns **HTTP 422 Unprocessable Entity** (`{"code": "missing_api_key", ...}`) *before* opening SSE stream. No raw stack traces shown. | ✅ PASS |
| **7. Out-of-Corpus Query** | Ask question with no transcript match | System prompt rule enforces: *"If retrieval produces no relevant results, explicitly say so rather than guessing."* Agent explicitly responds that transcripts do not contain information on the topic. | ✅ PASS |
| **8. Health State Transition** | `GET /health` shows `pi_subprocess: false` on boot $\rightarrow$ flips to `true` after 1 message | Verified lazy-start lifecycle: initial `/health` reports `"pi": "not started"`. Spawns on first turn, subsequent `/health` reports `"pi": "running"`. | ✅ PASS |

---

## 🧪 Running Automated Tests

Run the offline endpoint and scenario test suite from `backend/`:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_prd_scenarios.py tests/test_endpoints.py -v
```

---

## 🛠️ Troubleshooting & Known Limitations

### Windows Event Loop & Subprocess Spawning (`python run.py`)
- **Proactor Event Loop Required**: On Windows, `asyncio`'s default `SelectorEventLoop` does not support subprocess creation (`create_subprocess_exec`), raising `NotImplementedError` when attempting to spawn the Node.js Pi agent.
- **Reloader Subprocess Boundary (`reload=False`)**: Uvicorn's `--reload` mode spawns worker processes in a separate subprocess that does not inherit process-local event loop policies set in module space. Therefore, `backend/run.py` explicitly sets `WindowsProactorEventLoopPolicy()` and launches Uvicorn with `reload=False`.
- **Manual Restart**: On Windows, backend code edits require restarting `python run.py` manually.

### Windows CUDA Driver Issues with Ollama
On Windows machines with broken or incompatible CUDA drivers, Ollama may crash with exit code `0xc0000409` and a CUDA "shared object initialization failed" error. To resolve this, run Ollama in CPU-only mode by setting the `CUDA_VISIBLE_DEVICES` environment variable to `-1` as a persistent user environment variable.

**Symptom:**
- Ollama crashes immediately with exit code `0xc0000409`
- Error message mentions CUDA "shared object initialization failed"

**Solution (PowerShell):**
```powershell
# Set CUDA_VISIBLE_DEVICES=-1 as a persistent user environment variable
[System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '-1', 'User')

# Restart your terminal for the change to take effect
# Then start Ollama normally
ollama serve
```

This forces Ollama to use CPU-only inference, avoiding CUDA driver compatibility issues while still providing full local LLM functionality.
