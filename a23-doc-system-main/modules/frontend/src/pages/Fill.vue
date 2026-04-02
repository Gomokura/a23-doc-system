<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

interface FieldMapping {
  field: string
  value: string
  status: 'success' | 'warning' | 'error'
  confidence: number
}

interface FillResult {
  success: boolean
  output_file_id: string
  download_url: string
  fieldMappings: FieldMapping[]
  quality: {
    fieldMatchRate: number
    dataAccuracy: number
    formatCompatibility: boolean
    processingTime: number
  }
}

const template = ref<File | null>(null)
const fileIds = ref('')
const loading = ref(false)
const result = ref<FillResult | null>(null)

// Mock 数据
const mockResult: FillResult = {
  success: true,
  output_file_id: 'output_20240331_001',
  download_url: 'http://localhost:8000/download/output_20240331_001',
  fieldMappings: [
    { field: '合同金额', value: '500万元', status: 'success', confidence: 99 },
    { field: '甲方', value: 'ABC公司', status: 'success', confidence: 98 },
    { field: '签署日期', value: '2024-01-15', status: 'success', confidence: 97 },
    { field: '付款方式', value: '分期付款', status: 'success', confidence: 96 },
    { field: '交付期限', value: '30天', status: 'success', confidence: 95 },
    { field: '质保期', value: '12个月', status: 'warning', confidence: 85 }
  ],
  quality: {
    fieldMatchRate: 100,
    dataAccuracy: 98,
    formatCompatibility: true,
    processingTime: 2.3
  }
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success': return '✓'
    case 'warning': return '⚠'
    case 'error': return '✕'
    default: return '•'
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'success': return 'bg-green/10 text-green'
    case 'warning': return 'bg-yellow-500/10 text-yellow-600'
    case 'error': return 'bg-red/10 text-red'
    default: return 'bg-muted/10 text-muted'
  }
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 95) return 'text-green'
  if (confidence >= 85) return 'text-accent'
  if (confidence >= 75) return 'text-yellow-500'
  return 'text-red'
}

const handleFill = async () => {
  if (!template.value) {
    ElMessage.warning('请先上传 Word 模板')
    return
  }

  if (!fileIds.value.trim()) {
    ElMessage.warning('请输入数据来源 File ID')
    return
  }

  loading.value = true

  try {
    // TODO: 替换为真实 API 调用
    // const formData = new FormData()
    // formData.append('file', template.value)
    // const response = await fetch('http://localhost:8000/upload', {...})
    // ...

    // 使用 mock 数据
    await new Promise(resolve => setTimeout(resolve, 1500))
    result.value = mockResult
    ElMessage.success('回填成功')
  } catch (error) {
    ElMessage.error('回填失败')
  } finally {
    loading.value = false
  }
}

const handleDownload = () => {
  if (result.value) {
    window.open(result.value.download_url, '_blank')
    ElMessage.success('开始下载')
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      Word 模板自动回填
    </div>

    <!-- 上传区域 -->
    <div class="grid grid-cols-12 gap-6">
      <div class="col-span-5">
        <label class="block text-sm font-medium text-text2 mb-2">上传 Word 模板 (.docx)</label>
        <div class="bg-white border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-accent transition-colors cursor-pointer">
          <div class="text-3xl mb-2">📄</div>
          <div class="text-xs text-text2 mb-1">点击或拖拽上传</div>
          <div class="text-xs text-muted" v-if="template">
            已选择：{{ template.name }}
          </div>
          <input
            type="file"
            class="hidden"
            accept=".docx"
            @change="(e) => template = (e.target as HTMLInputElement).files?.[0] || null"
          />
        </div>
      </div>

      <div class="col-span-5">
        <label class="block text-sm font-medium text-text2 mb-2">数据来源 File ID</label>
        <textarea
          v-model="fileIds"
          class="w-full h-32 px-3 py-2 bg-white border border-border rounded-md text-sm text-text resize-none focus:border-accent focus:outline-none"
          placeholder="已入库文档的 File ID，多个用逗号分隔"
        ></textarea>
        <div class="mt-3 p-3 bg-accent-bg border-l-2 border-accent rounded text-xs text-text2">
          模板中使用 <code class="bg-white px-1.5 py-0.5 rounded text-accent">{{字段名}}</code> 作为占位符
        </div>
      </div>

      <div class="col-span-2 flex flex-col items-center justify-start pt-8">
        <button
          @click="handleFill"
          :disabled="loading"
          class="w-full px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '处理中...' : '一键回填' }}
        </button>
      </div>
    </div>

    <!-- 回填结果 -->
    <div v-if="result" class="space-y-6">
      <!-- 数据映射 -->
      <div>
        <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
          🔄 数据映射（{{ result.fieldMappings.length }} 个字段）
        </div>
        <div class="space-y-2">
          <div
            v-for="(mapping, index) in result.fieldMappings"
            :key="index"
            class="bg-white border border-border rounded-lg p-4 flex items-center justify-between hover:border-accent transition-colors"
          >
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-lg" :class="getStatusColor(mapping.status)">
                  {{ getStatusIcon(mapping.status) }}
                </span>
                <span class="font-medium text-text">{{ mapping.field }}</span>
                <span class="text-xs px-2 py-1 rounded bg-surface2 text-text2">
                  {{ mapping.value }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <div class="w-24 bg-surface2 rounded-full h-1.5 overflow-hidden">
                  <div
                    class="h-full bg-accent transition-all"
                    :style="{ width: `${mapping.confidence}%` }"
                  ></div>
                </div>
                <span class="text-xs text-muted">{{ mapping.confidence }}% 置信度</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 回填质量指标 -->
      <div class="grid grid-cols-4 gap-4">
        <div class="bg-white border border-border rounded-lg p-4 text-center">
          <div class="text-2xl font-bold text-accent">{{ result.quality.fieldMatchRate }}%</div>
          <div class="text-xs text-muted mt-1">字段匹配率</div>
        </div>
        <div class="bg-white border border-border rounded-lg p-4 text-center">
          <div class="text-2xl font-bold text-accent">{{ result.quality.dataAccuracy }}%</div>
          <div class="text-xs text-muted mt-1">数据准确度</div>
        </div>
        <div class="bg-white border border-border rounded-lg p-4 text-center">
          <div class="text-2xl font-bold" :class="result.quality.formatCompatibility ? 'text-green' : 'text-red'">
            {{ result.quality.formatCompatibility ? '✓' : '✕' }}
          </div>
          <div class="text-xs text-muted mt-1">格式兼容性</div>
        </div>
        <div class="bg-white border border-border rounded-lg p-4 text-center">
          <div class="text-2xl font-bold text-accent">{{ result.quality.processingTime }}s</div>
          <div class="text-xs text-muted mt-1">处理时间</div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex gap-3">
        <button
          @click="handleDownload"
          class="flex-1 px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 transition-colors flex items-center justify-center gap-2"
        >
          ⬇️ 下载回填文档
        </button>
        <button
          class="flex-1 px-4 py-3 bg-surface text-text2 font-medium rounded-md border border-border hover:bg-surface2 transition-colors flex items-center justify-center gap-2"
        >
          👁️ 在线预览
        </button>
        <button
          class="flex-1 px-4 py-3 bg-surface text-text2 font-medium rounded-md border border-border hover:bg-surface2 transition-colors flex items-center justify-center gap-2"
        >
          📋 复制 ID
        </button>
      </div>

      <!-- 输出信息 -->
      <div class="bg-surface2 border border-border rounded-lg p-4">
        <div class="text-xs font-semibold text-text2 mb-2">输出信息</div>
        <div class="space-y-1 text-xs text-text2">
          <div>输出 ID：<span class="font-mono text-accent">{{ result.output_file_id }}</span></div>
          <div>下载地址：<span class="font-mono text-accent">{{ result.download_url }}</span></div>
          <div>生成时间：<span class="font-mono">{{ new Date().toLocaleString() }}</span></div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="bg-surface2 border-2 border-dashed border-border rounded-lg p-12 text-center">
      <div class="text-4xl mb-3">📝</div>
      <div class="text-sm text-text2">上传 Word 模板并指定数据来源，系统将自动回填数据</div>
    </div>
  </div>
</template>

<style scoped>
</style>
