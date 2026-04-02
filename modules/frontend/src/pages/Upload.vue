<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const API_BASE = 'http://localhost:8000'
const file = ref<File | null>(null)
const loading = ref(false)
const fileId = ref('')
const uploadHistory = ref<any[]>([])

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement
  file.value = input.files?.[0] || null
}

const handleUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    
    const response = await fetch(`${API_BASE}/upload`, { 
      method: 'POST', 
      body: formData
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || '上传失败')
    }
    
    const data = await response.json()
    fileId.value = data.file_id
    ElMessage.success('上传成功，开始解析...')
    
    // 自动提交解析任务
    const parseResponse = await fetch(`${API_BASE}/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: data.file_id })
    })
    
    if (parseResponse.ok) {
      ElMessage.success('解析任务已提交，请稍候...')
    }
    
    await loadFileList()
    file.value = null
  } catch (error) {
    ElMessage.error(`上传失败: ${error.message}`)
    console.error('Upload error:', error)
  } finally {
    loading.value = false
  }
}

const loadFileList = async () => {
  try {
    const response = await fetch(`${API_BASE}/files?size=100`)
    const data = await response.json()
    uploadHistory.value = data.files || []
  } catch (error) {
    console.error('加载失败')
  }
}

onMounted(() => {
  loadFileList()
})
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      文档上传与解析入库
    </div>

    <div class="grid grid-cols-12 gap-8">
      <div class="col-span-5">
        <label class="block text-sm font-medium text-text2 mb-2">选择文件</label>
        <label class="bg-white border-2 border-dashed border-border rounded-lg p-12 text-center hover:border-accent transition-colors cursor-pointer h-full flex flex-col items-center justify-center block">
          <div class="text-5xl mb-4">📁</div>
          <div class="text-sm text-text2 mb-2 font-medium">拖拽文件至此，或点击选择</div>
          <div class="text-xs text-muted mb-6">支持 PDF · DOCX · XLSX · TXT · MD</div>
          <div v-if="file" class="text-xs text-accent font-medium mb-4">已选择：{{ file.name }}</div>
          <input type="file" class="hidden" accept=".pdf,.docx,.xlsx,.txt,.md,.xls" @change="handleFileSelect" />
        </label>
      </div>

      <div class="col-span-2"></div>

      <div class="col-span-5 space-y-4">
        <div v-if="fileId">
          <label class="block text-sm font-medium text-text2 mb-2">File ID</label>
          <div class="flex gap-2">
            <input v-model="fileId" readonly type="text" class="flex-1 px-3 py-2 bg-surface border border-border rounded-md text-sm text-text font-mono" />
            <button @click="() => { navigator.clipboard.writeText(fileId); ElMessage.success('已复制') }" class="px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded-md hover:bg-accent/20 transition-colors">复制</button>
          </div>
        </div>

        <button @click="handleUpload" :disabled="loading || !file" class="w-full px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors">
          {{ loading ? '处理中...' : '上传并解析' }}
        </button>
      </div>
    </div>

    <div v-if="uploadHistory.length > 0">
      <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">上传历史</div>
      <div class="bg-white border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-surface2 border-b border-border">
              <th class="px-4 py-3 text-left font-semibold text-text2">文件名</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">状态</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">分块数</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">File ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in uploadHistory" :key="record.file_id" class="border-b border-border-l hover:bg-surface2">
              <td class="px-4 py-3 text-text">{{ record.filename }}</td>
              <td class="px-4 py-3"><span class="px-2 py-1 rounded text-xs font-medium bg-green/10 text-green">{{ record.status }}</span></td>
              <td class="px-4 py-3 text-text2">{{ record.chunk_count }}</td>
              <td class="px-4 py-3 text-text2 font-mono text-xs">{{ record.file_id.substring(0, 8) }}...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
