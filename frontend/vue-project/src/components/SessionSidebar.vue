<script setup lang="ts">
import { ref } from 'vue'
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const menuOpenId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const editTitle = ref('')
const showDeleteConfirm = ref<string | null>(null)

function handleNewChat() {
  store.createSession('New Chat', store.activeProvider, store.activeModel)
}

function handleSelect(id: string) {
  if (editingId.value !== id) {
    store.selectSession(id)
  }
}

function toggleMenu(id: string, event: Event) {
  event.stopPropagation()
  menuOpenId.value = menuOpenId.value === id ? null : id
}

function closeMenu() {
  menuOpenId.value = null
}

function startRename(id: string, currentTitle: string) {
  editingId.value = id
  editTitle.value = currentTitle
  menuOpenId.value = null
}

function cancelRename() {
  editingId.value = null
  editTitle.value = ''
}

async function saveRename(id: string) {
  if (editTitle.value.trim()) {
    try {
      await store.renameSession(id, editTitle.value.trim())
      cancelRename()
    } catch (err) {
      console.error('Failed to rename:', err)
    }
  }
}

function handleKeyDown(event: KeyboardEvent, id: string) {
  if (event.key === 'Enter') {
    saveRename(id)
  } else if (event.key === 'Escape') {
    cancelRename()
  }
}

function confirmDelete(id: string) {
  showDeleteConfirm.value = id
  menuOpenId.value = null
}

function cancelDelete() {
  showDeleteConfirm.value = null
}

async function handleDelete(id: string) {
  try {
    await store.deleteSession(id)
    showDeleteConfirm.value = null
  } catch (err) {
    console.error('Failed to delete:', err)
  }
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
    <div class="flex-1 overflow-y-auto px-2 py-1 space-y-1" @click="closeMenu">
      <div v-if="store.sessions.length === 0" class="text-xs text-slate-500 text-center py-6">
        No chat sessions yet.
      </div>

      <div
        v-for="session in store.sessions"
        :key="session.id"
        :class="[
          'relative rounded-lg text-sm transition-all group',
          store.activeSessionId === session.id
            ? 'bg-slate-800 text-white font-medium shadow-inner'
            : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
        ]"
      >
        <!-- Session Item -->
        <button
          @click="handleSelect(session.id)"
          class="w-full text-left px-3 py-2.5 flex flex-col gap-0.5"
        >
          <!-- Delete Confirmation -->
          <div v-if="showDeleteConfirm === session.id" class="flex items-center gap-2 py-1">
            <span class="text-[10px] text-rose-400">Delete this session?</span>
            <button
              @click.stop="handleDelete(session.id)"
              class="text-[10px] px-2 py-0.5 bg-rose-600 hover:bg-rose-500 text-white rounded transition-colors"
            >
              Yes
            </button>
            <button
              @click.stop="cancelDelete"
              class="text-[10px] px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
            >
              Cancel
            </button>
          </div>

          <!-- Rename Input -->
          <div v-else-if="editingId === session.id" class="flex items-center gap-2 py-1">
            <input
              v-model="editTitle"
              @keydown="handleKeyDown($event, session.id)"
              @blur="saveRename(session.id)"
              class="flex-1 bg-slate-950 text-white text-xs px-2 py-1 rounded border border-slate-700 focus:border-indigo-500 focus:outline-none"
              maxlength="200"
            />
          </div>

          <!-- Normal Display -->
          <div v-else class="flex items-center justify-between">
            <span class="truncate max-w-[170px] text-xs font-semibold">
              {{ session.title || 'New Chat' }}
            </span>
            <div class="flex items-center gap-1">
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
              <!-- Three-dot menu button -->
              <button
                @click="toggleMenu(session.id, $event)"
                class="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-all"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="5" r="2" />
                  <circle cx="12" cy="12" r="2" />
                  <circle cx="12" cy="19" r="2" />
                </svg>
              </button>
            </div>
          </div>

          <!-- Date -->
          <span v-if="showDeleteConfirm !== session.id && editingId !== session.id" class="text-[10px] text-slate-500">
            {{ new Date(session.created_at).toLocaleDateString() }}
          </span>
        </button>

        <!-- Dropdown Menu -->
        <div
          v-if="menuOpenId === session.id"
          @click.stop
          class="absolute right-2 top-10 z-10 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 min-w-[100px]"
        >
          <button
            @click="startRename(session.id, session.title)"
            class="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
          >
            Rename
          </button>
          <button
            @click="confirmDelete(session.id)"
            class="w-full text-left px-3 py-1.5 text-xs text-rose-400 hover:bg-slate-700 hover:text-rose-300 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
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
