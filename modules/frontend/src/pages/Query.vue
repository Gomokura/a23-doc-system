<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, onActivated } from 'vue'
import { ElMessage } from 'element-plus'
import { parseResponseJson } from '@/utils/parseApiResponse'
import { useQueryStore } from '@/stores/query'
import type { QueryResult } from '@/stores/query'

const store = useQueryStore()

// ── 本地 UI 状态（不需要跨 tab 保留） ────────────────────────
const loading = ref(false)
const expandedSources = ref<Set<number>>(new Set())

// ── 从 store 读写的状态（切 tab 后保留） ─────────────────────
const query = computed({
  get: () => store.lastQuery,
  set: (v) => store.setQuery(v),
})

const fileIds = computed({
  get: () => store.selectedFileIds,
  set: (v) => store.setSelectedFileIds(v),
})

const result = computed(() => store.lastResult)
const filesList = computed(() => store.filesList)

const toggleSource = (index: number) => {
  if (expandedSources.value.has(index)) {
    expandedSources.value.delete(index)
  } else {
    expandedSources.value.add(index)
  }
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 70) return 'text-green'
  if (confidence >= 50) return 'text-accent'
  if (confidence >= 30) return 'text-yellow-500'
  return 'text-red'
}

const getRelevanceColor = (relevance: number) => {
  if (relevance >= 70) return 'bg-green/10 text-green'
  if (relevance >= 50) return 'bg-accent/10 text-accent'
  if (relevance >= 30) return 'bg-yellow-500/10 text-yellow-600'
  return 'bg-red/10 text-red'
}

/** 本批检索片段的 RRF 分绝对值小，映射为片段之间的相对「相关度」百分数，避免无 score 时误显示 80% */
function relativeRelevancePercents(raw: number[]): number[] {
  if (!raw.length) return []
  const lo = Math.min(...raw)
  const hi = Math.max(...raw)
  const den = hi - lo
  if (den < 1e-12) {
    const mid = Math.min(88, Math.max(32, Math.round(lo * 1600)))
    return raw.map(() => mid)
  }
  return raw.map(v => Math.round(36 + ((v - lo) / den) * 58))
}

// 关键词高亮
const escapeHtml = (str: string): string =>
  str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const highlightContent = (content: string, queryText: string): string => {
  if (!queryText || !content) return escapeHtml(content)
  const words = queryText.trim().split(/\s+/).filter(w => w.length > 1)
  let highlighted = escapeHtml(content)
  for (const word of words) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    highlighted = highlighted.replace(
      new RegExp(escaped, 'gi'),
      match => `<mark class="bg-yellow-200 rounded px-0.5">${match}</mark>`
    )
  }
  return highlighted
}

const handleQuery = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  loading.value = true
  expandedSources.value.clear()
  store.clearResult()

  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query.value,
        file_ids: fileIds.value,
      }),
    })

    const data = (await parseResponseJson(response)) as Record<string, any>
    if (!response.ok) {
      throw new Error(data.detail || data.message || `查询失败 (${response.status})`)
    }

    const sourcesRaw = data.sources || []
    const rawScores = sourcesRaw.map((s: any) => Number(s.score ?? s.hybrid_score ?? 0))
    const relPercents = relativeRelevancePercents(rawScores)

    const confidence = typeof data.confidence === 'number' && data.confidence >= 0
      ? Math.round(data.confidence * 100)
      : 0

    const hasConflicts = data.fusion?.has_conflicts || false
    const conflictCount = data.fusion?.conflict_count || 0
    const conflictDetails = data.fusion?.conflict_details || []

    const seenFiles = new Set<string>()
    const uniqueSources = sourcesRaw
      .map((s: any, i: number) => ({
        s,
        rel: relPercents[i] ?? 0,
        fn: extractFilename(s.source_file || s.filename || ''),
      }))
      .filter(({ fn }) => {
        if (seenFiles.has(fn)) return false
        seenFiles.add(fn)
        return true
      })
      .map(({ s, rel, fn }) => ({
        filename: fn,
        page: s.page || 0,
        content: s.content || '',
        relevance: rel,
        confidence,
      }))

    store.setResult({
      answer: data.answer || '无法生成答案',
      confidence,
      hasConflicts,
      conflictCount,
      conflictDetails,
      sources: uniqueSources,
      explanation: {
        why: hasConflicts
          ? `检测到 ${conflictCount} 处信息冲突，系统已融合多源信息给出答案`
          : '基于检索到的文档片段生成答案，相关度高',
        alternatives: hasConflicts
          ? conflictDetails.map((c: any) => c.description || c.field || c.key).filter(Boolean).join('；') || '存在多源冲突'
          : '未发现明显冲突信息',
        credibility: confidence >= 70
          ? '答案置信度高，来源可靠'
          : '答案仅供参考，建议进一步核实',
      },
    })
    ElMessage.success('查询成功')
  } catch (error: any) {
    ElMessage.error(error.message || '查询失败')
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  try {
    const response = await fetch('/api/files')
    const data = (await parseResponseJson(response)) as { files?: any[] }
    if (!response.ok) {
      ElMessage.error((data as any).detail || `刷新文件列表失败 (${response.status})`)
      return
    }
    store.setFilesList((data.files || []).filter((f: any) => f.status === 'indexed'))
  } catch (e: any) {
    ElMessage.error(e?.message || '刷新文件列表失败')
  }
}

// 清除全部问答缓存
const handleClearCache = async () => {
  if (!confirm('确定清除所有问答缓存？这不影响已入库的文档。')) return
  try {
    const res = await fetch('/api/cache/clear', { method: 'POST' })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '清缓存失败')
    ElMessage.success(`已清除 ${data.cleared ?? 0} 条缓存`)
  } catch (e: any) {
    ElMessage.error(e.message || '清缓存失败')
  }
}

const toggleFile = (fileId: string) => {
  const current = [...store.selectedFileIds]
  const idx = current.indexOf(fileId)
  if (idx === -1) current.push(fileId)
  else current.splice(idx, 1)
  store.setSelectedFileIds(current)
}

const extractFilename = (path: string) => {
  if (!path) return '未知文件'
  return path.replace(/\\/g, '/').split('/').pop() || path
}

// 页面打开时加载，之后每10秒自动刷新文件列表
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  handleRefresh()
  refreshTimer = setInterval(handleRefresh, 10000)
})

onActivated(() => {
  // 每次切回问答 tab 时清空上次结果，避免误导
  store.clearResult()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      多源文档智能问答与溯源
    </div>

    <!-- 查询输入 -->
    <div class="grid grid-cols-12 gap-4">
      <div class="col-span-7">
        <label class="block text-sm font-medium text-text2 mb-2">输入您的问题</label>
        <textarea
          v-model="query"
          class="w-full h-20 px-3 py-2 bg-white border border-border rounded-md text-sm text-text resize-none focus:border-accent focus:outline-none"
          placeholder="例：合同总金额是多少？付款方式是什么？"
        ></textarea>
      </div>

      <div class="col-span-4">
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text2">限定文档（留空则全库检索）</label>
          <button @click="handleRefresh" class="text-xs text-accent hover:underline">刷新</button>
          <button @click="handleClearCache" class="text-xs text-red hover:underline">清缓存</button>
        </div>
        <div class="bg-white border border-border rounded-md divide-y divide-border max-h-32 overflow-y-auto">
          <div v-if="filesList.length === 0" class="px-3 py-2 text-xs text-muted">暂无已索引文档</div>
          <label
            v-for="f in filesList"
            :key="f.file_id"
            class="flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-surface2 transition-colors"
            :class="fileIds.includes(f.file_id) ? 'bg-accent/5' : ''"
          >
            <input
              type="checkbox"
              :value="f.file_id"
              :checked="fileIds.includes(f.file_id)"
              @change="toggleFile(f.file_id)"
              class="accent-accent w-3.5 h-3.5 flex-shrink-0"
            />
            <span class="truncate" :class="fileIds.includes(f.file_id) ? 'text-accent font-medium' : 'text-text'">
              {{ f.filename }}
            </span>
          </label>
        </div>
        <div class="mt-1 text-xs text-muted">
          已选 {{ fileIds.length }} / {{ filesList.length }} 个文档
        </div>
      </div>

      <div class="col-span-1 flex items-end">
        <button
          @click="handleQuery"
          :disabled="loading"
          class="w-full px-4 py-2 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '查询中...' : '开始问答' }}
        </button>
      </div>
    </div>

    <!-- 查询结果 -->
    <div v-if="result" class="space-y-6">

      <!-- 冲突警告横幅 -->
      <div
        v-if="result.hasConflicts"
        class="bg-yellow-50 border border-yellow-300 rounded-lg p-4 flex items-start gap-3"
      >
        <span class="text-xl flex-shrink-0">⚠️</span>
        <div>
          <div class="text-sm font-bold text-yellow-800 mb-1">
            多源信息冲突（{{ result.conflictCount }} 处）
          </div>
          <div class="text-xs text-yellow-700">
            {{ result.conflictDetails.map((c: any) => c.description || c.field || c.key).filter(Boolean).join('；') || '多个来源存在矛盾，建议人工核实' }}
          </div>
        </div>
      </div>

      <!-- 答案卡片 -->
      <div class="bg-white border border-border rounded-lg p-6">
        <div class="flex items-start justify-between mb-4">
          <div>
            <h3 class="text-sm font-bold text-text mb-1">💡 答案</h3>
            <p class="text-xs text-muted">基于多源文档的智能问答结果</p>
          </div>
          <div class="text-right">
            <div class="text-2xl font-bold" :class="getConfidenceColor(result.confidence)">
              {{ result.confidence }}%
            </div>
            <div class="text-xs text-muted">置信度</div>
          </div>
        </div>
        <div class="bg-surface2 rounded-lg p-4 text-sm text-text leading-relaxed whitespace-pre-wrap">
          {{ result.answer }}
        </div>
      </div>

      <!-- 证据来源 -->
      <div>
        <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
          📄 证据来源（{{ result.sources.length }} 个）
        </div>
        <div class="space-y-3">
          <div
            v-for="(source, index) in result.sources"
            :key="index"
            class="bg-white border border-border rounded-lg overflow-hidden hover:border-accent transition-colors"
          >
            <!-- 证据头部 -->
            <div
              @click="toggleSource(index)"
              class="p-4 cursor-pointer hover:bg-surface2 transition-colors flex items-center justify-between"
            >
              <div class="flex-1">
                <div class="flex items-center gap-3 mb-2">
                  <span class="font-medium text-text">{{ source.filename }}</span>
                  <span class="text-xs px-2 py-1 rounded" :class="getRelevanceColor(source.relevance)">
                    相关度 {{ source.relevance }}%
                  </span>
                </div>
                <div class="text-xs text-muted">第 {{ source.page }} 页</div>
              </div>
              <div class="text-lg">
                {{ expandedSources.has(index) ? '▼' : '▶' }}
              </div>
            </div>

            <!-- 证据内容（展开时显示，含关键词高亮） -->
            <div v-if="expandedSources.has(index)" class="border-t border-border-l bg-surface2 p-4 space-y-3">
              <div>
                <div class="text-xs font-semibold text-text2 mb-2">原文内容（关键词已高亮）</div>
                <div
                  class="bg-white border border-border rounded p-3 text-sm text-text leading-relaxed"
                  v-html="highlightContent(source.content, query)"
                ></div>
              </div>

              <div class="grid grid-cols-3 gap-3">
                <div class="bg-white border border-border rounded p-3">
                  <div class="text-xs text-muted mb-1">相关度</div>
                  <div class="text-lg font-bold text-accent">{{ source.relevance }}%</div>
                </div>
                <div class="bg-white border border-border rounded p-3">
                  <div class="text-xs text-muted mb-1">置信度</div>
                  <div class="text-lg font-bold text-accent">{{ source.confidence }}%</div>
                </div>
                <div class="bg-white border border-border rounded p-3">
                  <div class="text-xs text-muted mb-1">来源文件</div>
                  <div class="text-sm font-medium text-text truncate" :title="source.filename">{{ source.filename }}</div>
                </div>
              </div>

              <div class="flex gap-2">
                <button
                  @click="() => { navigator.clipboard.writeText(source.content); ElMessage.success('已复制') }"
                  class="flex-1 px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded hover:bg-accent/20 transition-colors"
                >
                  📋 复制原文
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 解释性信息 -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-white border border-border rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">❓</span>
            <h4 class="text-sm font-bold text-text">为什么选这个答案？</h4>
          </div>
          <p class="text-xs text-text2 leading-relaxed">
            {{ result.explanation.why }}
          </p>
        </div>

        <div class="bg-white border border-border rounded-lg p-4" :class="result.hasConflicts ? 'border-yellow-300 bg-yellow-50' : ''">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">{{ result.hasConflicts ? '⚠️' : '🔄' }}</span>
            <h4 class="text-sm font-bold text-text">{{ result.hasConflicts ? '冲突信息' : '还有其他可能吗？' }}</h4>
          </div>
          <p class="text-xs text-text2 leading-relaxed">
            {{ result.explanation.alternatives }}
          </p>
        </div>

        <div class="bg-white border border-border rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">✓</span>
            <h4 class="text-sm font-bold text-text">数据可信度？</h4>
          </div>
          <p class="text-xs text-text2 leading-relaxed">
            {{ result.explanation.credibility }}
          </p>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="bg-surface2 border-2 border-dashed border-border rounded-lg p-12 text-center">
      <div class="text-4xl mb-3">💬</div>
      <div class="text-sm text-text2">输入问题并点击"开始问答"，系统将为您检索多源文档并生成答案</div>
    </div>
  </div>
</template>

<style scoped>
</style>
