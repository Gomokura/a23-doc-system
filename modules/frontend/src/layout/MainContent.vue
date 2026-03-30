<script setup lang="ts">
import Upload from '@/pages/Upload.vue'
import Query from '@/pages/Query.vue'
import Fill from '@/pages/Fill.vue'
import Status from '@/pages/Status.vue'

interface Props {
  tab: number
}

defineProps<Props>()

const pages = [Upload, Query, Fill, Status]
</script>

<template>
  <main class="flex-1 bg-bg overflow-y-auto">
    <div class="p-6">
      <component :is="pages[tab]" />
    </div>
  </main>
</template>

<style scoped>
</style>
