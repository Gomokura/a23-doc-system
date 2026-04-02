<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

interface FillResult {
  output_file_id: string
  download_url: string
}

const API_BASE = 'http://localhost:8000'

const template = ref<File | null>(null)
const fileIds = ref('')
const loading = ref(false)
const result = ref<FillResult | null>(null)

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
    // 第 1 步：上传模板
    const formData = new FormData()
    formData.append('file', template.value)

    const uploadResponse = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData
    })

    if (!uploadResponse.ok) throw new Error('模板上传失败')

    const uploadData = await uploadResponse.json()
    const templateFileId = uploadData.file_id

    // 第 2 步：调用回填接口
    const fillResponse = await fetch(`${API_BASE}/fill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId,
        answers: fileIds.value.split(',').map(id => id.trim()).map(id => ({
          file_id: id,
          fields: {}
        }))
      })
    })

    if (!fillResponse.ok) throw new Error('回填失败')

    const fillData = await fillResponse.json()
    result.value = {
      output_file_id: fillData.output_file_id,
      download_url: `${API_BASE}${fillData.download_url}`
    }

    ElMessage.success('回填成功')
  } catch (error) {
    ElMessage.error(`回填失败: ${error}`)
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

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement
  template.value = input.files?.[0] || null
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
        <label class="bg-white border-2 border-dashed border-border rounded-lg p-12 text-center hover:border-accent transition-colors cursor-pointer h-full flex flex-col items-center justify-center block">
          <div class="text-5xl mb-4">📄</div>
          <div class="text-sm text-text2 mb-2 font-medium">拖拽文件至此，或点击选择</div>
          <div class="text-xs text-muted mb-6">支持 DOCX 格式</div>
          <div v-if="template" class="text-xs text-accent font-medium mb-4">
            已选择：{{ template.name }}
          </div>
          <input
            type="file"
            class="hidden"
            accept=".docx"
            @change="handleFileSelect"
          />
        </label>
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
      <div class="bg-green/10 border border-green rounded-lg p-6">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-2xl">✓</span>
          <h3 class="text-sm font-bold text-green">回填成功</h3>
        </div>
        <p class="text-xs text-green mb-4">您的文档已成功回填，可以下载查看。</p>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div class="bg-white border border-border rounded-lg p-4">
          <div class="text-xs text-muted mb-2">输出 ID</div>
          <div class="font-mono text-sm text-text break-all">{{ result.output_file_id }}</div>
        </div>
        <div class="bg-white border border-border rounded-lg p-4">
          <div class="text-xs text-muted mb-2">下载地址</div>
          <div class="font-mono text-sm text-accent break-all">{{ result.download_url }}</div>
        </div>
      </div>

      <div class="flex gap-3">
        <button
          @click="handleDownload"
          class="flex-1 px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 transition-colors flex items-center justify-center gap-2"
        >
          ⬇️ 下载回填文档
        </button>
        <button
          @click="() => { navigator.clipboard.writeText(result.output_file_id); ElMessage.success('已复制') }"
          class="flex-1 px-4 py-3 bg-surface text-text2 font-medium rounded-md border border-border hover:bg-surface2 transition-colors flex items-center justify-center gap-2"
        >
          📋 复制 ID
        </button>
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
