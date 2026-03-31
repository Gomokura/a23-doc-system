<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

interface UploadHistory {
  filename: string
  fileId: string
  size: number
  uploadTime: string
  status: 'success' | 'processing' | 'error'
  pages?: number
}

interface ProcessStep {
  name: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  progress: number
}

const file = ref<File | null>(null)
const loading = ref(false)
const uploadProgress = ref(0)
const fileId = ref('')

const processSteps = ref<ProcessStep[]>([
  { name: '文件上传', status: 'pending', progress: 0 },
  { name: '格式识别', status: 'pending', progress: 0 },
  { name: '内容解析', status: 'pending', progress: 0 },
  { name: '向量化处理', status: 'pending', progress: 0 },
  { name: '索引入库', status: 'pending', progress: 0 }
])

const uploadHistory = ref<UploadHistory[]>([
  { filename: '采购合同_2024.pdf', fileId: 'file_001', size: 2.5, uploadTime: '2024-03-30 14:30', status: 'success', pages: 15 },
  { filename: '财务报表_Q1.xlsx', fileId: 'file_002', size: 1.2, uploadTime: '2024-03-30 13:45', status: 'success', pages: 8 },
  { filename: '采购计划_2024.docx', fileId: 'file_003', size: 0.8, uploadTime: '2024-03-30 12:20', status: 'success', pages: 5 }
])

const fileStats = computed(() => ({
  totalFiles: uploadHistory.value.length,
  totalSize: uploadHistory.value.reduce((sum, f) => sum + f.size, 0),
  totalPages: uploadHistory.value.reduce((sum, f) => sum + (f.pages || 0), 0)
}))

const getFileIcon = (filename: string) => {
  if (filename.endsWith('.pdf')) return '📕'
  if (filename.endsWith('.docx')) return '📄'
  if (filename.endsWith('.xlsx')) return '📊'
  if (filename.endsWith('.txt')) return '📝'
  if (filename.endsWith('.md')) return '📋'
  return '📁'
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success': return '✓'
    case 'processing': return '⏳'
    case 'error': return '✕'
    default: return '•'
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'success': return 'bg-green/10 text-green'
    case 'processing': return 'bg-accent/10 text-accent'
    case 'error': return 'bg-red/10 text-red'
    default: return 'bg-muted/10 text-muted'
  }
}

const getStepStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'bg-green text-white'
    case 'processing': return 'bg-accent text-white'
    case 'error': return 'bg-red text-white'
    default: return 'bg-surface2 text-text2'
  }
}

const handleUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  loading.value = true
  uploadProgress.value = 0
  fileId.value = ''

  // 重置处理步骤
  processSteps.value.forEach(step => {
    step.status = 'pending'
    step.progress = 0
  })

  try {
    // 模拟上传过程
    for (let i = 0; i < processSteps.value.length; i++) {
      processSteps.value[i].status = 'processing'

      // 模拟处理时间
      await new Promise(resolve => {
        const interval = setInterval(() => {
          processSteps.value[i].progress += Math.random() * 30
          if (processSteps.value[i].progress >= 100) {
            processSteps.value[i].progress = 100
            processSteps.value[i].status = 'completed'
            clearInterval(interval)
            resolve(null)
          }
        }, 200)
      })

      uploadProgress.value = ((i + 1) / processSteps.value.length) * 100
    }

    // 生成 File ID
    fileId.value = `file_${Date.now()}`

    // 添加到历史记录
    uploadHistory.value.unshift({
      filename: file.value.name,
      fileId: fileId.value,
      size: file.value.size / (1024 * 1024),
      uploadTime: new Date().toLocaleString('zh-CN'),
      status: 'success',
      pages: Math.floor(Math.random() * 20) + 5
    })

    ElMessage.success('文档上传成功')
  } catch (error) {
    processSteps.value.forEach(step => {
      if (step.status === 'processing') {
        step.status = 'error'
      }
    })
    ElMessage.error('上传失败')
  } finally {
    loading.value = false
  }
}

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement
  file.value = input.files?.[0] || null
}
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      文档上传与解析入库
    </div>

    <!-- 文件统计 -->
    <div class="grid grid-cols-3 gap-4">
      <div class="bg-white border border-border rounded-lg p-4 text-center">
        <div class="text-2xl font-bold text-accent">{{ fileStats.totalFiles }}</div>
        <div class="text-xs text-muted mt-1">已上传文档</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-4 text-center">
        <div class="text-2xl font-bold text-accent">{{ fileStats.totalSize.toFixed(1) }} MB</div>
        <div class="text-xs text-muted mt-1">总大小</div>
      </div>
      <div class="bg-white border border-border rounded-lg p-4 text-center">
        <div class="text-2xl font-bold text-accent">{{ fileStats.totalPages }}</div>
        <div class="text-xs text-muted mt-1">总页数</div>
      </div>
    </div>

    <!-- 上传区域 -->
    <div class="grid grid-cols-12 gap-8">
      <!-- 左侧：文件上传 -->
      <div class="col-span-5">
        <label class="block text-sm font-medium text-text2 mb-2">选择文件</label>
        <div class="bg-white border-2 border-dashed border-border rounded-lg p-12 text-center hover:border-accent transition-colors cursor-pointer h-full flex flex-col items-center justify-center">
          <div class="text-5xl mb-4">📁</div>
          <div class="text-sm text-text2 mb-2 font-medium">拖拽文件至此，或点击选择</div>
          <div class="text-xs text-muted mb-6">支持 PDF · DOCX · XLSX · TXT · MD</div>
          <div v-if="file" class="text-xs text-accent font-medium mb-4">
            已选择：{{ file.name }}
          </div>
          <input
            type="file"
            class="hidden"
            accept=".pdf,.docx,.xlsx,.txt,.md"
            @change="handleFileSelect"
          />
        </div>
      </div>

      <!-- 中间：留白 -->
      <div class="col-span-2"></div>

      <!-- 右侧：处理信息 -->
      <div class="col-span-5 space-y-4">
        <!-- 上传进度 -->
        <div v-if="loading">
          <label class="block text-sm font-medium text-text2 mb-2">上传进度</label>
          <div class="w-full bg-surface2 rounded-full h-2 overflow-hidden">
            <div
              class="h-full bg-accent transition-all duration-300"
              :style="{ width: `${uploadProgress}%` }"
            ></div>
          </div>
          <div class="text-xs text-muted mt-1">{{ Math.round(uploadProgress) }}%</div>
        </div>

        <!-- File ID -->
        <div v-if="fileId">
          <label class="block text-sm font-medium text-text2 mb-2">File ID</label>
          <div class="flex gap-2">
            <input
              v-model="fileId"
              readonly
              type="text"
              class="flex-1 px-3 py-2 bg-surface border border-border rounded-md text-sm text-text font-mono"
            />
            <button
              @click="() => { navigator.clipboard.writeText(fileId); ElMessage.success('已复制') }"
              class="px-3 py-2 bg-accent/10 text-accent text-sm font-medium rounded-md hover:bg-accent/20 transition-colors"
            >
              复制
            </button>
          </div>
        </div>

        <!-- 上传按钮 -->
        <button
          @click="handleUpload"
          :disabled="loading || !file"
          class="w-full px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '处理中...' : '上传并解析' }}
        </button>
      </div>
    </div>

    <!-- 处理步骤 -->
    <div v-if="loading" class="bg-white border border-border rounded-lg p-6">
      <div class="text-sm font-bold text-text mb-4">处理步骤</div>
      <div class="space-y-3">
        <div v-for="(step, index) in processSteps" :key="index" class="flex items-center gap-3">
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
            :class="getStepStatusColor(step.status)"
          >
            {{ step.status === 'completed' ? '✓' : step.status === 'processing' ? '⏳' : index + 1 }}
          </div>
          <div class="flex-1">
            <div class="text-sm text-text font-medium">{{ step.name }}</div>
            <div v-if="step.status !== 'pending'" class="w-full bg-surface2 rounded-full h-1.5 mt-1 overflow-hidden">
              <div
                class="h-full bg-accent transition-all duration-300"
                :style="{ width: `${step.progress}%` }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传历史 -->
    <div v-if="uploadHistory.length > 0">
      <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
        📜 上传历史（最近 {{ uploadHistory.length }} 个）
      </div>
      <div class="bg-white border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-surface2 border-b border-border">
              <th class="px-4 py-3 text-left font-semibold text-text2">文件名</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">大小</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">页数</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">上传时间</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">状态</th>
              <th class="px-4 py-3 text-left font-semibold text-text2">File ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(record, index) in uploadHistory" :key="index" class="border-b border-border-l hover:bg-surface2">
              <td class="px-4 py-3 text-text">
                <div class="flex items-center gap-2">
                  <span class="text-lg">{{ getFileIcon(record.filename) }}</span>
                  <span>{{ record.filename }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-text2">{{ record.size.toFixed(1) }} MB</td>
              <td class="px-4 py-3 text-text2">{{ record.pages }} 页</td>
              <td class="px-4 py-3 text-text2 text-xs">{{ record.uploadTime }}</td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="getStatusColor(record.status)"
                >
                  {{ getStatusIcon(record.status) }} {{ record.status === 'success' ? '已入库' : record.status === 'processing' ? '处理中' : '失败' }}
                </span>
              </td>
              <td class="px-4 py-3 text-text2 font-mono text-xs">
                <div class="flex items-center gap-2">
                  <span>{{ record.fileId }}</span>
                  <button
                    @click="() => { navigator.clipboard.writeText(record.fileId); ElMessage.success('已复制') }"
                    class="text-accent hover:text-blue-600"
                  >
                    📋
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
