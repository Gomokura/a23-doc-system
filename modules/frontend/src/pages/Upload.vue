<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { parseResponseJson } from '@/utils/parseApiResponse'

interface UploadHistory {
  file_id: string
  filename: string
  file_type: string
  file_size: number
  status: string
  chunk_count: number
  uploaded_at: string
}

interface ProcessStep {
  name: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  progress: number
}

const file = ref<File | null>(null)
const loading = ref(false)
const fileId = ref('')
const taskId = ref('')
const uploadHistory = ref<UploadHistory[]>([])

const processSteps = ref<ProcessStep[]>([
  { name: '文件上传', status: 'pending', progress: 0 },
  { name: '提交解析', status: 'pending', progress: 0 },
  { name: '内容解析', status: 'pending', progress: 0 },
  { name: '向量化处理', status: 'pending', progress: 0 },
  { name: '索引入库', status: 'pending', progress: 0 }
])

// 轮询解析进度
let pollTimer: ReturnType<typeof setTimeout> | null = null

const stopPolling = () => {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const pollParseStatus = async (taskId: string) => {
  try {
    const res = await fetch(`/api/parse/status/${taskId}`)
    const data = (await parseResponseJson(res)) as Record<string, any>

    if (data.status === 'pending') {
      processSteps.value[2].status = 'processing'
    } else if (data.status === 'processing') {
      // 10% → 70% 对应 parsing 阶段
      processSteps.value[2].status = 'processing'
      processSteps.value[2].progress = Math.min(70, Math.max(10, data.progress))
      // 70% → 90% 对应 indexing 阶段
      if (data.progress >= 70) {
        processSteps.value[3].status = 'processing'
        processSteps.value[3].progress = Math.min(90, data.progress)
      }
      if (data.progress >= 90) {
        processSteps.value[4].status = 'processing'
        processSteps.value[4].progress = data.progress
      }
    } else if (data.status === 'done') {
      processSteps.value[2].status = 'completed'
      processSteps.value[2].progress = 100
      processSteps.value[3].status = 'completed'
      processSteps.value[3].progress = 100
      processSteps.value[4].status = 'completed'
      processSteps.value[4].progress = 100
      stopPolling()
      await loadHistory()
      ElMessage.success('解析完成，文档已入库')
      loading.value = false
      return
    } else if (data.status === 'failed') {
      processSteps.value.forEach(s => { if (s.status === 'processing') s.status = 'error' })
      stopPolling()
      ElMessage.error('解析失败: ' + (data.error || '未知错误'))
      loading.value = false
      return
    }

    pollTimer = setTimeout(() => pollParseStatus(taskId), 2000)
  } catch (e: any) {
    stopPolling()
    ElMessage.error('查询解析状态失败')
    loading.value = false
  }
}

const handleUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  loading.value = true
  fileId.value = ''
  taskId.value = ''
  stopPolling()

  // 重置步骤
  processSteps.value.forEach(s => { s.status = 'pending'; s.progress = 0 })

  try {
    // 步骤1：上传文件
    processSteps.value[0].status = 'processing'
    const formData = new FormData()
    formData.append('file', file.value)

    const uploadRes = await fetch('/api/upload', { method: 'POST', body: formData })
    const uploadData = (await parseResponseJson(uploadRes)) as Record<string, any>

    if (!uploadRes.ok) throw new Error(uploadData.detail || '上传失败')

    fileId.value = uploadData.file_id
    processSteps.value[0].status = 'completed'
    processSteps.value[0].progress = 100

    if (uploadData.duplicate) {
      ElMessage.info('文件已存在，已跳过重复上传')
    }

    // 步骤2：提交解析任务
    processSteps.value[1].status = 'processing'
    const parseRes = await fetch('/api/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId.value })
    })
    const parseData = (await parseResponseJson(parseRes)) as Record<string, any>

    if (!parseRes.ok) throw new Error(parseData.detail || '提交解析失败')

    taskId.value = parseData.task_id
    processSteps.value[1].status = 'completed'
    processSteps.value[1].progress = 100

    // 开始轮询
    pollTimer = setTimeout(() => pollParseStatus(taskId.value), 1500)

  } catch (e: any) {
    processSteps.value.forEach(s => { if (s.status === 'processing') s.status = 'error' })
    ElMessage.error(e.message || '上传失败')
    loading.value = false
  }
}

const loadHistory = async () => {
  try {
    const res = await fetch('/api/files')
    const data = (await parseResponseJson(res)) as { files?: UploadHistory[] }
    if (res.ok) uploadHistory.value = data.files || []
  } catch {
    // 静默失败，不打扰主流程
  }
}

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement
  file.value = input.files?.[0] || null
}

const getFileIcon = (filename: string) => {
  if (filename.endsWith('.pdf')) return '📕'
  if (filename.endsWith('.docx')) return '📄'
  if (filename.endsWith('.xlsx')) return '📊'
  if (filename.endsWith('.txt')) return '📝'
  if (filename.endsWith('.md')) return '📋'
  return '📁'
}

const getStatusIcon = (status: string) => {
  if (status === 'indexed') return '✓'
  if (status === 'parsed') return '⏳'
  if (status === 'uploaded') return '↑'
  if (status === 'failed') return '✕'
  return '•'
}

const getStatusColor = (status: string) => {
  if (status === 'indexed') return 'bg-green/10 text-green'
  if (status === 'parsed') return 'bg-accent/10 text-accent'
  if (status === 'uploaded') return 'bg-blue-100 text-blue-600'
  if (status === 'failed') return 'bg-red/10 text-red'
  return 'bg-muted/10 text-muted'
}

const getStatusLabel = (status: string) => {
  if (status === 'indexed') return '已入库'
  if (status === 'parsed') return '已解析'
  if (status === 'uploaded') return '已上传'
  if (status === 'failed') return '失败'
  return status
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const formatTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

const totalChunks = () => uploadHistory.value.reduce((sum, f) => sum + (f.chunk_count || 0), 0)
const totalSize = () => uploadHistory.value.reduce((sum, f) => sum + (f.file_size || 0), 0)

const deletingId = ref('')

const handleDelete = async (record: UploadHistory) => {
  if (!confirm(`确定删除文件「${record.filename}」？\n删除后将无法恢复，且向量索引也会一并清除。`)) return
  deletingId.value = record.file_id
  try {
    const res = await fetch(`/api/files/${record.file_id}`, { method: 'DELETE' })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '删除失败')
    uploadHistory.value = uploadHistory.value.filter(r => r.file_id !== record.file_id)
    ElMessage.success('删除成功')
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  } finally {
    deletingId.value = ''
  }
}

const handleReParse = async (record: UploadHistory) => {
  const confirmed = confirm(
    `确定要对「${record.filename}」重新解析？\n` +
    `· 将删除旧的向量索引\n` +
    `· 用 VLM 重新解析（需 Ollama 运行）\n` +
    `· 完成后自动清除该文件的问答缓存`
  )
  if (!confirmed) return

  try {
    // 调用新的 /files/{file_id}/reparse（一键完成：删索引 + 重解析 + 清缓存）
    const res = await fetch(`/api/files/${record.file_id}/reparse`, { method: 'POST' })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '提交失败')

    ElMessage.success(`重新解析任务已提交，任务 ID：${data.task_id}，2秒后开始轮询进度...`)

    // 2.5s 后开始轮询进度（展示当前步骤状态）
    setTimeout(() => pollReParseStatus(data.task_id), 2500)
  } catch (e: any) {
    ElMessage.error(e.message || '提交失败')
  }
}

// 轮询重新解析任务的进度
const reparsePollTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const currentReParseTaskId = ref('')

const stopReParsePoll = () => {
  if (reparsePollTimer.value) {
    clearTimeout(reparsePollTimer.value)
    reparsePollTimer.value = null
  }
}

const pollReParseStatus = async (taskId: string) => {
  if (!taskId) return
  currentReParseTaskId.value = taskId
  try {
    const res = await fetch(`/api/parse/status/${taskId}`)
    const data = (await parseResponseJson(res)) as Record<string, any>

    if (data.status === 'done') {
      stopReParsePoll()
      // 自动清除该文件的问答缓存
      try {
        await fetch(`/api/cache/clear/${data.file_id}`, { method: 'POST' })
      } catch { /* ignore */ }
      await loadHistory()
      ElMessage.success('重新解析完成！该文件的问答缓存已清除，可重新测试。')
    } else if (data.status === 'failed') {
      stopReParsePoll()
      ElMessage.error('重新解析失败: ' + (data.error || '未知错误'))
    } else {
      // pending / processing：静默轮询，不重复弹消息打扰用户
      reparsePollTimer.value = setTimeout(() => pollReParseStatus(taskId), 3000)
    }
  } catch {
    stopReParsePoll()
    ElMessage.error('查询重新解析状态失败')
  }
}

const batchParsing = ref(false)
const batchResult = ref<string>('')

const handleBatchParse = async () => {
  batchParsing.value = true
  batchResult.value = ''
  try {
    const res = await fetch('/api/parse/batch', { method: 'POST' })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '批量解析失败')
    const submitted = data.tasks?.filter((t: any) => t.status === 'submitted').length || 0
    batchResult.value = data.message || `已提交 ${submitted} 个解析任务`
    ElMessage.success(batchResult.value)
    // 每2秒刷新一次历史记录，直到没有 uploaded 状态
    let checks = 0
    const interval = setInterval(async () => {
      await loadHistory()
      checks++
      const stillPending = uploadHistory.value.some(f => f.status === 'uploaded')
      if (!stillPending || checks > 30) clearInterval(interval)
    }, 2000)
  } catch (e: any) {
    ElMessage.error(e.message || '批量解析失败')
  } finally {
    batchParsing.value = false
  }
}

// ── 拖拽上传 ──────────────────────────────────────────────
const isDragging = ref(false)

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
  const dropped = e.dataTransfer?.files?.[0]
  if (!dropped) return
  const allowed = ['.pdf', '.docx', '.xlsx', '.txt', '.md', '.xls']
  const ext = '.' + dropped.name.split('.').pop()?.toLowerCase()
  if (!allowed.includes(ext)) {
    ElMessage.warning('不支持该文件类型，请上传 PDF / DOCX / XLSX / TXT / MD')
    return
  }
  file.value = dropped
  ElMessage.success(`已选择：${dropped.name}`)
}

// ── 生命周期 ──────────────────────────────────────────────
onMounted(() => {
  loadHistory()
})

onUnmounted(() => {
  stopPolling()
  stopReParsePoll()
})

</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      文档上传与解析入库
    </div>

    <!-- 文件统计 -->
    <div class="grid grid-cols-3 gap-4">
      <div class="bg-white border border-border rounded-lg p-4 text-center">
        <div class="text-2xl font-bold text-accent">{{ uploadHistory.length }}</div>
        <div class="text-xs text-muted mt-1">已上传文档</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-4 text-center">
        <div class="text-2xl font-bold text-accent">{{ formatSize(totalSize()) }}</div>
        <div class="text-xs text-muted mt-1">总大小</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-4 text-center">
        <div class="text-2xl font-bold text-accent">{{ totalChunks() }}</div>
        <div class="text-xs text-muted mt-1">总文本块</div>
      </div>
    </div>

    <!-- 上传区域 -->
    <div class="space-y-5">
      <div>
        <label class="block text-sm font-medium text-text2 mb-2">选择文件</label>
        <label
          class="bg-white border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer min-h-[320px] flex flex-col items-center justify-center block"
          :class="isDragging ? 'border-accent bg-accent/5' : 'border-border hover:border-accent'"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
        >
          <div class="text-5xl mb-4">{{ isDragging ? '📂' : '📁' }}</div>
          <div class="text-sm text-text2 mb-2 font-medium">{{ isDragging ? '松开鼠标即可上传' : '拖拽文件至此，或点击选择' }}</div>
          <div class="text-xs text-muted mb-6">支持 PDF · DOCX · XLSX · TXT · MD</div>
          <div v-if="file" class="text-xs text-accent font-medium mb-4">
            已选择：{{ file.name }}
          </div>
          <input
            type="file"
            class="hidden"
            accept=".pdf,.docx,.xlsx,.txt,.md,.xls"
            @change="handleFileSelect"
          />
        </label>
      </div>

      <div class="bg-white border border-border rounded-lg p-5 space-y-4">
        <button
          @click="handleUpload"
          :disabled="loading || !file"
          class="w-full px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '处理中...' : '上传并解析' }}
        </button>

        <div v-if="fileId">
          <label class="block text-sm font-medium text-text2 mb-1">File ID</label>
          <div class="flex gap-2">
            <input
              :value="fileId"
              readonly
              type="text"
              class="flex-1 px-3 py-2 bg-surface border border-border rounded-md text-sm text-text font-mono"
            />
            <button
              @click="() => { navigator.clipboard.writeText(fileId); ElMessage.success('已复制') }"
              class="px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded-md hover:bg-accent/20"
            >
              复制
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 处理步骤 -->
    <div v-if="loading" class="bg-white border border-border rounded-lg p-6">
      <div class="text-sm font-bold text-text mb-4">处理步骤</div>
      <div class="space-y-3">
        <div v-for="(step, index) in processSteps" :key="index" class="flex items-center gap-3">
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
            :class="{
              'bg-green text-white': step.status === 'completed',
              'bg-accent text-white': step.status === 'processing',
              'bg-red text-white': step.status === 'error',
              'bg-surface2 text-text2': step.status === 'pending'
            }"
          >
            {{ step.status === 'completed' ? '✓' : step.status === 'processing' ? '⏳' : index + 1 }}
          </div>
          <div class="flex-1">
            <div class="text-sm text-text font-medium">{{ step.name }}</div>
            <div v-if="step.status !== 'pending'" class="w-full bg-surface2 rounded-full h-1.5 mt-1 overflow-hidden">
              <div
                class="h-full bg-accent transition-all duration-300"
                :style="{ width: step.progress + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传历史 -->
    <div>
      <div class="flex items-center justify-between pb-2.5 border-b border-border-l mb-4">
        <div class="text-xs font-bold tracking-widest text-muted uppercase">
          上传历史
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="handleBatchParse"
            :disabled="batchParsing || !uploadHistory.some(f => f.status === 'uploaded')"
            class="text-xs px-3 py-1 bg-accent text-white rounded hover:bg-blue-600 disabled:opacity-40 font-medium transition-colors"
          >
            {{ batchParsing ? '解析中...' : '一键解析全部' }}
          </button>
          <button
            @click="loadHistory"
            class="text-xs text-accent hover:text-blue-600"
          >
            刷新
          </button>
        </div>
      </div>
      <div class="bg-white border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-surface2 border-b border-border">
              <th class="px-4 py-3 text-left font-semibold text-text2">文件名</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">大小</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">文本块</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">状态</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">File ID</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in uploadHistory" :key="record.file_id" class="border-b border-border-l hover:bg-surface2">
              <td class="px-4 py-3 text-text">
                <div class="flex items-center gap-2">
                  <span class="text-lg">{{ getFileIcon(record.filename) }}</span>
                  <span>{{ record.filename }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-text2">{{ formatSize(record.file_size) }}</td>
              <td class="px-4 py-3 text-text2">{{ record.chunk_count || 0 }} 块</td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="getStatusColor(record.status)"
                >
                  {{ getStatusIcon(record.status) }} {{ getStatusLabel(record.status) }}
                </span>
              </td>
              <td class="px-4 py-3 text-text2 font-mono text-xs">
                <div class="flex items-center gap-2">
                  <span>{{ record.file_id.slice(0, 8) }}...</span>
                  <button
                    @click="() => { navigator.clipboard.writeText(record.file_id); ElMessage.success('已复制') }"
                    class="text-accent hover:text-blue-600"
                  >
                    📋
                  </button>
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1.5">
                  <button
                    v-if="record.status === 'uploaded' || record.status === 'indexed'"
                    @click="handleReParse(record)"
                    class="px-2 py-1 text-xs bg-blue-100 text-blue-600 rounded hover:bg-blue-200 font-medium"
                  >
                    重新解析
                  </button>
                  <button
                    @click="handleDelete(record)"
                    :disabled="deletingId === record.file_id"
                    class="px-2 py-1 text-xs bg-red/10 text-red rounded hover:bg-red/20 font-medium disabled:opacity-40"
                  >
                    {{ deletingId === record.file_id ? '删除中' : '删除' }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="uploadHistory.length === 0">
              <td colspan="6" class="px-4 py-8 text-center text-muted">暂无上传记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
