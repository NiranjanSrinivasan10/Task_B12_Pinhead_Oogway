<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()
const activeTab = ref<'preview' | 'code'>('preview')
const copied = ref(false)

// Configure marked options for GFM support
marked.setOptions({
  gfm: true,
  breaks: true,
})

const renderedMarkdown = computed(() => {
  if (!store.activeArtifact || store.activeArtifact.type !== 'markdown') return ''
  try {
    return marked.parse(store.activeArtifact.content || '')
  } catch (err) {
    return `<p class="text-rose-400">Failed to render markdown: ${err}</p>`
  }
})

const iframeSrcdoc = computed(() => {
  if (!store.activeArtifact || store.activeArtifact.type !== 'html') return ''
  const rawHtml = store.activeArtifact.content || ''
  // Wrap with fallback styling if full <html> document is missing
  if (rawHtml.includes('<html') || rawHtml.includes('<!DOCTYPE')) {
    return rawHtml
  }
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 1.5rem; color: #1e293b; background: #ffffff; line-height: 1.6; }
    pre { background: #f8fafc; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
    code { font-family: monospace; }
  </style>
</head>
<body>
  ${rawHtml}
</body>
</html>`
})

function handleDownload() {
  if (!store.activeArtifact) return
  const ext = store.activeArtifact.type === 'html' ? 'html' : 'md'
  const title = store.activeArtifact.title || 'artifact'
  const filename = `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.${ext}`
  
  const blob = new Blob([store.activeArtifact.content], {
    type: ext === 'html' ? 'text/html;charset=utf-8' : 'text/markdown;charset=utf-8'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function handleCopy() {
  if (!store.activeArtifact) return
  navigator.clipboard.writeText(store.activeArtifact.content)
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 2000)
}
</script>

<template>
  <aside
    v-if="store.isArtifactPanelOpen"
    class="w-96 lg:w-[480px] bg-slate-900 border-l border-slate-800 flex flex-col h-full shrink-0 shadow-2xl z-20 transition-all duration-200"
  >
    <!-- Top Header: Title + Collapse + Multi-artifact Switcher -->
    <div class="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
      <div class="flex items-center gap-2 min-w-0">
        <span class="p-1.5 rounded-lg bg-indigo-950 text-indigo-400 border border-indigo-800 shrink-0">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </span>
        <div class="min-w-0">
          <h2 class="font-bold text-xs text-slate-200 truncate">
            {{ store.activeArtifact?.title || 'Artifact Viewer' }}
          </h2>
          <p class="text-[10px] text-slate-500 font-mono">
            {{ store.activeArtifact?.type ? store.activeArtifact.type.toUpperCase() : 'NO ARTIFACT' }}
          </p>
        </div>
      </div>

      <!-- Actions: Download & Collapse -->
      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="store.activeArtifact"
          @click="handleDownload"
          title="Download artifact file"
          class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs flex items-center gap-1 font-medium px-2"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export
        </button>

        <button
          @click="store.toggleArtifactPanel"
          title="Collapse panel"
          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Multi-Artifact Selection Bar (if any artifacts exist) -->
    <div v-if="store.artifacts.length > 0" class="px-3 py-2 border-b border-slate-800 bg-slate-900 flex items-center gap-2 overflow-x-auto text-xs">
      <span class="text-[10px] text-slate-400 uppercase font-mono shrink-0">Artifacts:</span>
      <button
        v-for="art in store.artifacts"
        :key="art.id"
        @click="store.selectArtifact(art.id)"
        :class="[
          'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium truncate max-w-[140px] transition-all shrink-0',
          store.activeArtifact?.id === art.id
            ? 'bg-indigo-600 text-white shadow-sm'
            : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
        ]"
      >
        <!-- Type icon -->
        <svg v-if="art.type === 'html'" class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
        <svg v-else class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span class="truncate">{{ art.title }}</span>
      </button>
    </div>

    <!-- Sub-header: Tabs (Preview vs Code) -->
    <div v-if="store.activeArtifact" class="px-3 py-2 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
      <div class="flex items-center gap-1 bg-slate-800 p-0.5 rounded-lg border border-slate-700">
        <button
          @click="activeTab = 'preview'"
          :class="[
            'px-3 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1.5',
            activeTab === 'preview'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          ]"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Preview
        </button>
        <button
          @click="activeTab = 'code'"
          :class="[
            'px-3 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1.5',
            activeTab === 'code'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          ]"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          Code
        </button>
      </div>

      <button
        @click="handleCopy"
        class="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 transition-colors"
      >
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        {{ copied ? 'Copied!' : 'Copy Raw' }}
      </button>
    </div>

    <!-- Main Content Panel -->
    <div class="flex-1 overflow-y-auto p-4 relative">
      <!-- Empty State -->
      <div v-if="!store.activeArtifact" class="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-3">
        <div class="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center text-slate-400">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <p class="text-xs font-medium text-slate-400">No active artifact selected.</p>
        <p class="text-[11px] text-slate-500 max-w-xs leading-relaxed">
          Ask the assistant to generate an essay, markdown guide, or HTML component to view it rendered here live.
        </p>
      </div>

      <template v-else>
        <!-- PREVIEW TAB -->
        <div v-if="activeTab === 'preview'" class="h-full">
          <!-- Markdown Render -->
          <div
            v-if="store.activeArtifact.type === 'markdown'"
            class="markdown-body text-slate-200 text-sm leading-relaxed space-y-4 max-w-none font-sans"
            v-html="renderedMarkdown"
          ></div>

          <!-- HTML Sandboxed iframe Render -->
          <div v-else-if="store.activeArtifact.type === 'html'" class="h-full w-full rounded-lg overflow-hidden border border-slate-800 bg-white shadow-inner">
            <iframe
              :srcdoc="iframeSrcdoc"
              sandbox="allow-scripts"
              class="w-full h-full border-0 min-h-[400px]"
              title="Artifact HTML Sandbox Preview"
            ></iframe>
          </div>
        </div>

        <!-- CODE TAB -->
        <div v-else class="h-full">
          <pre class="bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto whitespace-pre-wrap leading-relaxed"><code>{{ store.activeArtifact.content }}</code></pre>
        </div>
      </template>
    </div>
  </aside>
</template>

<style>
/* Custom Markdown styling for rendered preview */
/* Type scale: 3 clear steps at ~1.25 ratio — fixes [flat-type-hierarchy] */
.markdown-body h1 {
  font-size: 1.5rem;     /* step 3 */
  font-weight: 700;
  color: #f8fafc;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 0.5rem;
  letter-spacing: -0.01em;
}
.markdown-body h2 {
  font-size: 1.25rem;    /* step 2 */
  font-weight: 600;
  color: #e2e8f0;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  letter-spacing: -0.01em;
}
.markdown-body h3 {
  font-size: 1rem;       /* step 1 — same as body, distinguished by weight */
  font-weight: 700;
  color: #cbd5e1;
  margin-top: 1rem;
  margin-bottom: 0.25rem;
}
.markdown-body p {
  margin-bottom: 0.75rem;
  color: #cbd5e1;
}
.markdown-body ul {
  list-style-type: disc;
  padding-left: 1.25rem;
  margin-bottom: 0.75rem;
}
.markdown-body ol {
  list-style-type: decimal;
  padding-left: 1.25rem;
  margin-bottom: 0.75rem;
}
.markdown-body li {
  margin-bottom: 0.25rem;
}
/* [side-tab] fix: background treatment instead of thick accent border */
.markdown-body blockquote {
  background-color: #111827;
  border-radius: 0.375rem;
  padding: 0.6rem 1rem;
  color: #94a3b8;
  font-style: italic;
  margin-bottom: 0.75rem;
}
.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
  font-size: 0.8rem;     /* base step */
}
.markdown-body th, .markdown-body td {
  border: 1px solid #1e293b;
  padding: 0.5rem 0.75rem;
  text-align: left;
}
.markdown-body th {
  background-color: #0f172a;
  color: #e2e8f0;
  font-weight: 600;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.markdown-body code {
  font-family: ui-monospace, 'Cascadia Code', monospace;
  background-color: #1e293b;
  color: #a5b4fc;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.8rem;     /* matches base step */
}
.markdown-body pre code {
  display: block;
  padding: 0.75rem;
  background-color: #0f172a;
  border-radius: 0.5rem;
  overflow-x: auto;
}
</style>
