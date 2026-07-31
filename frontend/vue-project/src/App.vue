<script setup lang="ts">
import { onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPane from '@/components/ChatPane.vue'
import ArtifactViewer from '@/components/ArtifactViewer.vue'

const store = useSessionStore()

onMounted(() => {
  store.checkHealth()
  store.fetchSessions()
})
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 antialiased">
    <!-- Left Sidebar -->
    <SessionSidebar />

    <!-- Main Chat Pane -->
    <ChatPane />

    <!-- Right Artifact Panel Placeholder -->
    <ArtifactViewer />
  </div>
</template>
