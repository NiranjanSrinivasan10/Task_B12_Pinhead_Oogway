<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()
</script>

<template>
  <aside class="w-80 lg:w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-full shrink-0">
    <div class="p-4 border-b border-slate-800 flex items-center justify-between">
      <h2 class="font-semibold text-sm text-slate-200 flex items-center gap-2">
        <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        Artifact Panel
      </h2>
      <span class="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
        Phase 7 Preview
      </span>
    </div>

    <div class="flex-1 overflow-y-auto p-4 flex flex-col items-center justify-center text-center">
      <div v-if="!store.activeArtifact" class="space-y-3">
        <div class="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <div class="text-xs text-slate-400">
          <p class="font-medium text-slate-300">No active artifact</p>
          <p class="mt-1 text-slate-500">Generated essays, framework guides, and structured documents will appear here.</p>
        </div>
      </div>

      <div v-else class="w-full text-left space-y-3">
        <div class="p-3 rounded-lg bg-slate-800 border border-slate-700">
          <div class="text-xs text-indigo-400 font-mono uppercase tracking-wider mb-1">
            {{ store.activeArtifact.type }}
          </div>
          <h3 class="font-bold text-slate-100 text-sm mb-2">
            {{ store.activeArtifact.title }}
          </h3>
          <div class="text-xs text-slate-300 whitespace-pre-wrap max-h-[70vh] overflow-y-auto font-mono bg-slate-950 p-3 rounded border border-slate-850">
            {{ store.activeArtifact.content }}
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
