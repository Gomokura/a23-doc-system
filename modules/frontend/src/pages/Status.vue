<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { parseResponseJson } from '@/utils/parseApiResponse'

interface FileRecord {
  filename: string
  status: string
  file_size: number
  chunk_count: number
  file_id: string
  file_type: string
}

const files = ref<FileRecord[]>([])
const health = ref<any>(null)
const loading = ref(false)

// 实际测量的后端响应时间（ms）
const measuredResponseMs = ref<number | null>(null)

// ── 从文件列表动态计算的统计数据 ────────────────────────────
const indexedFiles = computed(() => files.value.filter(f => f.status === 'indexed'))
const totalChunks  = computed(() => files.value.reduce((s, f) => s + (f.chunk_count || 0), 0))
const totalSize    = computed(() => files.value.reduce((s, f) => s + (f.file_size || 0), 0))

// 格式分布
const formatDist = computed(() => {
  const dist: Record<string, number> = {}
  for (const f of files.value) {
    const ext = f.filename.split('.').pop()?.toUpperCase() || 'OTHER'
    dist[ext] = (dist[ext] || 0) + 1
  }
  return Object.entries(dist).sort((a, b) => b[1] - a[1])
})

const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// ── 响应时间着色 ─────────────────────────────────────────────
const responseTimeColor = computed(() => {
  const ms = measuredResponseMs.value
  if (ms === null) return 'text-muted'
  if (ms < 500)  return 'text-green'
  if (ms < 1500) return 'text-accent'
  if (ms < 3000) return 'text-yellow-500'
  return 'text-red'
})

const handleRefresh = async () => {
  loading.value = true
  try {
    // 同时请求文件列表和健康检查，并测量健康检查耗时
    const t0 = Date.now()
    const [filesResponse, healthResponse] = await Promise.all([
      fetch('/api/files'),
      fetch('/api/health'),
    ])
    measuredResponseMs.value = Date.now() - t0

    const filesData = (await parseResponseJson(filesResponse)) as { files?: FileRecord[] }
    if (!filesResponse.ok) throw new Error((filesData as any).detail || '获取文件列表失败')
    files.value = filesData.files || []

    const healthData = (await parseResponseJson(healthResponse)) as Record<string, unknown>
    // health 接口 503 时也把数据存下来，方便展示 degraded 状态
    health.value = healthData

    ElMessage.success('状态已刷新')
  } catch (error: any) {
    ElMessage.error(error?.message || '刷新失败')
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
      系统状态仪表盘
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

    <!-- 第一行：知识库统计 + 系统性能 -->
    <div class="grid grid-cols-2 gap-6">

      <!-- 知识库统计（全部真实数据） -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-lg">📚</span>
          <h3 class="text-sm font-bold text-text">知识库统计</h3>
        </div>
        <div class="space-y-4">
          <!-- 已入库文档 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">已入库文档</span>
            <span class="text-sm font-semibold text-accent">{{ indexedFiles.length }} 个</span>
          </div>
          <!-- 总文本块 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">总文本块数</span>
            <span class="text-sm font-semibold text-accent">{{ totalChunks }} 块</span>
          </div>
          <!-- 总大小 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">知识库总大小</span>
            <span class="text-sm font-semibold text-accent">{{ formatSize(totalSize) }}</span>
          </div>
          <!-- 格式分布 -->
          <div>
            <div class="text-xs text-text2 mb-2">文档格式分布</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="[ext, count] in formatDist"
                :key="ext"
                class="px-2 py-0.5 bg-accent/10 text-accent text-xs rounded font-mono"
              >
                {{ ext }} × {{ count }}
              </span>
              <span v-if="formatDist.length === 0" class="text-xs text-muted">暂无文档</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 系统性能（真实测量） -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-lg">⚡</span>
          <h3 class="text-sm font-bold text-text">系统性能</h3>
        </div>
        <div class="space-y-4">
          <!-- 后端响应时间（实测） -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">后端响应时间（实测）</span>
            <span
              class="text-sm font-semibold"
              :class="responseTimeColor"
            >
              {{ measuredResponseMs !== null ? measuredResponseMs + ' ms' : '—' }}
            </span>
          </div>
          <!-- 数据库状态 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">数据库状态</span>
            <span
              class="text-sm font-semibold"
              :class="health?.database?.ok ? 'text-green' : 'text-red'"
            >
              {{ health === null ? '—' : health?.database?.ok ? '正常' : '异常' }}
            </span>
          </div>
          <!-- 服务状态 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">服务状态</span>
            <span
              class="text-sm font-semibold"
              :class="health?.status === 'ok' ? 'text-green' : health === null ? 'text-muted' : 'text-red'"
            >
              {{ health === null ? '—' : health?.status === 'ok' ? '正常运行' : '服务降级' }}
            </span>
          </div>
          <!-- 服务版本 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">服务版本</span>
            <span class="text-sm font-semibold text-text2 font-mono">
              {{ health?.version ?? '—' }}
            </span>
          </div>
          <!-- 最后检查时间 -->
          <div class="flex justify-between items-center">
            <span class="text-xs text-text2">最后检查时间</span>
            <span class="text-xs text-muted">
              {{
                health?.timestamp
                  ? new Date(health.timestamp).toLocaleTimeString('zh-CN')
                  : '—'
              }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 已入库文档列表 -->
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
              <th class="px-4 py-3 text-left font-semibold text-text2">文本块</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">大小</th>
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
                    file.status === 'indexed' ? 'bg-green/10 text-green'
                      : file.status === 'parsed' ? 'bg-accent/10 text-accent'
                      : file.status === 'failed' ? 'bg-red/10 text-red'
                      : 'bg-muted/10 text-muted'
                  ]"
                >
                  {{
                    file.status === 'indexed' ? '✓ 已入库'
                    : file.status === 'parsed' ? '⏳ 已解析'
                    : file.status === 'uploaded' ? '↑ 已上传'
                    : file.status === 'failed' ? '✕ 失败'
                    : file.status
                  }}
                </span>
              </td>
              <td class="px-4 py-3 text-text2">{{ file.chunk_count || 0 }} 块</td>
              <td class="px-4 py-3 text-text2">{{ formatSize(file.file_size || 0) }}</td>
              <td class="px-4 py-3 text-text2 font-mono text-xs">{{ file.file_id }}</td>
            </tr>
            <tr v-if="files.length === 0">
              <td colspan="5" class="px-4 py-8 text-center text-muted">暂无文档</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
