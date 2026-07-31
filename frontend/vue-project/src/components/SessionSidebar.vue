<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

function handleNewChat() {
  store.createSession('New Chat', store.activeProvider, store.activeModel)
}

function handleSelect(id: string) {
  store.selectSession(id)
}
</script>

<template>
  <aside class="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-full shrink-0">
    <!-- Header / Brand -->
    <div class="p-4 border-b border-slate-800 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md">
          L
        </div>
        <div>
          <h1 class="font-bold text-sm text-slate-100 leading-tight">Lenny Assistant</h1>
          <p class="text-xs text-slate-400">Growth RAG Chat</p>
        </div>
      </div>
    </div>

    <!-- New Chat Button -->
    <div class="p-3">
      <button
        @click="handleNewChat"
        :disabled="store.isLoading"
        class="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-lg font-medium text-sm transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        New Chat
      </button>
    </div>

    <!-- Sessions List -->
    <div class="flex-1 overflow-y-auto px-2 py-1 space-y-1">
      <div v-if="store.sessions.length === 0" class="text-xs text-slate-500 text-center py-6">
        No chat sessions yet.
      </div>

      <button
        v-for="session in store.sessions"
        :key="session.id"
        @click="handleSelect(session.id)"
        :class="[
          'w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all flex flex-col gap-0.5 group',
          store.activeSessionId === session.id
            ? 'bg-slate-800 text-white font-medium shadow-inner'
            : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
        ]"
      >
        <div class="flex items-center justify-between">
          <span class="truncate max-w-[170px] text-xs font-semibold">
            {{ session.title || 'New Chat' }}
          </span>
          <span
            :class="[
              'text-[10px] px-1.5 py-0.5 rounded font-mono',
              session.llm_provider === 'ollama'
                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                : 'bg-indigo-950 text-indigo-300 border border-indigo-800'
            ]"
          >
            {{ session.llm_provider === 'ollama' ? 'Local' : 'Cloud' }}
          </span>
        </div>
        <span class="text-[10px] text-slate-500">
          {{ new Date(session.created_at).toLocaleDateString() }}
        </span>
      </button>
    </div>

    <!-- Footer Health Status -->
    <div class="p-3 border-t border-slate-800 text-xs text-slate-400 bg-slate-950/50">
      <div class="flex items-center justify-between text-[11px]">
        <span class="flex items-center gap-1.5">
          <span
            :class="[
              'w-2 h-2 rounded-full',
              store.health?.db ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
            ]"
          ></span>
          Postgres DB
        </span>
        <span :class="store.health?.db ? 'text-emerald-400' : 'text-rose-400'">
          {{ store.health?.db ? 'Online' : 'Offline' }}
        </span>
      </div>

      <div class="flex items-center justify-between text-[11px] mt-1.5">
        <span class="flex items-center gap-1.5">
          <span
            :class="[
              'w-2 h-2 rounded-full',
              store.health?.ollama ? 'bg-emerald-500' : 'bg-amber-500'
            ]"
          ></span>
          Ollama Local
        </span>
        <span :class="store.health?.ollama ? 'text-emerald-400' : 'text-amber-400'">
          {{ store.health?.ollama ? 'Active' : 'Down' }}
        </span>
      </div>
    </div>
  </aside>
</template>
