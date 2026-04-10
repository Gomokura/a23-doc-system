<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Props {
  modelValue: number
}

interface Emits {
  (e: 'update:modelValue', value: number): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

const navItems = [
  { icon: '📤', label: '文档上传', id: 0 },
  { icon: '💬', label: '智能问答', id: 1 },
  { icon: '📋', label: '表格回填', id: 2 },
  { icon: '🖥️', label: '文档操作', id: 4 },
  { icon: '🔧', label: '系统状态', id: 3 },
]

const handleNav = (id: number) => {
  emit('update:modelValue', id)
}

// 动态检测后端连接状态
const backendOk = ref(false)
let healthTimer: ReturnType<typeof setInterval> | null = null

async function checkHealth() {
  try {
    const res = await fetch('/api/health', { signal: AbortSignal.timeout(3000) })
    backendOk.value = res.ok
  } catch {
    backendOk.value = false
  }
}

onMounted(() => {
  checkHealth()
  healthTimer = setInterval(checkHealth, 15000)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
})
</script>

<template>
  <aside class="w-52 bg-white border-r border-border flex flex-col h-full">
    <div class="flex-1 overflow-y-auto">
      <div class="px-4 py-4">
        <div class="text-xs font-bold tracking-widest text-muted uppercase mb-2">主菜单</div>
        <div class="space-y-1">
          <button
            v-for="item in navItems"
            :key="item.id"
            @click="handleNav(item.id)"
            :class="[
              'w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-all duration-100',
              modelValue === item.id
                ? 'bg-accent-bg text-accent font-medium'
                : 'bg-transparent text-text2 font-normal hover:bg-surface2'
            ]"
          >
            <span class="text-base w-4.5 text-center">{{ item.icon }}</span>
            <span class="flex-1">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </div>
    <div class="border-t border-border-l mx-2"></div>
    <div class="px-4 py-3 text-xs text-muted">
      <div class="flex justify-between items-center mb-1">
        <span>后端状态</span>
        <span :class="backendOk ? 'text-green font-semibold' : 'text-red font-semibold'">
          {{ backendOk ? '已连接' : '未连接' }}
        </span>
      </div>
      <div class="text-border-l text-xs break-all">http://localhost:8000</div>
    </div>
  </aside>
</template>

<style scoped>
</style>
