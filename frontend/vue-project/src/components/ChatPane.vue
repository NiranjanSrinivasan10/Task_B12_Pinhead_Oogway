<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import LlmToggle from './LlmToggle.vue'

const store = useSessionStore()
const inputContent = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(
  () => store.activeSession?.messages?.length,
  () => scrollToBottom()
)

watch(
  () => store.activeSession?.messages?.slice(-1)[0]?.content,
  () => scrollToBottom()
)

function handleSubmit() {
  if (!inputContent.value.trim() || store.isStreaming) return
  const text = inputContent.value
  inputContent.value = ''
  store.sendMessage(text)
  scrollToBottom()
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}

const showOllamaWarning = computed(() => {
  return store.activeProvider === 'ollama' && store.health && !store.health.ollama
})

const showDbError = computed(() => {
  return store.health && !store.health.db
})
</script>

<template>
  <main class="flex-1 flex flex-col h-full bg-slate-950 min-w-0 relative">
    <!-- Header -->
    <header class="h-16 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/50 backdrop-blur shrink-0">
      <div class="flex items-center gap-3">
        <h2 class="font-bold text-slate-100 text-base truncate">
          {{ store.activeSession?.title || 'Lenny Growth Assistant' }}
        </h2>
      </div>
      <LlmToggle />
    </header>

    <!-- System Banners -->
    <div v-if="showDbError" class="bg-rose-950/90 border-b border-rose-800 px-4 py-2 text-xs text-rose-200 flex items-center justify-between shrink-0">
      <span class="flex items-center gap-2 font-medium">
        <svg class="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        Database connection offline — check backend/.env SUPABASE_DB_URL.
      </span>
    </div>

    <div v-if="showOllamaWarning" class="bg-amber-950/90 border-b border-amber-800 px-4 py-2 text-xs text-amber-200 flex items-center justify-between shrink-0">
      <span class="flex items-center gap-2 font-medium">
        <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Local model unavailable — is <code class="bg-amber-900/50 px-1 rounded">ollama serve</code> running on port 11434?
      </span>
    </div>

    <div v-if="store.errorMessage" class="bg-rose-900/80 border-b border-rose-700 px-4 py-2 text-xs text-rose-100 flex items-center justify-between shrink-0">
      <span class="truncate font-medium">
        ⚠️ {{ store.errorMessage }}
      </span>
      <button @click="store.errorMessage = null" class="text-rose-300 hover:text-white font-bold ml-2">
        ✕
      </button>
    </div>

    <!-- Messages Container -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-6 space-y-6">
      <div v-if="!store.activeSession?.messages?.length" class="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4 text-slate-400 my-12">
        <div class="w-14 h-14 rounded-2xl bg-indigo-950/80 border border-indigo-800 flex items-center justify-center text-indigo-400 shadow-lg">
          <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <div>
          <h3 class="font-bold text-slate-100 text-lg">Ask Lenny's Growth Assistant</h3>
          <p class="text-xs text-slate-400 mt-1 leading-relaxed">
            Search 300+ Lenny's Podcast transcripts, generate grounded growth advice, or create Ship30for30 essays.
          </p>
        </div>
        <div class="grid grid-cols-1 gap-2 w-full text-xs pt-2">
          <button
            @click="inputContent = 'How do top product leaders determine Product-Market Fit?'; handleSubmit()"
            class="p-3 bg-slate-900 hover:bg-slate-850 rounded-xl border border-slate-800 text-left text-slate-300 transition-colors"
          >
            💡 "How do top product leaders determine Product-Market Fit?"
          </button>
          <button
            @click="inputContent = 'Generate a Ship30 essay on growth loops vs funnel marketing.'; handleSubmit()"
            class="p-3 bg-slate-900 hover:bg-slate-850 rounded-xl border border-slate-800 text-left text-slate-300 transition-colors"
          >
            🚀 "Generate a Ship30 essay on growth loops vs funnel marketing."
          </button>
        </div>
      </div>

      <!-- Render Messages -->
      <div
        v-for="msg in store.activeSession?.messages"
        :key="msg.id"
        :class="[
          'flex flex-col max-w-3xl',
          msg.role === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'
        ]"
      >
        <!-- Role Header -->
        <div class="flex items-center gap-2 mb-1 text-[11px] text-slate-400 px-1">
          <span class="font-semibold text-slate-300">
            {{ msg.role === 'user' ? 'You' : 'Lenny Assistant' }}
          </span>

          <!-- Skill Badge -->
          <span
            v-if="msg.skill_used"
            class="bg-indigo-950 text-indigo-300 border border-indigo-800 text-[10px] px-2 py-0.5 rounded-full font-mono font-medium flex items-center gap-1"
          >
            ⚡ {{ msg.skill_used }}
          </span>
        </div>

        <!-- Bubble Body -->
        <div
          :class="[
            'rounded-2xl p-4 text-sm leading-relaxed whitespace-pre-wrap shadow-md border',
            msg.role === 'user'
              ? 'bg-indigo-600 text-white border-indigo-500 rounded-br-xs'
              : 'bg-slate-900 text-slate-100 border-slate-800 rounded-bl-xs'
          ]"
        >
          {{ msg.content }}

          <!-- Streaming Indicator -->
          <span
            v-if="msg.isStreaming && !msg.content"
            class="inline-flex items-center gap-1 text-slate-400 py-1"
          >
            <span class="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
            Thinking & retrieving transcripts...
          </span>

          <!-- Error message if any -->
          <div
            v-if="msg.error"
            class="mt-2 pt-2 border-t border-rose-800 text-xs text-rose-300 font-mono"
          >
            ❌ {{ msg.error }}
          </div>
        </div>
      </div>
    </div>

    <!-- Input Footer -->
    <div class="p-4 border-t border-slate-800 bg-slate-900/50 shrink-0">
      <form @submit.prevent="handleSubmit" class="max-w-3xl mx-auto relative flex items-end bg-slate-900 rounded-2xl border border-slate-800 focus-within:border-indigo-500 transition-colors shadow-lg">
        <textarea
          v-model="inputContent"
          @keydown="handleKeyDown"
          placeholder="Ask a question grounded in Lenny's Podcast transcripts... (Shift+Enter for newline)"
          rows="2"
          class="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm p-4 focus:outline-none resize-none min-h-[56px] max-h-32"
          :disabled="store.isStreaming"
        ></textarea>

        <button
          type="submit"
          :disabled="!inputContent.trim() || store.isStreaming"
          class="m-2 p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm shrink-0"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </button>
      </form>
      <div class="text-[10px] text-slate-500 text-center mt-2">
        Lenny Growth Assistant uses hybrid topic-tag + pgvector transcript retrieval.
      </div>
    </div>
  </main>
</template>
