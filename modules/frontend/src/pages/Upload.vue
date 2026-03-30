<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const file = ref<File | null>(null)
const status = ref('')
const fileId = ref('')
const loading = ref(false)

const handleUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  loading.value = true
  status.value = '正在上传文件...'

  try {
    const formData = new FormData()
    formData.append('file', file.value)

    const response = await fetch('http://localhost:8000/upload', {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) throw new Error('上传失败')

    const data = await response.json()
    fileId.value = data.file_id
    status.value = `上传成功：${data.filename}\n正在提交解析任务...`

    setTimeout(() => {
      status.value = `解析完成，文档已入库\nFile ID：${fileId.value}`
      ElMessage.success('文档上传成功')
    }, 1000)
  } catch (error) {
    status.value = `错误：${error}`
    ElMessage.error('上传失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      文档上传与解析入库
    </div>

    <div class="grid grid-cols-12 gap-8">
      <!-- 左侧：文件上传 -->
      <div class="col-span-5">
        <div class="bg-white border-2 border-dashed border-border rounded-lg p-12 text-center hover:border-accent transition-colors cursor-pointer h-full flex flex-col items-center justify-center">
          <div class="text-5xl mb-4">📁</div>
          <div class="text-sm text-text2 mb-2 font-medium">拖拽文件至此，或点击选择</div>
          <div class="text-xs text-muted mb-6">支持 PDF · DOCX · XLSX · TXT · MD</div>
          <input
            type="file"
            class="hidden"
            accept=".pdf,.docx,.xlsx,.txt,.md"
            @change="(e) => file = (e.target as HTMLInputElement).files?.[0] || null"
          />
        </div>
      </div>

      <!-- 中间：留白 -->
      <div class="col-span-2"></div>

      <!-- 右侧：处理信息 -->
      <div class="col-span-5 space-y-4">
        <div>
          <label class="block text-sm font-medium text-text2 mb-2">处理日志</label>
          <textarea
            v-model="status"
            readonly
            class="w-full h-24 px-3 py-2 bg-surface border border-border rounded-md text-sm text-text resize-none"
            placeholder="等待上传..."
          ></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium text-text2 mb-2">File ID</label>
          <input
            v-model="fileId"
            readonly
            type="text"
            class="w-full px-3 py-2 bg-surface border border-border rounded-md text-sm text-text"
            placeholder="—"
          />
        </div>
        <button
          @click="handleUpload"
          :disabled="loading"
          class="w-full px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '上传中...' : '上传并解析' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
