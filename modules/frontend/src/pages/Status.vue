<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

interface FileRecord {
  filename: string
  status: string
  page_count: number
  file_id: string
}

interface RAGASMetrics {
  retrieval: {
    recall: number
    precision: number
    mrr: number
  }
  context: {
    relevance: number
    accuracy: number
    coverage: number
  }
  generation: {
    faithfulness: number
    relevance: number
    completeness: number
  }
  performance: {
    avg_response_ms: number
    p95_response_ms: number
    throughput: number
  }
}

const files = ref<FileRecord[]>([])
const health = ref<any>(null)
const loading = ref(false)
const ragasMetrics = ref<RAGASMetrics>({
  retrieval: { recall: 85, precision: 92, mrr: 0.88 },
  context: { relevance: 89, accuracy: 91, coverage: 87 },
  generation: { faithfulness: 94, relevance: 96, completeness: 88 },
  performance: { avg_response_ms: 1200, p95_response_ms: 2100, throughput: 45 }
})

// 进度条颜色
const getMetricColor = (value: number) => {
  if (value >= 90) return 'bg-green'
  if (value >= 80) return 'bg-accent'
  if (value >= 70) return 'bg-yellow-500'
  return 'bg-red'
}

// 进度条宽度
const getMetricWidth = (value: number) => {
  return `${Math.min(value, 100)}%`
}

const handleRefresh = async () => {
  loading.value = true

  try {
    const filesResponse = await fetch('/api/files')
    const filesData = await filesResponse.json()
    files.value = filesData.files || []

    const healthResponse = await fetch('/api/health')
    const healthData = await healthResponse.json()
    health.value = healthData

    // TODO: 后端提供 RAGAS 指标时，替换 mock 数据
    // const ragasResponse = await fetch('http://localhost:8000/metrics/ragas')
    // const ragasData = await ragasResponse.json()
    // ragasMetrics.value = ragasData

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
      RAG 系统评测仪表盘
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

    <!-- RAGAS 指标仪表盘 -->
    <div class="grid grid-cols-2 gap-6">
      <!-- 检索质量 -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-lg">🔍</span>
          <h3 class="text-sm font-bold text-text">检索质量</h3>
        </div>
        <div class="space-y-4">
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">召回率 (Recall)</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.retrieval.recall }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.retrieval.recall)"
                :style="{ width: getMetricWidth(ragasMetrics.retrieval.recall) }"
              ></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">精准率 (Precision)</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.retrieval.precision }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.retrieval.precision)"
                :style="{ width: getMetricWidth(ragasMetrics.retrieval.precision) }"
              ></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">MRR (Mean Reciprocal Rank)</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.retrieval.mrr.toFixed(2) }}</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.retrieval.mrr * 100)"
                :style="{ width: getMetricWidth(ragasMetrics.retrieval.mrr * 100) }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 上下文利用 -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-lg">📝</span>
          <h3 class="text-sm font-bold text-text">上下文利用</h3>
        </div>
        <div class="space-y-4">
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">上下文相关性</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.context.relevance }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.context.relevance)"
                :style="{ width: getMetricWidth(ragasMetrics.context.relevance) }"
              ></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">上下文精准性</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.context.accuracy }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.context.accuracy)"
                :style="{ width: getMetricWidth(ragasMetrics.context.accuracy) }"
              ></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">上下文覆盖率</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.context.coverage }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.context.coverage)"
                :style="{ width: getMetricWidth(ragasMetrics.context.coverage) }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 生成质量 -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-lg">🎯</span>
          <h3 class="text-sm font-bold text-text">生成质量</h3>
        </div>
        <div class="space-y-4">
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">答案忠实度</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.generation.faithfulness }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.generation.faithfulness)"
                :style="{ width: getMetricWidth(ragasMetrics.generation.faithfulness) }"
              ></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">答案相关性</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.generation.relevance }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.generation.relevance)"
                :style="{ width: getMetricWidth(ragasMetrics.generation.relevance) }"
              ></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">答案完整性</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.generation.completeness }}%</span>
            </div>
            <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="getMetricColor(ragasMetrics.generation.completeness)"
                :style="{ width: getMetricWidth(ragasMetrics.generation.completeness) }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 性能指标 -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-lg">⏱️</span>
          <h3 class="text-sm font-bold text-text">性能指标</h3>
        </div>
        <div class="space-y-4">
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">平均响应时间</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.performance.avg_response_ms }}ms</span>
            </div>
            <div class="text-xs text-muted">越低越好</div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">P95 响应时间</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.performance.p95_response_ms }}ms</span>
            </div>
            <div class="text-xs text-muted">95% 请求在此时间内完成</div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-text2">吞吐量</span>
              <span class="text-sm font-semibold text-accent">{{ ragasMetrics.performance.throughput }} req/min</span>
            </div>
            <div class="text-xs text-muted">每分钟请求数</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 基础统计 -->
    <div v-if="health" class="grid grid-cols-3 gap-4">
      <div class="bg-white border border-border rounded-lg p-5 text-center">
        <div class="text-3xl font-bold text-accent">{{ files.length }}</div>
        <div class="text-xs text-muted mt-1">已入库文档</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-5 text-center">
        <div class="text-3xl font-bold text-accent">{{ health.database?.ok ? 'OK' : 'FAIL' }}</div>
        <div class="text-xs text-muted mt-1">数据库</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-5 text-center">
        <div class="text-2xl font-bold" :class="health.status === 'ok' ? 'text-green' : 'text-red'">
          {{ health.status === 'ok' ? '正常' : '异常' }}
        </div>
        <div class="text-xs text-muted mt-1">{{ health.status }}</div>
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
              <td class="px-4 py-3 text-text">{{ file.chunk_count || 0 }} 块</td>
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
