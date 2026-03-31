<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

interface Evidence {
  filename: string
  page: number
  content: string
  relevance: number
  confidence: number
}

interface QueryResult {
  answer: string
  confidence: number
  sources: Evidence[]
  explanation: {
    why: string
    alternatives: string
    credibility: string
  }
}

const query = ref('')
const fileIds = ref<string[]>([])
const loading = ref(false)
const expandedSources = ref<Set<number>>(new Set())

const result = ref<QueryResult | null>(null)

// Mock 数据
const mockResult: QueryResult = {
  answer: '合同总金额为 500 万元人民币，分三期支付。第一期 200 万元在签署后 30 天内支付，第二期 200 万元在交付后 30 天内支付，第三期 100 万元在验收后 30 天内支付。',
  confidence: 94,
  sources: [
    {
      filename: '采购合同_2024.pdf',
      page: 3,
      content: '合同总金额：500万元人民币，分三期支付。第一期200万元在签署后30天内支付...',
      relevance: 98,
      confidence: 99
    },
    {
      filename: '财务报表_Q1.xlsx',
      page: 5,
      content: '合同金额: 5,000,000 元，付款方式：分期付款',
      relevance: 85,
      confidence: 92
    },
    {
      filename: '采购计划_2024.docx',
      page: 2,
      content: '预算金额 500 万元用于采购项目',
      relevance: 72,
      confidence: 88
    }
  ],
  explanation: {
    why: '2 个高相关文档都明确提到此金额和付款方式，信息一致',
    alternatives: '未发现矛盾信息，其他文档也支持此结论',
    credibility: '来自官方财务文档和合同，可信度高'
  }
}

const toggleSource = (index: number) => {
  if (expandedSources.value.has(index)) {
    expandedSources.value.delete(index)
  } else {
    expandedSources.value.add(index)
  }
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 90) return 'text-green'
  if (confidence >= 80) return 'text-accent'
  if (confidence >= 70) return 'text-yellow-500'
  return 'text-red'
}

const getRelevanceColor = (relevance: number) => {
  if (relevance >= 90) return 'bg-green/10 text-green'
  if (relevance >= 80) return 'bg-accent/10 text-accent'
  if (relevance >= 70) return 'bg-yellow-500/10 text-yellow-600'
  return 'bg-red/10 text-red'
}

const handleQuery = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  loading.value = true
  expandedSources.value.clear()

  try {
    // TODO: 替换为真实 API 调用
    // const response = await fetch('http://localhost:8000/query', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({
    //     query: query.value,
    //     file_ids: fileIds.value,
    //   }),
    // })
    // const data = await response.json()
    // result.value = data

    // 使用 mock 数据
    await new Promise(resolve => setTimeout(resolve, 800))
    result.value = mockResult
    ElMessage.success('查询成功')
  } catch (error) {
    ElMessage.error('查询失败')
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  try {
    const response = await fetch('http://localhost:8000/files')
    const data = await response.json()
    fileIds.value = data.files?.map((f: any) => f.file_id) || []
  } catch (error) {
    ElMessage.error('刷新文件列表失败')
  }
}
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
        <label class="block text-sm font-medium text-text2 mb-2">限定文档（留空则全库检索）</label>
        <div class="space-y-2">
          <select
            v-model="fileIds"
            multiple
            class="w-full px-3 py-2 bg-white border border-border rounded-md text-sm text-text focus:border-accent focus:outline-none"
          >
            <option value="">选择文档...</option>
          </select>
          <button
            @click="handleRefresh"
            class="w-full px-3 py-1.5 bg-surface text-text2 text-sm font-medium rounded-md border border-border hover:bg-surface2 transition-colors"
          >
            刷新列表
          </button>
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
        <div class="bg-surface2 rounded-lg p-4 text-sm text-text leading-relaxed">
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

            <!-- 证据内容（展开时显示） -->
            <div v-if="expandedSources.has(index)" class="border-t border-border-l bg-surface2 p-4 space-y-3">
              <div>
                <div class="text-xs font-semibold text-text2 mb-2">原文内容</div>
                <div class="bg-white border border-border rounded p-3 text-sm text-text leading-relaxed">
                  "{{ source.content }}"
                </div>
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
                  <div class="text-xs text-muted mb-1">来源</div>
                  <div class="text-sm font-medium text-text">{{ source.filename }}</div>
                </div>
              </div>

              <div class="flex gap-2">
                <button class="flex-1 px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded hover:bg-accent/20 transition-colors">
                  📋 复制
                </button>
                <button class="flex-1 px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded hover:bg-accent/20 transition-colors">
                  ⬇️ 下载
                </button>
                <button class="flex-1 px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded hover:bg-accent/20 transition-colors">
                  🔗 查看原文
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

        <div class="bg-white border border-border rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">🔄</span>
            <h4 class="text-sm font-bold text-text">还有其他可能吗？</h4>
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
