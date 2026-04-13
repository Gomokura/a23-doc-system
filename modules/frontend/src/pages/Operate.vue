<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { parseResponseJson } from '@/utils/parseApiResponse'

interface FileRecord {
  file_id: string
  filename: string
  file_type: string
  status: string
  chunk_count?: number
}

interface SupportedOperation {
  type: string
  name: string
  description: string
}

interface PreviewResult {
  instruction: string
  file_type: string
  parsed_operation?: {
    type?: string
    confidence?: number
    parameters?: Record<string, unknown>
    reasoning?: string
  }
  supported?: boolean
}

interface ExecuteResult {
  success?: boolean
  message?: string
  operation_type?: string
  confidence?: number
  result?: Record<string, unknown>
  backup_path?: string
  download_url?: string
}

const files = ref<FileRecord[]>([])
const selectedFileId = ref('')
const instruction = ref('')
const supportedOperations = ref<SupportedOperation[]>([])
const previewResult = ref<PreviewResult | null>(null)
const executeResult = ref<ExecuteResult | null>(null)

const loadingFiles = ref(false)
const loadingSupported = ref(false)
const loadingPreview = ref(false)
const loadingExecute = ref(false)

const quickPrompts = [
  '把第二段加粗并设为红色',
  '提取所有表格内容',
  '删除最后一段',
]

const selectedFile = computed(() => files.value.find(f => f.file_id === selectedFileId.value) || null)
const selectedFileType = computed(() => selectedFile.value?.file_type || 'docx')
const canSubmit = computed(() => !!selectedFile.value && !!instruction.value.trim())
const busy = computed(() => loadingPreview.value || loadingExecute.value)

const fmt = (v: unknown) => {
  if (v == null || v === '') return '—'
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

const confidenceClass = (v?: number) => {
  const n = v || 0
  if (n >= 0.85) return 'text-green bg-green/10 border-green/20'
  if (n >= 0.6) return 'text-accent bg-accent/10 border-accent/20'
  if (n >= 0.35) return 'text-yellow-600 bg-yellow-500/10 border-yellow-500/20'
  return 'text-red bg-red/10 border-red/20'
}

async function loadFiles() {
  loadingFiles.value = true
  try {
    const res = await fetch('/api/files')
    const data = (await parseResponseJson(res)) as { files?: FileRecord[]; detail?: string }
    if (!res.ok) throw new Error(data.detail || `加载文件失败 (${res.status})`)
    files.value = (data.files || []).filter(f => ['docx', 'xlsx', 'pdf'].includes(f.file_type))
    if (selectedFileId.value && !files.value.some(f => f.file_id === selectedFileId.value)) {
      selectedFileId.value = ''
    }
    if (!selectedFileId.value && files.value.length > 0) {
      selectedFileId.value = files.value[0].file_id
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载文件失败')
  } finally {
    loadingFiles.value = false
  }
}

async function loadSupportedOperations(fileType: string) {
  if (!fileType) return
  loadingSupported.value = true
  try {
    const res = await fetch(`/api/document/supported_operations/${fileType}`)
    const data = (await parseResponseJson(res)) as { operations?: SupportedOperation[]; detail?: string }
    if (!res.ok) throw new Error(data.detail || `加载支持操作失败 (${res.status})`)
    supportedOperations.value = data.operations || []
  } catch (e: any) {
    supportedOperations.value = []
    ElMessage.error(e.message || '加载支持操作失败')
  } finally {
    loadingSupported.value = false
  }
}

async function handlePreview() {
  if (!canSubmit.value) return ElMessage.warning('请先选择文件并输入操作指令')
  loadingPreview.value = true
  previewResult.value = null
  try {
    const res = await fetch('/api/document/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction: instruction.value.trim(), file_type: selectedFileType.value }),
    })
    const data = (await parseResponseJson(res)) as PreviewResult & { detail?: string }
    if (!res.ok) throw new Error(data.detail || `预览失败 (${res.status})`)
    previewResult.value = data
    ElMessage.success(data.supported === false ? '指令已解析，但暂不支持' : '预览成功')
  } catch (e: any) {
    ElMessage.error(e.message || '预览失败')
  } finally {
    loadingPreview.value = false
  }
}

async function handleExecute() {
  if (!canSubmit.value) return ElMessage.warning('请先选择文件并输入操作指令')
  loadingExecute.value = true
  executeResult.value = null
  try {
    const res = await fetch('/api/document/operate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: selectedFileId.value, instruction: instruction.value.trim(), create_backup: true }),
    })
    const data = (await parseResponseJson(res)) as ExecuteResult & { detail?: string }
    if (!res.ok) throw new Error(data.detail || `执行失败 (${res.status})`)
    executeResult.value = data
    ElMessage[data.success ? 'success' : 'warning'](data.message || (data.success ? '执行成功' : '执行未成功'))
    if (data.success) await loadFiles()
  } catch (e: any) {
    ElMessage.error(e.message || '执行失败')
  } finally {
    loadingExecute.value = false
  }
}

watch(selectedFileType, type => {
  previewResult.value = null
  executeResult.value = null
  loadSupportedOperations(type)
})

onMounted(loadFiles)
</script>

<template>
  <div class="space-y-6">
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">文档智能操作交互</div>

    <section class="rounded-xl border border-border bg-white p-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="text-lg font-semibold text-text">像聊天一样编辑文档</div>
          <div class="mt-1 text-sm text-text2">先选文件，再输入自然语言指令，建议先预览再执行。</div>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              v-for="prompt in quickPrompts"
              :key="prompt"
              @click="instruction = prompt"
              class="rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text2 hover:bg-surface2"
            >
              {{ prompt }}
            </button>
          </div>
        </div>
        <div class="min-w-[220px] rounded-lg border border-border bg-surface/70 p-4 text-sm">
          <div class="text-xs uppercase tracking-widest text-muted">当前文档</div>
          <div class="mt-2 text-text font-medium">{{ selectedFile?.filename || '尚未选择文件' }}</div>
          <div class="mt-1 text-xs text-text2">
            {{ selectedFile ? `${selectedFile.file_type.toUpperCase()} · ${selectedFile.status}` : '请先从左侧选择文档' }}
          </div>
        </div>
      </div>
    </section>

    <div class="grid grid-cols-12 gap-4">
      <section class="col-span-4 bg-white border border-border rounded-lg p-4 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-semibold text-text">文件选择</div>
            <div class="text-xs text-muted mt-1">支持 .docx / .xlsx / .pdf</div>
          </div>
          <button @click="loadFiles" class="text-xs text-accent hover:underline" :disabled="loadingFiles">{{ loadingFiles ? '刷新中...' : '刷新' }}</button>
        </div>

        <div class="border border-border rounded-md overflow-hidden max-h-64 overflow-y-auto">
          <div v-if="files.length === 0" class="px-3 py-8 text-center text-sm text-muted">暂无可操作文档，请先上传并完成入库。</div>
          <label v-for="file in files" :key="file.file_id" class="flex gap-3 px-3 py-3 border-b last:border-b-0 border-border cursor-pointer hover:bg-surface2" :class="selectedFileId === file.file_id ? 'bg-accent/5' : 'bg-white'">
            <input v-model="selectedFileId" type="radio" name="operate-file" :value="file.file_id" class="mt-1 accent-accent" />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium text-text truncate">{{ file.filename }}</div>
              <div class="mt-1 flex items-center gap-2 text-xs text-muted">
                <span class="px-2 py-0.5 rounded-full bg-surface2 text-text2 uppercase">{{ file.file_type }}</span>
                <span>{{ file.status }}</span>
                <span v-if="file.chunk_count">{{ file.chunk_count }} chunks</span>
              </div>
            </div>
          </label>
        </div>

        <div class="rounded-md border border-border bg-surface/60 p-3">
          <div class="flex items-center justify-between"><div class="text-sm font-medium text-text">支持操作</div><span class="text-xs text-muted">{{ loadingSupported ? '加载中...' : `${supportedOperations.length} 项` }}</span></div>
          <div class="mt-3 space-y-2 max-h-56 overflow-y-auto pr-1">
            <div v-if="!selectedFile" class="text-xs text-muted">选择文档后显示支持列表。</div>
            <div v-for="item in supportedOperations" :key="item.type" class="rounded-md border border-border bg-white px-3 py-2">
              <div class="flex items-center justify-between gap-2"><span class="text-sm font-medium text-text">{{ item.name }}</span><span class="text-[11px] text-muted font-mono">{{ item.type }}</span></div>
              <div class="mt-1 text-xs text-text2">{{ item.description }}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="col-span-8 bg-white border border-border rounded-lg p-4 space-y-4">
        <div>
          <div class="text-sm font-semibold text-text">指令输入</div>
          <div class="text-xs text-muted mt-1">例如：把第二段加粗并设为红色；提取所有表格内容。</div>
        </div>

        <textarea v-model="instruction" class="w-full min-h-[140px] px-3 py-3 bg-white border border-border rounded-md text-sm text-text resize-y focus:border-accent focus:outline-none" placeholder="输入你的自然语言指令..." />

        <div class="flex flex-wrap items-center gap-3">
          <button @click="handlePreview" :disabled="!canSubmit || busy" class="px-4 py-2 bg-surface text-text2 font-medium rounded-md border border-border hover:bg-surface2 disabled:opacity-50">{{ loadingPreview ? '预览中...' : '预览' }}</button>
          <button @click="handleExecute" :disabled="!canSubmit || busy" class="px-4 py-2 bg-accent text-white font-medium rounded-md hover:opacity-90 disabled:opacity-50">{{ loadingExecute ? '执行中...' : '执行' }}</button>
          <a v-if="executeResult?.download_url" :href="executeResult.download_url" class="px-4 py-2 bg-green text-white font-medium rounded-md hover:opacity-90">下载修改后文件</a>
          <div class="text-xs text-muted">当前文档：<span class="text-text2 font-medium">{{ selectedFile?.filename || '未选择' }}</span></div>
        </div>

        <div class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          文档操作修改的是系统中上传后的副本文件，不会直接改你电脑原始文件。执行成功后请点击“下载修改后文件”获取新版本。
        </div>

        <div v-if="previewResult || executeResult" class="rounded-lg border border-border bg-white p-3">
          <div class="text-xs uppercase tracking-widest text-muted">操作洞察</div>
          <div class="mt-2 text-sm text-text">
            {{ previewResult?.parsed_operation?.reasoning || executeResult?.message || '结果将显示在这里。' }}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="rounded-md border border-border p-4 bg-surface/40 min-h-[300px]">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-semibold text-text">预览结果</div>
              <span v-if="previewResult?.parsed_operation?.confidence !== undefined" class="px-2.5 py-1 text-xs rounded-full border" :class="confidenceClass(previewResult.parsed_operation.confidence)">置信度 {{ Math.round((previewResult.parsed_operation.confidence || 0) * 100) }}%</span>
            </div>
            <div v-if="!previewResult" class="text-sm text-muted leading-6">点击“预览”后，这里会展示解析出的操作类型、参数和说明。</div>
            <div v-else class="space-y-3 text-sm">
              <div><span class="text-muted">操作类型：</span><span class="text-text font-medium">{{ previewResult.parsed_operation?.type || 'unknown' }}</span></div>
              <div><span class="text-muted">解析状态：</span><span :class="previewResult.supported === false ? 'text-yellow-600' : 'text-green'">{{ previewResult.supported === false ? '暂不支持' : '可执行' }}</span></div>
              <div>
                <div class="text-muted mb-2">参数</div>
                <pre class="text-xs bg-white border border-border rounded-md p-3 overflow-x-auto text-text whitespace-pre-wrap">{{ fmt(previewResult.parsed_operation?.parameters || {}) }}</pre>
              </div>
              <div>
                <div class="text-muted mb-2">预览说明</div>
                <div class="text-text2 leading-6 bg-white border border-border rounded-md p-3">{{ previewResult.parsed_operation?.reasoning || '后端未返回额外说明。' }}</div>
              </div>
            </div>
          </div>

          <div class="rounded-md border border-border p-4 bg-surface/40 min-h-[300px]">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-semibold text-text">执行结果</div>
              <span v-if="executeResult?.confidence !== undefined" class="px-2.5 py-1 text-xs rounded-full border" :class="confidenceClass(executeResult.confidence)">置信度 {{ Math.round((executeResult.confidence || 0) * 100) }}%</span>
            </div>
            <div v-if="!executeResult" class="text-sm text-muted leading-6">点击“执行”后，这里会展示执行状态、反馈信息和备份路径。</div>
            <div v-else class="space-y-3 text-sm">
              <div><span class="text-muted">执行状态：</span><span :class="executeResult.success ? 'text-green font-medium' : 'text-red font-medium'">{{ executeResult.success ? '执行成功' : '执行失败' }}</span></div>
              <div><span class="text-muted">操作类型：</span><span class="text-text font-medium">{{ executeResult.operation_type || 'unknown' }}</span></div>
              <div>
                <div class="text-muted mb-2">反馈信息</div>
                <div class="text-text2 leading-6 bg-white border border-border rounded-md p-3">{{ executeResult.message || '无返回信息' }}</div>
              </div>
              <div v-if="executeResult.backup_path">
                <div class="text-muted mb-2">备份路径</div>
                <div class="font-mono text-xs text-text bg-white border border-border rounded-md p-3 break-all">{{ executeResult.backup_path }}</div>
              </div>
              <div>
                <div class="text-muted mb-2">结果详情</div>
                <pre class="text-xs bg-white border border-border rounded-md p-3 overflow-x-auto text-text whitespace-pre-wrap">{{ fmt(executeResult.result || executeResult) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
