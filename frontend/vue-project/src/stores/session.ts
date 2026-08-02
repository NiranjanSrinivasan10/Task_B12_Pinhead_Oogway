import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Message {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  skill_used?: string | null
  retrieved_chunk_ids?: string[]
  created_at?: string
  isStreaming?: boolean
  error?: string | null
}

export interface Artifact {
  id: string
  message_id: string
  session_id: string
  type: string
  title: string
  content: string
  version: number
  created_at: string
}

export interface Session {
  id: string
  title: string
  llm_provider: 'openai' | 'anthropic' | 'ollama'
  llm_model: string
  created_at: string
  updated_at: string
  messages?: Message[]
  artifacts?: Artifact[]
}

export interface HealthInfo {
  status: 'ok' | 'degraded' | 'unhealthy'
  db: boolean
  ollama: boolean
  pi_subprocess: boolean
  details?: Record<string, any>
}

const API_BASE = 'http://localhost:8000'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<Session[]>([])
  const activeSessionId = ref<string | null>(null)
  const activeSession = ref<Session | null>(null)
  const isLoading = ref(false)
  const isStreaming = ref(false)
  const errorMessage = ref<string | null>(null)
  const health = ref<HealthInfo | null>(null)
  const activeArtifact = ref<Artifact | null>(null)
  const artifacts = ref<Artifact[]>([])
  const isArtifactPanelOpen = ref(true)

  const activeProvider = computed(() => activeSession.value?.llm_provider || 'openai')
  const activeModel = computed(() => activeSession.value?.llm_model || 'gpt-4o-mini')

  function addArtifact(art: Artifact) {
    const idx = artifacts.value.findIndex(a => a.id === art.id)
    if (idx !== -1) {
      artifacts.value[idx] = art
    } else {
      artifacts.value.push(art)
    }
    activeArtifact.value = art
    isArtifactPanelOpen.value = true
  }

  function selectArtifact(id: string) {
    const found = artifacts.value.find(a => a.id === id)
    if (found) {
      activeArtifact.value = found
    }
  }

  function toggleArtifactPanel() {
    isArtifactPanelOpen.value = !isArtifactPanelOpen.value
  }

  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`)
      if (res.ok) {
        health.value = await res.json()
      }
    } catch (err) {
      health.value = {
        status: 'unhealthy',
        db: false,
        ollama: false,
        pi_subprocess: false,
        details: { error: 'Backend API unreachable' }
      }
    }
  }

  async function fetchSessions() {
    isLoading.value = true
    errorMessage.value = null
    try {
      const res = await fetch(`${API_BASE}/sessions`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      sessions.value = data
      if (data.length > 0 && !activeSessionId.value) {
        await selectSession(data[0].id)
      }
    } catch (err: any) {
      errorMessage.value = `Failed to load sessions: ${err.message}`
    } finally {
      isLoading.value = false
    }
  }

  async function selectSession(id: string) {
    activeSessionId.value = id
    isLoading.value = true
    errorMessage.value = null
    try {
      const res = await fetch(`${API_BASE}/sessions/${id}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      activeSession.value = data
      // Load artifacts from session
      if (data.artifacts && Array.isArray(data.artifacts)) {
        artifacts.value = data.artifacts
        // Set the most recent artifact as active if available
        if (data.artifacts.length > 0) {
          activeArtifact.value = data.artifacts[data.artifacts.length - 1]
        } else {
          activeArtifact.value = null
        }
      } else {
        artifacts.value = []
        activeArtifact.value = null
      }
    } catch (err: any) {
      errorMessage.value = `Failed to load session details: ${err.message}`
    } finally {
      isLoading.value = false
    }
  }

  async function createSession(title = 'New Chat', provider = 'openai', model = 'gpt-4o-mini') {
    isLoading.value = true
    errorMessage.value = null
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, llm_provider: provider, llm_model: model })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const newSession: Session = await res.json()
      sessions.value.unshift(newSession)
      activeSessionId.value = newSession.id
      activeSession.value = { ...newSession, messages: [] }
      // Clear artifacts for new session
      artifacts.value = []
      activeArtifact.value = null
      return newSession
    } catch (err: any) {
      errorMessage.value = `Failed to create session: ${err.message}`
    } finally {
      isLoading.value = false
    }
  }

  async function updateConfig(provider: 'openai' | 'anthropic' | 'ollama', model: string) {
    if (!activeSession.value) return
    const id = activeSession.value.id
    try {
      const res = await fetch(`${API_BASE}/sessions/${id}/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ llm_provider: provider, llm_model: model })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const updated = await res.json()
      activeSession.value.llm_provider = updated.llm_provider
      activeSession.value.llm_model = updated.llm_model

      const sIdx = sessions.value.findIndex(s => s.id === id)
      if (sIdx !== -1 && sessions.value[sIdx]) {
        sessions.value[sIdx].llm_provider = updated.llm_provider
        sessions.value[sIdx].llm_model = updated.llm_model
      }
    } catch (err: any) {
      errorMessage.value = `Failed to update model config: ${err.message}`
    }
  }

  async function renameSession(id: string, newTitle: string) {
    try {
      const res = await fetch(`${API_BASE}/sessions/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const updated = await res.json()

      // Update local state
      const sIdx = sessions.value.findIndex(s => s.id === id)
      if (sIdx !== -1 && sessions.value[sIdx]) {
        sessions.value[sIdx].title = updated.title
        sessions.value[sIdx].updated_at = updated.updated_at
      }
      if (activeSession.value?.id === id) {
        activeSession.value.title = updated.title
        activeSession.value.updated_at = updated.updated_at
      }
    } catch (err: any) {
      errorMessage.value = `Failed to rename session: ${err.message}`
      throw err
    }
  }

  async function deleteSession(id: string) {
    try {
      const res = await fetch(`${API_BASE}/sessions/${id}`, {
        method: 'DELETE'
      })
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`)

      // Remove from local state
      sessions.value = sessions.value.filter(s => s.id !== id)

      // If deleted session was active, switch to another or create new
      if (activeSessionId.value === id) {
        if (sessions.value.length > 0 && sessions.value[0]) {
          await selectSession(sessions.value[0].id)
        } else {
          await createSession()
        }
      }
    } catch (err: any) {
      errorMessage.value = `Failed to delete session: ${err.message}`
      throw err
    }
  }

  async function sendMessage(content: string) {
    if (!activeSession.value || isStreaming.value) return
    errorMessage.value = null

    const session = activeSession.value
    if (!session.messages) session.messages = []

    // 1. Append User Message
    const userMsgId = `temp-user-${Date.now()}`
    session.messages.push({
      id: userMsgId,
      session_id: session.id,
      role: 'user',
      content: content.trim()
    })

    // 2. Append Assistant Placeholder
    const assistantMsgId = `temp-asst-${Date.now()}`
    const assistantMsg: Message = {
      id: assistantMsgId,
      session_id: session.id,
      role: 'assistant',
      content: '',
      isStreaming: true
    }
    session.messages.push(assistantMsg)
    isStreaming.value = true

    try {
      const res = await fetch(`${API_BASE}/sessions/${session.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content.trim() })
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        const msg = errorData.detail?.message || errorData.detail || `HTTP ${res.status}`
        assistantMsg.error = typeof msg === 'string' ? msg : JSON.stringify(msg)
        assistantMsg.isStreaming = false
        errorMessage.value = assistantMsg.error
        return
      }

      if (!res.body) {
        throw new Error('No response body for SSE stream')
      }

      // 3. Consume SSE Stream
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const block of lines) {
          if (!block.trim()) continue
          let currentEvent = 'message'
          let currentData = ''

          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              currentData += line.slice(5).trim()
            }
          }

          if (currentData) {
            try {
              const parsed = JSON.parse(currentData)
              if (currentEvent === 'message_delta') {
                assistantMsg.content += parsed.content || ''
              } else if (currentEvent === 'artifact_created') {
                // Map artifact_type to type for compatibility with Artifact interface
                const artifact = { ...parsed, type: parsed.artifact_type || parsed.type }
                addArtifact(artifact)
              } else if (currentEvent === 'error') {
                errorMessage.value = parsed.message || 'Unknown error'
                assistantMsg.error = parsed.message || 'Unknown error'
              } else if (currentEvent === 'done') {
                if (parsed.message_id) assistantMsg.id = parsed.message_id
                if (parsed.skill_used) assistantMsg.skill_used = parsed.skill_used || null
              }
            } catch (e) {
              console.warn('Failed to parse SSE payload:', currentData)
            }
          }
        }
      }
    } catch (err: any) {
      assistantMsg.error = (err.message || 'Stream connection failed') as string | null
      errorMessage.value = assistantMsg.error
    } finally {
      assistantMsg.isStreaming = false
      isStreaming.value = false
    }
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    isLoading,
    isStreaming,
    errorMessage,
    health,
    activeArtifact,
    artifacts,
    isArtifactPanelOpen,
    activeProvider,
    activeModel,
    checkHealth,
    fetchSessions,
    selectSession,
    createSession,
    updateConfig,
    renameSession,
    deleteSession,
    sendMessage,
    addArtifact,
    selectArtifact,
    toggleArtifactPanel
  }
})
