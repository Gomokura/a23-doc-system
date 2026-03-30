<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const query = ref('')
const fileIds = ref<string[]>([])
const answer = ref('')
const sources = ref('')
const loading = ref(false)

const handleQuery = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  loading.value = true
  answer.value = '正在查询...'
  sources.value = ''

  try {
    const response = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query.value,
        file_ids: fileIds.value,
      }),
    })

    if (!response.ok) throw new Error('查询失败')

    const data = await response.json()
    answer.value = data.answer || '无答案'
    
    if (data.sources && data.sources.length > 0) {
      sources.value = data.sources
        .map((s: any) => `**[第${s.page}页] ${s.source_file}**\n> ${s.content}`)
        .join('\n\n---\n\n')
    } else {
      sources.value = '*暂无证据来源*'
    }
  } catch (error) {
    answer.value = `错误：${error}`
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

    <div class="grid grid-cols-12 gap-6">
      <div class="col-span-6">
        <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
          回答
        </div>
        <div class="bg-white border border-border rounded-lg p-4 min-h-48 text-sm text-text prose prose-sm max-w-none">
          {{ answer || '*问答结果将在此显示*' }}
        </div>
      </div>

      <div class="col-span-6">
        <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
          证据来源
        </div>
        <div class="bg-white border border-border rounded-lg p-4 min-h-48 text-sm text-text prose prose-sm max-w-none">
          {{ sources || '*问答后显示证据来源与页码*' }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
