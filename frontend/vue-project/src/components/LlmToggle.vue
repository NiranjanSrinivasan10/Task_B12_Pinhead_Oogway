<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const selectedOption = computed({
  get() {
    const provider = store.activeProvider
    const model = store.activeModel
    return `${provider}:${model}`
  },
  set(val: string) {
    const colonIndex = val.indexOf(':')
    const provider = val.slice(0, colonIndex)
    const model = val.slice(colonIndex + 1)
    store.updateConfig(provider as any, model || 'gpt-4o-mini')
  }
})

const isOllamaDown = computed(() => {
  return store.activeProvider === 'ollama' && store.health && !store.health.ollama
})
</script>

<template>
  <div class="flex items-center gap-3 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800 shadow-sm">
    <div class="flex items-center gap-2">
      <span class="text-xs text-slate-400 font-medium hidden sm:inline">Model:</span>
      <select
        v-model="selectedOption"
        class="bg-slate-800 text-slate-100 text-xs rounded-lg px-2.5 py-1.5 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium cursor-pointer"
      >
        <option value="openai:gpt-4o-mini">Cloud — GPT-4o-mini (OpenAI)</option>
        <option value="ollama:llama3.1:8b">Local — Llama 3.1 8B (Ollama)</option>
        <option value="ollama:phi4-mini:3.8b">Local — Phi 4 Mini 3.8B (Ollama)</option>
        <option value="anthropic:claude-3-5-sonnet-20241022">Cloud — Claude 3.5 Sonnet (Anthropic)</option>
      </select>
    </div>

    <!-- Provider badge indicator -->
    <span
      v-if="store.activeProvider === 'ollama'"
      :class="[
        'text-[11px] px-2 py-0.5 rounded-full font-medium flex items-center gap-1',
        isOllamaDown ? 'bg-amber-950/80 text-amber-300 border border-amber-800' : 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
      ]"
    >
      <span :class="['w-1.5 h-1.5 rounded-full', isOllamaDown ? 'bg-amber-400' : 'bg-emerald-400']"></span>
      {{ isOllamaDown ? 'Ollama Offline' : 'Local Instance' }}
    </span>
    <span
      v-else
      class="text-[11px] px-2 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-800 font-medium flex items-center gap-1"
    >
      <span class="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
      Cloud API
    </span>
  </div>
</template>
