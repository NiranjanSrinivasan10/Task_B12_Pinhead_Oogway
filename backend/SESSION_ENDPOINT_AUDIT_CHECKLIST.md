# Session Endpoint Audit Checklist

This checklist ensures that any endpoint returning `SessionOut` properly handles lazy-loaded relationships to avoid MissingGreenlet errors.

## Background

`SessionOut` schema includes two lazy-loaded relationships:
- `messages: List[MessageOut] = []`
- `artifacts: List[ArtifactOut] = []`

When Pydantic validates a SQLAlchemy model with `from_attributes=True`, it attempts to access these relationships synchronously. In an async context, this triggers `MissingGreenlet` errors unless the relationships are eagerly loaded.

## Audit Rules

### Rule 1: For endpoints returning `SessionOut` with existing session data

**Endpoints affected:**
- `GET /sessions/{id}` - get session with full history
- `PATCH /sessions/{id}/config` - update provider/model

**Requirement:** The query MUST use `selectinload` for BOTH relationships:
```python
.options(selectinload(SessionModel.messages))
.options(selectinload(SessionModel.artifacts))
```

**Why:** `db.refresh()` does NOT reload relationships. A fresh query with eager loading is required.

---

### Rule 2: For endpoints creating brand-new sessions

**Endpoints affected:**
- `POST /sessions` - create new session

**Requirement:** Explicitly construct the response with empty lists:
```python
return SessionOut(
    id=session.id,
    title=session.title,
    llm_provider=session.llm_provider,
    llm_model=session.llm_model,
    created_at=session.created_at,
    updated_at=session.updated_at,
    messages=[],  # Explicit empty list
    artifacts=[],  # Explicit empty list
)
```

**Why:** A new session has zero messages and zero artifacts by definition. No lazy load needed.

---

### Rule 3: For endpoints returning `SessionListItem`

**Endpoints affected:**
- `GET /sessions` - list all sessions
- `PATCH /sessions/{id}` - rename session

**Requirement:** No action needed. `SessionListItem` does NOT include messages or artifacts fields.

**Why:** The slimmer schema avoids the lazy-load issue entirely.

---

## Current Status (Last Audit: 2026-08-02)

| Endpoint | Schema | Query Pattern | Status |
|----------|--------|---------------|--------|
| POST /sessions | SessionOut | Explicit construction with messages=[], artifacts=[] | ✅ PASS |
| GET /sessions | SessionListItem | N/A (no relationships) | ✅ PASS |
| GET /sessions/{id} | SessionOut | selectinload(messages) + selectinload(artifacts) | ✅ PASS |
| PATCH /sessions/{id}/config | SessionOut | selectinload(messages) + selectinload(artifacts) | ✅ PASS |
| PATCH /sessions/{id} | SessionListItem | N/A (no relationships) | ✅ PASS |
| DELETE /sessions/{id} | None (204) | N/A | ✅ PASS |

---

## Regression Prevention

When modifying `SessionOut` schema:
1. Add any new relationship fields to this checklist
2. Re-audit all endpoints returning `SessionOut`
3. Update this checklist with the new field requirements

When adding new session endpoints:
1. Identify which schema the endpoint returns
2. Follow the appropriate rule from above
3. Add the endpoint to the status table

---

## Manual Test Procedure

To verify the fix works:

1. **Test POST /sessions:**
   ```bash
   curl -X POST http://localhost:8000/sessions \
     -H "Content-Type: application/json" \
     -d '{"title": "Test Session", "llm_provider": "openai", "llm_model": "gpt-4o-mini"}'
   ```
   Expected: 201 response with `messages: []` and `artifacts: []`

2. **Test PATCH /sessions/{id}/config:**
   ```bash
   curl -X PATCH http://localhost:8000/sessions/{id}/config \
     -H "Content-Type: application/json" \
     -d '{"llm_provider": "ollama", "llm_model": "llama3.1:8b"}'
   ```
   Expected: 200 response (not 500), with updated provider/model

3. **Test GET /sessions/{id}:**
   ```bash
   curl http://localhost:8000/sessions/{id}
   ```
   Expected: 200 response with messages and artifacts arrays populated

4. **Frontend verification:**
   - Switch a session to Ollama via LLM toggle
   - Confirm badge updates to "Local"
   - Switch back to OpenAI
   - Confirm badge updates to "Cloud"
