<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { parseResponseJson } from '@/utils/parseApiResponse'

// ── 类型定义 ────────────────────────────────────────────────
interface FileRecord {
  file_id: string
  filename: string
  status: string
  chunk_count: number
}

interface FieldItem {
  field: string
  value: string
  status: 'pending' | 'extracting' | 'success' | 'warning' | 'error'
  confidence: number
  sourceChunk: string
}

interface Progress {
  upload: boolean
  parse: boolean
  extract: boolean
  fill: boolean
  done: boolean
}

// ── 状态 ────────────────────────────────────────────────────
const templateFile = ref<File | null>(null)
const templateFileId = ref('')
const templateList = ref<FileRecord[]>([])
const useExisting = ref(false)
const selectedTemplateId = ref('')

const fieldList = ref<FieldItem[]>([])           // 自动解析出的字段
const sourceFileIds = ref<string[]>([])           // 数据来源文件
const loading = ref(false)
const step = ref<keyof Progress>('upload')

const progress = ref<Progress>({
  upload: false,
  parse: false,
  extract: false,
  fill: false,
  done: false,
})

const outputFileId = ref('')
const downloadUrl = ref('')
const errorMsg = ref('')

// ── 生命周期 ────────────────────────────────────────────────
onMounted(loadFileList)

// ── 工具函数 ────────────────────────────────────────────────
const getStatusIcon = (s: string) =>
  s === 'success' ? '✓' : s === 'extracting' ? '⏳' : s === 'warning' ? '⚠' : s === 'error' ? '✕' : '○'

const getStatusColor = (s: string) =>
  s === 'success' ? 'text-green' :
  s === 'extracting' ? 'text-accent' :
  s === 'warning' ? 'text-yellow-600' :
  s === 'error' ? 'text-red' : 'text-muted'

const getConfColor = (c: number) =>
  c >= 90 ? 'text-green' : c >= 75 ? 'text-accent' : c >= 50 ? 'text-yellow-500' : 'text-red'

const indexedFiles = computed(() =>
  templateList.value.filter(f => f.status === 'indexed')
)

const selectedFiles = computed(() =>
  templateList.value.filter(f => sourceFileIds.value.includes(f.file_id))
)

const allFieldsReady = computed(() =>
  fieldList.value.length > 0 && fieldList.value.every(f => f.status !== 'pending')
)

// ── 加载文件列表 ─────────────────────────────────────────────
async function loadFileList() {
  try {
    const res = await fetch('/api/files')
    const data = (await parseResponseJson(res)) as { files?: FileRecord[] }
    if (res.ok) templateList.value = data.files || []
  } catch { /* 静默 */ }
}

// ── 上传模板并自动解析占位符 ────────────────────────────────
async function handleUploadTemplate() {
  if (!templateFile.value) {
    ElMessage.warning('请先选择 Word 或 Excel 模板文件')
    return
  }

  progress.value.upload = true
  progress.value.parse = false
  progress.value.extract = false
  progress.value.fill = false
  progress.value.done = false
  step.value = 'parse'
  fieldList.value = []
  errorMsg.value = ''

  try {
    // 1. 上传模板
    const fd = new FormData()
    fd.append('file', templateFile.value)
    const upRes = await fetch('/api/upload', { method: 'POST', body: fd })
    const upData = (await parseResponseJson(upRes)) as Record<string, any>
    if (!upRes.ok) throw new Error(upData.detail || '上传失败')

    templateFileId.value = upData.file_id
    progress.value.upload = true

    // 2. 自动解析占位符
    const parseRes = await fetch('/api/template/placeholders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_file_id: templateFileId.value })
    })
    const parseData = (await parseResponseJson(parseRes)) as Record<string, any>
    if (!parseRes.ok) throw new Error(parseData.detail || '解析占位符失败')

    if (!parseData.fields || parseData.fields.length === 0) {
      ElMessage.warning('模板中未找到可填写字段')
      fieldList.value = []
    } else {
      const methodLabel = parseData.method === 'llm' ? 'AI智能识别' : '占位符解析'
      fieldList.value = parseData.fields.map((f: string) => ({
        field: f,
        value: '',
        status: 'pending' as const,
        confidence: 0,
        sourceChunk: '',
      }))
      ElMessage.success(`${methodLabel}完成，找到 ${parseData.fields.length} 个待填字段`)
    }

    progress.value.parse = true
    step.value = 'extract'

  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error(e.message)
    step.value = 'upload'
    progress.value.upload = false
  }
}

// ── 从历史模板解析占位符 ────────────────────────────────────
async function handleSelectExisting() {
  if (!selectedTemplateId.value) {
    ElMessage.warning('请先选择一个模板')
    return
  }

  progress.value.upload = true
  progress.value.parse = false
  fieldList.value = []
  errorMsg.value = ''

  try {
    const parseRes = await fetch('/api/template/placeholders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_file_id: selectedTemplateId.value })
    })
    const parseData = (await parseResponseJson(parseRes)) as Record<string, any>
    if (!parseRes.ok) throw new Error(parseData.detail || '解析占位符失败')

    if (!parseData.fields || parseData.fields.length === 0) {
      ElMessage.warning('模板中未找到可填写字段')
      fieldList.value = []
    } else {
      const methodLabel = parseData.method === 'llm' ? 'AI智能识别' : '占位符解析'
      fieldList.value = parseData.fields.map((f: string) => ({
        field: f,
        value: '',
        status: 'pending' as const,
        confidence: 0,
        sourceChunk: '',
      }))
      templateFileId.value = selectedTemplateId.value
      ElMessage.success(`${methodLabel}完成，找到 ${parseData.fields.length} 个待填字段`)
    }

    progress.value.upload = true
    progress.value.parse = true
    step.value = 'extract'

  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error(e.message)
  }
}

// ── 全量提取字段值 ──────────────────────────────────────────
async function handleExtractAll() {
  if (fieldList.value.length === 0) {
    ElMessage.warning('没有可提取的字段')
    return
  }
  if (sourceFileIds.value.length === 0) {
    ElMessage.warning('请至少选择一个数据来源文档')
    return
  }

  loading.value = true
  step.value = 'extract'
  errorMsg.value = ''

  const pending = fieldList.value.filter(f => f.status === 'pending')
  const doneMap = new Map(fieldList.value.map(f => [f.field, f]))

  for (const item of pending) {
    item.status = 'extracting'

    try {
      // 用 extract 场景专门做字段值提取，LLM 只返回纯值
      const askRes = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `从文档中提取"${item.field}"的值，只输出值本身`,
          file_ids: sourceFileIds.value,
          scenario: 'extract'
        })
      })
      const askData = (await parseResponseJson(askRes)) as Record<string, any>

      if (askRes.ok && askData.answer) {
        // extract 场景下 LLM 直接返回纯值，只做基本清理
        const raw = askData.answer
          .replace(/^(回答|值|答案|提取结果)[：:]\s*/g, '')  // 防止 LLM 仍然加前缀
          .replace(/\n来源[：:][\s\S]*/g, '')                 // 去掉来源行
          .replace(/\[文档\d+\]/g, '')                        // 去掉文档引用标记
          .trim()
          .slice(0, 200)

        if (raw && raw !== '(无)' && raw !== '未知' && raw !== '根据提供的信息无法回答该问题') {
          item.value = raw
          item.confidence = Math.round((askData.confidence || 0.6) * 100)
          item.sourceChunk = askData.sources?.[0]?.content?.slice(0, 60) || ''
          item.status = 'success'
        } else {
          item.value = '(未找到)'
          item.status = 'warning'
          item.confidence = 0
        }
      } else {
        item.value = '(提取失败)'
        item.status = 'error'
        item.confidence = 0
      }
    } catch {
      item.value = '(提取失败)'
      item.status = 'error'
      item.confidence = 0
    }
  }

  loading.value = false
  step.value = 'fill'
  const ok = fieldList.value.filter(f => f.status === 'success').length
  ElMessage.success(`提取完成：${ok}/${fieldList.value.length} 个字段成功`)
}

// ── 智能回填（直接用 source_file_ids，让 LLM 自动填表） ──
async function handleSmartFill() {
  if (!templateFileId.value) {
    ElMessage.warning('缺少模板文件 ID')
    return
  }
  if (sourceFileIds.value.length === 0) {
    ElMessage.warning('请至少选择一个数据来源文档')
    return
  }

  loading.value = true
  step.value = 'fill'
  errorMsg.value = ''

  try {
    const res = await fetch('/api/fill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId.value,
        source_file_ids: sourceFileIds.value,
        max_rows: 10,
      })
    })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '智能回填失败')

    outputFileId.value = data.output_file_id
    downloadUrl.value = data.download_url
    step.value = 'done'
    progress.value.done = true
    ElMessage.success('智能回填成功！可下载文档')
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('回填失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// ── 执行回填 ────────────────────────────────────────────────
async function handleFill() {
  if (!templateFileId.value) {
    ElMessage.warning('缺少模板文件 ID')
    return
  }

  loading.value = true
  step.value = 'fill'
  errorMsg.value = ''

  const answers = fieldList.value
    .filter(f => f.status !== 'pending' && f.status !== 'extracting')
    .map(f => ({
      field_name: f.field,
      value: f.value === '(未找到)' || f.value === '(提取失败)' ? '' : f.value,
    }))

  try {
    const res = await fetch('/api/fill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId.value,
        answers,
      })
    })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '回填失败')

    outputFileId.value = data.output_file_id
    downloadUrl.value = data.download_url
    step.value = 'done'
    progress.value.done = true
    ElMessage.success('回填成功！可下载文档')
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('回填失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// ── 下载 ─────────────────────────────────────────────────────
function handleDownload() {
  if (downloadUrl.value) {
    // downloadUrl 形如 /download/{id}，加 /api 前缀走 Vite 代理转发到后端
    const url = downloadUrl.value.startsWith('/api')
      ? downloadUrl.value
      : '/api' + downloadUrl.value
    window.open(url, '_blank')
  }
}

// ── 重置 ─────────────────────────────────────────────────────
function handleReset() {
  templateFile.value = null
  templateFileId.value = ''
  selectedTemplateId.value = ''
  fieldList.value = []
  sourceFileIds.value = []
  outputFileId.value = ''
  downloadUrl.value = ''
  errorMsg.value = ''
  step.value = 'upload'
  progress.value = { upload: false, parse: false, extract: false, fill: false, done: false }
}
</script>

<template>
  <div class="space-y-6">

    <!-- 页面标题 -->
    <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l">
      Word / Excel 模板自动回填
    </div>

    <!-- 步骤条 -->
    <div class="flex items-center gap-0 text-xs">
      <div v-for="(label, key, i) in { upload:'① 上传模板', parse:'② 解析字段', extract:'③ 提取值', fill:'④ 回填', done:'⑤ 完成' }" :key="key"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-full border"
        :class="step === key ? 'bg-accent text-white border-accent' : 'bg-white text-muted border-border'">
        <span>{{ label }}</span>
      </div>
    </div>

    <!-- ── ① 上传模板 ── -->
    <div class="grid grid-cols-12 gap-6">
      <!-- 左侧：上传 -->
      <div class="col-span-5">
        <div class="mb-3 flex items-center gap-4 text-xs">
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" v-model="useExisting" :value="false" class="accent-accent" />
            上传新模板
          </label>
          <label v-if="indexedFiles.length > 0" class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" v-model="useExisting" :value="true" class="accent-accent" />
            用历史文件作模板
          </label>
        </div>

        <!-- 上传新模板 -->
        <div v-if="!useExisting">
          <label class="block text-sm font-medium text-text2 mb-2">上传 Word / Excel 模板</label>
          <label class="bg-white border-2 border-dashed border-border rounded-lg p-8 flex flex-col items-center justify-center hover:border-accent transition-colors cursor-pointer text-center">
            <div class="text-4xl mb-2">📄</div>
            <div class="text-xs text-text2">点击或拖拽上传</div>
            <div class="text-xs text-muted mt-1">.docx / .xlsx</div>
            <div v-if="templateFile" class="mt-2 px-2 py-1 bg-accent/10 text-accent text-xs rounded">
              {{ templateFile.name }}
            </div>
            <input type="file" class="hidden" accept=".docx,.xlsx"
              @change="(e) => templateFile = (e.target as HTMLInputElement).files?.[0] || null" />
          </label>
          <button
            @click="handleUploadTemplate"
            :disabled="!templateFile"
            class="mt-3 w-full px-4 py-2 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-40 transition-colors text-sm"
          >
            上传并解析占位符 →
          </button>
        </div>

        <!-- 历史模板 -->
        <div v-else>
          <label class="block text-sm font-medium text-text2 mb-2">选择已有文档作为模板</label>
          <select v-model="selectedTemplateId" class="w-full px-3 py-2 bg-white border border-border rounded-md text-sm text-text">
            <option value="">-- 选择 --</option>
            <option v-for="f in templateList" :key="f.file_id" :value="f.file_id">
              {{ f.filename }} ({{ f.file_id.slice(0, 8) }})
            </option>
          </select>
          <button
            @click="handleSelectExisting"
            :disabled="!selectedTemplateId"
            class="mt-3 w-full px-4 py-2 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-40 transition-colors text-sm"
          >
            解析占位符 →
          </button>
        </div>
      </div>

      <!-- 右侧：已解析字段预览 -->
      <div class="col-span-7">
        <div v-if="fieldList.length > 0">
          <div class="flex items-center justify-between mb-2">
            <div class="text-xs font-bold text-muted uppercase tracking-wider">
              已识别待填字段（共 {{ fieldList.length }} 个）
            </div>
            <div class="text-xs text-muted">
              字段值状态：
              <span class="text-green font-semibold">{{ fieldList.filter(f=>f.status==='success').length }}</span> 成功 ·
              <span class="text-yellow-600 font-semibold">{{ fieldList.filter(f=>f.status==='warning').length }}</span> 未找到 ·
              <span class="text-red font-semibold">{{ fieldList.filter(f=>f.status==='error').length }}</span> 失败
            </div>
          </div>

          <div class="bg-white border border-border rounded-lg overflow-hidden">
            <table class="w-full text-xs">
              <thead>
                <tr class="bg-surface2 border-b border-border">
                  <th class="px-3 py-2 text-left font-semibold text-text2 w-8">#</th>
                  <th class="px-3 py-2 text-left font-semibold text-text2">占位符</th>
                  <th class="px-3 py-2 text-left font-semibold text-text2">提取结果</th>
                  <th class="px-3 py-2 text-left font-semibold text-text2 w-16">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(f, i) in fieldList" :key="i" class="border-b border-border-l last:border-0 hover:bg-surface2">
                  <td class="px-3 py-2 text-muted">{{ i + 1 }}</td>
                  <td class="px-3 py-2">
                    <code class="bg-surface2 px-1.5 py-0.5 rounded text-accent">{{ f.field }}</code>
                  </td>
                  <td class="px-3 py-2">
                    <div v-if="f.status === 'success'" class="flex items-center gap-2">
                      <span class="text-text">{{ f.value }}</span>
                      <span class="text-xs" :class="getConfColor(f.confidence)">{{ f.confidence }}%</span>
                    </div>
                    <span v-else-if="f.status === 'extracting'" class="text-accent">⏳ 提取中...</span>
                    <span v-else-if="f.status === 'warning'" class="text-yellow-600">⚠ {{ f.value || '(未找到)' }}</span>
                    <span v-else-if="f.status === 'error'" class="text-red">{{ f.value || '(失败)' }}</span>
                    <span v-else class="text-muted">○ 待提取</span>
                  </td>
                  <td class="px-3 py-2">
                    <span :class="getStatusColor(f.status)">{{ getStatusIcon(f.status) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 暂无字段 -->
        <div v-else class="h-full flex items-center justify-center border-2 border-dashed border-border rounded-lg p-8 text-center text-muted text-sm">
          <div>
            <div class="text-3xl mb-2">📋</div>
            <div>上传模板后自动解析占位符</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── ② 选数据来源 ── -->
    <div v-if="fieldList.length > 0">
      <div class="text-xs font-bold tracking-widest text-muted uppercase pb-2.5 border-b border-border-l mb-4">
        选择数据来源（已入库文档）
      </div>
      <div class="flex flex-wrap gap-2 mb-3">
        <label
          v-for="f in indexedFiles" :key="f.file_id"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs cursor-pointer transition-colors"
          :class="sourceFileIds.includes(f.file_id)
            ? 'bg-accent/10 border-accent text-accent'
            : 'bg-white border-border text-text2 hover:border-accent'"
        >
          <input type="checkbox" :value="f.file_id" v-model="sourceFileIds" class="hidden" />
          {{ f.filename }} ({{ f.chunk_count }}块)
        </label>
        <div v-if="indexedFiles.length === 0" class="text-xs text-muted">
          暂无已入库文档，请先在「上传」页面解析文档
        </div>
      </div>
      <div class="text-xs text-muted">
        已选：{{ sourceFileIds.length }} 个文档 |
        <button @click="sourceFileIds = indexedFiles.map(f => f.file_id)"
          class="text-accent hover:underline ml-1">全选</button> |
        <button @click="sourceFileIds = []" class="text-accent hover:underline">清除</button>
      </div>
    </div>

    <!-- ── ③ 提取 & 回填按钮 ── -->
    <div v-if="fieldList.length > 0" class="flex gap-3 flex-wrap">
      <button
        @click="handleExtractAll"
        :disabled="loading || sourceFileIds.length === 0"
        class="px-5 py-2.5 bg-accent text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-40 transition-colors"
      >
        {{ loading ? '⏳ 提取中...' : '🔍 从文档中提取全部字段值' }}
      </button>

      <button
        @click="handleSmartFill"
        :disabled="loading || sourceFileIds.length === 0"
        class="px-5 py-2.5 bg-purple-600 text-white font-medium rounded-md hover:bg-purple-700 disabled:opacity-40 transition-colors"
        title="LLM 自动读取模板表头并从数据源提取数据，无需逐字段提取"
      >
        {{ loading ? '⏳ 智能回填中...' : '🤖 智能回填（推荐）' }}
      </button>

      <button
        @click="handleFill"
        :disabled="loading || !allFieldsReady"
        class="px-5 py-2.5 bg-green text-white font-medium rounded-md hover:bg-green-600 disabled:opacity-40 transition-colors"
        title="所有字段提取完成后可回填"
      >
        ✓ 回填模板并下载
      </button>

      <button
        @click="handleReset"
        class="px-4 py-2.5 bg-surface text-text2 font-medium rounded-md border border-border hover:bg-surface2 transition-colors text-sm"
      >
        重新开始
      </button>
    </div>

    <!-- ── ④ 完成 ── -->
    <div v-if="step === 'done'" class="bg-green/5 border border-green/30 rounded-lg p-6 space-y-4">
      <div class="flex items-center gap-3">
        <span class="text-4xl">🎉</span>
        <div>
          <div class="text-base font-bold text-green">回填完成！</div>
          <div class="text-xs text-muted mt-0.5">文档已生成，点击下载</div>
        </div>
      </div>
      <div class="bg-white border border-border rounded p-3 space-y-1 text-xs text-text2">
        <div>输出 ID：<span class="font-mono text-accent">{{ outputFileId }}</span></div>
        <div>填充字段：{{ fieldList.filter(f=>f.status==='success').length }} / {{ fieldList.length }}</div>
      </div>
      <div class="flex gap-3">
        <button @click="handleDownload"
          class="flex-1 px-4 py-3 bg-accent text-white font-medium rounded-md hover:bg-blue-600 transition-colors flex items-center justify-center gap-2">
          ⬇️ 下载回填文档
        </button>
        <button @click="handleReset"
          class="flex-1 px-4 py-3 bg-white text-text2 font-medium rounded-md border border-border hover:bg-surface2 transition-colors">
          新建任务
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="bg-red/5 border border-red/30 rounded p-3 text-xs text-red">
      {{ errorMsg }}
    </div>

  </div>
</template>

<style scoped>
</style>
