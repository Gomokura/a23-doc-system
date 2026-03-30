<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

interface FileRecord {
  filename: string
  status: string
  page_count: number
  file_id: string
}

const files = ref<FileRecord[]>([])
const health = ref<any>(null)
const loading = ref(false)

const handleRefresh = async () => {
  loading.value = true

  try {
    const filesResponse = await fetch('http://localhost:8000/files')
    const filesData = await filesResponse.json()
    files.value = filesData.files || []

    const healthResponse = await fetch('http://localhost:8000/health')
    const healthData = await healthResponse.json()
    health.value = healthData

    ElMessage.success('状态已刷新')
  } catch (error) {
    ElMessage.error('刷新失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  handleRefresh()
})
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      服务健康状态与已入库文档
    </div>

    <div>
      <button
        @click="handleRefresh"
        :disabled="loading"
        class="px-4 py-2 bg-surface text-text2 font-medium rounded-md border border-border hover:bg-surface2 disabled:opacity-50 transition-colors"
      >
        {{ loading ? '刷新中...' : '刷新状态' }}
      </button>
    </div>

    <div v-if="health" class="grid grid-cols-3 gap-4">
      <div class="bg-white border border-border rounded-lg p-5 text-center">
        <div class="text-3xl font-bold text-accent">{{ files.length }}</div>
        <div class="text-xs text-muted mt-1">已入库文档</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-5 text-center">
        <div class="text-3xl font-bold text-accent">{{ health.avg_response_ms || '—' }}<span class="text-base">ms</span></div>
        <div class="text-xs text-muted mt-1">平均响应</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-5 text-center">
        <div class="text-2xl font-bold" :class="health.status === 'ok' ? 'text-green' : 'text-red'">
          {{ health.status === 'ok' ? '正常' : '异常' }}
        </div>
        <div class="text-xs text-muted mt-1">{{ health.status }}</div>
      </div>
    </div>

    <div>
      <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
        已入库文档列表
      </div>
      <div class="bg-white border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-surface2 border-b border-border">
              <th class="px-4 py-3 text-left font-semibold text-text2">文件名</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">状态</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">页数</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">File ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in files" :key="file.file_id" class="border-b border-border-l hover:bg-surface2">
              <td class="px-4 py-3 text-text">{{ file.filename }}</td>
              <td class="px-4 py-3">
                <span
                  :class="[
                    'px-2 py-1 rounded text-xs font-medium',
                    file.status === 'indexed'
                      ? 'bg-green/10 text-green'
                      : file.status === 'parsed'
                      ? 'bg-accent/10 text-accent'
                      : 'bg-muted/10 text-muted'
                  ]"
                >
                  {{ file.status }}
                </span>
              </td>
              <td class="px-4 py-3 text-text">{{ file.page_count }}</td>
              <td class="px-4 py-3 text-text2 font-mono text-xs">{{ file.file_id }}</td>
            </tr>
            <tr v-if="files.length === 0">
              <td colspan="4" class="px-4 py-8 text-center text-muted">暂无文档</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
