<script setup lang="ts">
import Upload from '@/pages/Upload.vue'
import Query from '@/pages/Query.vue'
import Fill from '@/pages/Fill.vue'
import Operate from '@/pages/Operate.vue'
import Status from '@/pages/Status.vue'

interface Props {
  tab: number
}

defineProps<Props>()

const pageByTab: Record<number, unknown> = {
  0: Upload,
  1: Query,
  2: Fill,
  3: Status,
  4: Operate,
}
</script>

<template>
  <main class="flex-1 bg-bg overflow-y-auto">
    <div class="p-6">
      <keep-alive>
        <component :is="pageByTab[tab] ?? Upload" :key="tab" />
      </keep-alive>
    </div>
  </main>
</template>

<style scoped>
</style>
