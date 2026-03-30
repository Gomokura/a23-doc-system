<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const template = ref<File | null>(null)
const fileIds = ref('')
const status = ref('')
const loading = ref(false)

const handleFill = async () => {
  if (!template.value) {
    ElMessage.warning('请先上传 Word 模板')
    return
  }

  loading.value = true
  status.value = '正在处理...'

  try {
    const formData = new FormData()
    formData.append('file', template.value)

    const response = await fetch('http://localhost:8000/upload', {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) throw new Error('模板上传失败')

    const data = await response.json()
    const templateFileId = data.file_id

    const fillResponse = await fetch('http://localhost:8000/fill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId,
        file_ids: fileIds.value.split(',').map(id => id.trim()),
      }),
    })

    if (!fillResponse.ok) throw new Error('回填失败')

    const fillData = await fillResponse.json()
    status.value = `回填完成\n输出 ID：${fillData.output_file_id}\n下载地址：${fillData.download_url}`
    ElMessage.success('回填成功')
  } catch (error) {
    status.value = `错误：${error}`
    ElMessage.error('回填失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      Word 模板自动回填
    </div>

    <div class="grid grid-cols-12 gap-6">
      <div class="col-span-5">
        <label class="block text-sm font-medium text-text2 mb-2">上传 Word 模板 (.docx)</label>
        <div class="bg-white border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-accent transition-colors cursor-pointer">
          <div class="text-3xl mb-2">📄</div>
          <div class="text-xs text-text2">点击或拖拽上传</div>
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
          class="w-full px-4 py-2 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '处理中...' : '一键回填' }}
        </button>
      </div>
    </div>

    <div>
      <label class="block text-sm font-medium text-text2 mb-2">回填状态</label>
      <textarea
        v-model="status"
        readonly
        class="w-full h-24 px-3 py-2 bg-surface border border-border rounded-md text-sm text-text resize-none"
        placeholder="等待操作..."
      ></textarea>
    </div>
  </div>
</template>

<style scoped>
</style>
