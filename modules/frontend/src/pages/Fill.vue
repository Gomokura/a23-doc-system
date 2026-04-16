<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
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
  values: string[]      // 支持多行值
  value: string         // 单行预览显示用（取 values.join(', ') 的前100字符）
  status: 'pending' | 'extracting' | 'success' | 'warning' | 'error'
  confidence: number
  editing: boolean      // 是否处于编辑模式
}

// ── 状态 ────────────────────────────────────────────────────
const templateFile = ref<File | null>(null)
const templateFileId = ref('')
const templateList = ref<FileRecord[]>([])
const useExisting = ref(false)
const selectedTemplateId = ref('')

const fieldList = ref<FieldItem[]>([])
const sourceFileIds = ref<string[]>([])
const userInstruction = ref('')     // 用户自定义筛选条件
const maxRows = ref(50)             // 最多提取行数（预览用）
const fillRows = ref(0)             // 回填行数（0=不限制）
const loading = ref(false)
const step = ref<'upload'|'parse'|'extract'|'preview'|'fill'|'done'>('upload')

const outputFileId = ref('')
const downloadUrl = ref('')
const errorMsg = ref('')

// 预览数据（智能回填第一步）
const previewFields = ref<Array<{field_name: string, values: string[], method: string}>>([])
const showPreview = ref(false)

// ── 生命周期 ────────────────────────────────────────────────
onMounted(loadFileList)

onActivated(async () => {
  await loadFileList()
  // 清掉已被删除的 sourceFileIds
  const validIds = new Set(templateList.value.map(f => f.file_id))
  sourceFileIds.value = sourceFileIds.value.filter(id => validIds.has(id))
})

// ── 工具函数 ────────────────────────────────────────────────
const getStatusIcon = (s: string) =>
  s === 'success' ? '✓' : s === 'extracting' ? '⏳' : s === 'warning' ? '⚠' : s === 'error' ? '✕' : '○'

const getStatusColor = (s: string) =>
  s === 'success' ? 'text-green-600' :
  s === 'extracting' ? 'text-blue-500' :
  s === 'warning' ? 'text-yellow-600' :
  s === 'error' ? 'text-red-500' : 'text-gray-400'

const indexedFiles = computed(() =>
  templateList.value.filter(f => f.status === 'indexed')
)

const allFieldsReady = computed(() =>
  fieldList.value.length > 0 && fieldList.value.every(f => f.status !== 'pending' && f.status !== 'extracting')
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

  loading.value = true
  step.value = 'parse'
  fieldList.value = []
  errorMsg.value = ''
  showPreview.value = false

  try {
    const fd = new FormData()
    fd.append('file', templateFile.value)
    const upRes = await fetch('/api/upload', { method: 'POST', body: fd })
    const upData = (await parseResponseJson(upRes)) as Record<string, any>
    if (!upRes.ok) throw new Error(upData.detail || '上传失败')

    templateFileId.value = upData.file_id

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
        field: f, values: [], value: '', status: 'pending' as const,
        confidence: 0, editing: false,
      }))
      ElMessage.success(`${methodLabel}完成，找到 ${parseData.fields.length} 个待填字段`)
    }
    step.value = 'extract'
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error(e.message)
    step.value = 'upload'
  } finally {
    loading.value = false
  }
}

// ── 从历史模板解析占位符 ────────────────────────────────────
async function handleSelectExisting() {
  if (!selectedTemplateId.value) { ElMessage.warning('请先选择一个模板'); return }

  loading.value = true
  fieldList.value = []
  errorMsg.value = ''
  showPreview.value = false

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
    } else {
      const methodLabel = parseData.method === 'llm' ? 'AI智能识别' : '占位符解析'
      fieldList.value = parseData.fields.map((f: string) => ({
        field: f, values: [], value: '', status: 'pending' as const,
        confidence: 0, editing: false,
      }))
      templateFileId.value = selectedTemplateId.value
      ElMessage.success(`${methodLabel}完成，找到 ${parseData.fields.length} 个待填字段`)
    }
    step.value = 'extract'
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// ── 全量提取字段值（逐字段调 /ask） ──────────────────────────
async function handleExtractAll() {
  if (fieldList.value.length === 0) { ElMessage.warning('没有可提取的字段'); return }
  if (sourceFileIds.value.length === 0) { ElMessage.warning('请至少选择一个数据来源文档'); return }

  loading.value = true
  step.value = 'extract'
  errorMsg.value = ''

  const pending = fieldList.value.filter(f => f.status === 'pending')
  for (const item of pending) {
    item.status = 'extracting'
    try {
      const query = userInstruction.value.trim()
        ? `从文档中提取"${item.field}"的值，条件：${userInstruction.value}，只输出值本身`
        : `从文档中提取"${item.field}"的值，只输出值本身`

      const askRes = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, file_ids: sourceFileIds.value, scenario: 'extract' })
      })
      const askData = (await parseResponseJson(askRes)) as Record<string, any>

      if (askRes.ok && askData.answer) {
        const raw = askData.answer
          .replace(/^(回答|值|答案|提取结果)[：:]\s*/g, '')
          .replace(/\n来源[：:][\s\S]*/g, '')
          .replace(/\[文档\d+\]/g, '')
          .trim().slice(0, 200)

        if (raw && raw !== '(无)' && raw !== '未知' && !raw.includes('无法回答')) {
          item.values = [raw]
          item.value = raw
          item.confidence = Math.round((askData.confidence || 0.6) * 100)
          item.status = 'success'
        } else {
          item.value = '(未找到)'; item.values = []; item.status = 'warning'; item.confidence = 0
        }
      } else {
        item.value = '(提取失败)'; item.values = []; item.status = 'error'; item.confidence = 0
      }
    } catch {
      item.value = '(提取失败)'; item.values = []; item.status = 'error'; item.confidence = 0
    }
  }

  loading.value = false
  step.value = 'fill'
  const ok = fieldList.value.filter(f => f.status === 'success').length
  ElMessage.success(`提取完成：${ok}/${fieldList.value.length} 个字段成功`)
}

// ── 智能回填预览（第一步：调 /fill/preview，展示结果供确认） ──
async function handleSmartPreview() {
  if (!templateFileId.value) { ElMessage.warning('缺少模板文件 ID'); return }
  if (sourceFileIds.value.length === 0) { ElMessage.warning('请至少选择一个数据来源文档'); return }

  loading.value = true
  step.value = 'preview'
  errorMsg.value = ''
  showPreview.value = false

  try {
    const res = await fetch('/api/fill/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId.value,
        source_file_ids: sourceFileIds.value,
        max_rows: 99999,
        user_instruction: userInstruction.value.trim(),
      })
    })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) {
      if (res.status === 409) throw new Error('部分数据源文档尚未完成解析，请先在「上传」页面解析')
      throw new Error(data.detail || '预览提取失败')
    }

    // 全量存入 previewFields，前端展示时按 maxRows 截断
    previewFields.value = (data.fields || []).map((f: any) => ({
      field_name: f.field_name,
      values: Array.isArray(f.values) ? f.values : [String(f.values ?? '')],
      method: f.method || 'llm',
    }))
    showPreview.value = true
    const totalRows = previewFields.value[0]?.values?.length ?? 0
    ElMessage.success(`预览完成，共提取 ${previewFields.value.length} 个字段 / ${totalRows} 行`)
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('预览失败：' + e.message)
    step.value = 'extract'
  } finally {
    loading.value = false
  }
}

// ── 智能回填确认（第二步：用预览数据直接写入文件） ──────────────
async function handleSmartFillConfirm() {
  if (!templateFileId.value || previewFields.value.length === 0) return

  loading.value = true
  errorMsg.value = ''

  try {
    const answers = previewFields.value.map(f => ({
      field_name: f.field_name,
      values: f.values,
    }))

    const res = await fetch('/api/fill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId.value,
        answers,
        source_file_ids: sourceFileIds.value,
        user_instruction: userInstruction.value,
      })
    })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '回填失败')

    outputFileId.value = data.output_file_id
    downloadUrl.value = data.download_url
    step.value = 'done'
    showPreview.value = false
    ElMessage.success('回填完成！可下载文档')
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('回填失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// ── 全自动智能回填（不预览，直接生成文件） ──────────────────
async function handleSmartFillDirect() {
  if (!templateFileId.value) { ElMessage.warning('缺少模板文件 ID'); return }
  if (sourceFileIds.value.length === 0) { ElMessage.warning('请至少选择一个数据来源文档'); return }

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
        max_rows: maxRows.value,
        fill_rows: fillRows.value,
        user_instruction: userInstruction.value.trim(),
      })
    })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) {
      if (res.status === 409) throw new Error('部分数据源文档尚未完成解析，请先解析后再试')
      throw new Error(data.detail || '智能回填失败')
    }

    outputFileId.value = data.output_file_id
    downloadUrl.value = data.download_url
    step.value = 'done'
    ElMessage.success('智能回填成功！可下载文档')
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('回填失败：' + e.message)
    step.value = 'extract'
  } finally {
    loading.value = false
  }
}

// ── 执行回填（用逐字段提取结果） ──────────────────────────────
async function handleFill() {
  if (!templateFileId.value) { ElMessage.warning('缺少模板文件 ID'); return }

  loading.value = true
  step.value = 'fill'
  errorMsg.value = ''

  const answers = fieldList.value
    .filter(f => f.status === 'success')
    .map(f => ({
      field_name: f.field,
      values: f.values.length > 0 ? f.values : [f.value],
    }))

  try {
    const res = await fetch('/api/fill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_file_id: templateFileId.value,
        answers,
        source_file_ids: sourceFileIds.value,
        user_instruction: userInstruction.value,
      })
    })
    const data = (await parseResponseJson(res)) as Record<string, any>
    if (!res.ok) throw new Error(data.detail || '回填失败')

    outputFileId.value = data.output_file_id
    downloadUrl.value = data.download_url
    step.value = 'done'
    ElMessage.success('回填成功！可下载文档')
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('回填失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// 预览横表：展示行数 = min(全量行数, maxRows)，全量数据仍保留在 previewFields 供确认时写入
const previewRowCount = computed(() => {
  if (previewFields.value.length === 0) return 0
  const total = Math.max(...previewFields.value.map(f => f.values.length), 0)
  return Math.min(total, maxRows.value)
})

// 设置某字段某行的值（确保 values 数组足够长）
function setPreviewCell(fieldIdx: number, rowIdx: number, val: string) {
  const f = previewFields.value[fieldIdx]
  while (f.values.length <= rowIdx) f.values.push('')
  f.values[rowIdx] = val
}

// 删除某数据行（对所有字段同步删除同一行索引）
function removePreviewRow(rowIdx: number) {
  for (const f of previewFields.value) {
    if (rowIdx < f.values.length) f.values.splice(rowIdx, 1)
  }
}

// 在末尾追加一行（所有字段 values 各 push 一个空串）
function addPreviewRow() {
  for (const f of previewFields.value) {
    f.values.push('')
  }
}
function handleDownload() {
  if (!downloadUrl.value) return
  const url = downloadUrl.value.startsWith('/api') ? downloadUrl.value : '/api' + downloadUrl.value
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
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
  userInstruction.value = ''
  maxRows.value = 50
  fillRows.value = 0
  step.value = 'upload'
  showPreview.value = false
  previewFields.value = []
}
</script>

<template>
  <div class="fill-page">

    <!-- 页面头部 -->
    <div class="fill-header">
      <div class="fill-header-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="3" width="18" height="18" rx="3"/>
          <path d="M7 8h10M7 12h7M7 16h5"/>
          <circle cx="19" cy="19" r="4" fill="#3b82f6" stroke="none"/>
          <path d="M17.5 19l1 1 2-2" stroke="#fff" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="fill-header-text">
        <h2>表格回填</h2>
        <p>上传 Word / Excel 模板，从文档中智能提取数据并自动填写</p>
      </div>
      <div class="fill-steps">
        <div v-for="(label, key) in { upload:'上传模板', parse:'解析字段', extract:'配置提取', preview:'预览确认', done:'完成' }"
          :key="key"
          class="fill-step"
          :class="step === key ? 'fill-step--active' : ''">
          <span class="fill-step-dot"></span>
          <span class="fill-step-label">{{ label }}</span>
        </div>
      </div>
    </div>

    <!-- 主体两栏 -->
    <div class="fill-body">

      <!-- 左栏 -->
      <div class="fill-left">

        <!-- Panel 01: 上传模板 -->
        <div class="fill-panel">
          <div class="panel-label">01 上传模板</div>
          <div class="radio-row">
            <label class="radio-opt">
              <input type="radio" v-model="useExisting" :value="false" />
              上传新模板
            </label>
            <label v-if="templateList.length > 0" class="radio-opt">
              <input type="radio" v-model="useExisting" :value="true" />
              用历史文件
            </label>
          </div>

          <div v-if="!useExisting">
            <label class="upload-zone">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="upload-zone-icon">
                <path d="M12 16V8m0 0l-3 3m3-3l3 3"/>
                <path d="M20 16.7A5 5 0 0018 7h-1.26A8 8 0 104 15.25"/>
              </svg>
              <span class="upload-zone-text">点击或拖拽上传</span>
              <span class="upload-zone-sub">.docx / .xlsx</span>
              <span v-if="templateFile" class="upload-zone-file">{{ templateFile.name }}</span>
              <input type="file" class="hidden" accept=".docx,.xlsx"
                @change="(e) => templateFile = (e.target as HTMLInputElement).files?.[0] || null" />
            </label>
            <button @click="handleUploadTemplate" :disabled="!templateFile || loading" class="btn-primary btn-full">
              {{ loading ? '处理中...' : '上传并解析字段 →' }}
            </button>
          </div>

          <div v-else>
            <select v-model="selectedTemplateId" class="fill-select">
              <option value="">-- 选择已有文件 --</option>
              <option v-for="f in templateList" :key="f.file_id" :value="f.file_id">{{ f.filename }}</option>
            </select>
            <button @click="handleSelectExisting" :disabled="!selectedTemplateId || loading" class="btn-primary btn-full" style="margin-top:10px">
              解析字段 →
            </button>
          </div>
        </div>

        <!-- Panel 02: 字段列表 -->
        <div class="fill-panel fill-panel--grow">
          <div class="panel-label">02 识别字段</div>
          <div v-if="fieldList.length > 0">
            <div class="field-stats">
              <span>共 {{ fieldList.length }} 个字段</span>
              <span class="stat-ok">{{ fieldList.filter(f=>f.status==='success').length }} 成功</span>
              <span class="stat-warn">{{ fieldList.filter(f=>f.status==='warning').length }} 未找到</span>
              <span class="stat-err">{{ fieldList.filter(f=>f.status==='error').length }} 失败</span>
            </div>
            <div class="field-table-wrap">
              <table class="field-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>字段名</th>
                    <th>提取值</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(f, i) in fieldList" :key="i">
                    <td class="td-num">{{ i + 1 }}</td>
                    <td><code class="field-code">{{ f.field }}</code></td>
                    <td>
                      <input v-if="f.status === 'success' || f.editing"
                        v-model="f.value"
                        @blur="f.editing = false; f.values = f.value ? [f.value] : []"
                        @focus="f.editing = true"
                        class="field-input" placeholder="可手动输入..." />
                      <span v-else-if="f.status === 'extracting'" class="tag-extracting">提取中...</span>
                      <span v-else-if="f.status === 'warning'" class="tag-warn">未找到</span>
                      <span v-else-if="f.status === 'error'" class="tag-err">失败</span>
                      <button v-else @click="f.editing = true; f.status = 'success'" class="link-btn">手动输入</button>
                    </td>
                    <td class="td-status">
                      <span :class="getStatusColor(f.status)">{{ getStatusIcon(f.status) }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="field-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <path d="M7 8h10M7 12h6M7 16h4"/>
            </svg>
            <span>上传模板后自动识别待填字段</span>
          </div>
        </div>

      </div><!-- /fill-left -->

      <!-- 右栏 -->
      <div class="fill-right">

    <!-- 空态引导 -->
    <div v-if="fieldList.length === 0" class="right-empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="width:48px;height:48px;color:#cbd5e1">
        <path d="M9 12h6M9 16h4M7 4H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V8l-5-4H7z"/>
        <path d="M14 4v4h4"/>
      </svg>
      <p style="font-size:13px;color:#94a3b8;margin:8px 0 4px">请先上传并解析模板</p>
      <p style="font-size:11px;color:#cbd5e1">解析完成后，在此配置数据来源并执行回填</p>
    </div>

    <!-- ── ② 数据来源 + 填表条件 ── -->
    <div v-if="fieldList.length > 0" class="space-y-3">
      <div class="text-xs font-bold tracking-widest text-gray-400 uppercase pb-2 border-b border-gray-100">
        数据来源 & 填表条件
      </div>

      <!-- 文档选择 -->
      <div class="flex flex-wrap gap-2">
        <label
          v-for="f in indexedFiles" :key="f.file_id"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs cursor-pointer transition-colors"
          :class="sourceFileIds.includes(f.file_id)
            ? 'bg-blue-50 border-blue-400 text-blue-600'
            : 'bg-white border-gray-200 text-gray-600 hover:border-blue-400'"
        >
          <input type="checkbox" :value="f.file_id" v-model="sourceFileIds" class="hidden" />
          {{ f.filename }} ({{ f.chunk_count }}块)
        </label>
        <div v-if="indexedFiles.length === 0" class="text-xs text-gray-400">
          暂无已索引文档，请先在「上传」页解析
        </div>
      </div>

      <div class="flex items-center gap-3 text-xs text-gray-400">
        已选 {{ sourceFileIds.length }} 个 |
        <button @click="sourceFileIds = indexedFiles.map(f => f.file_id)" class="text-blue-500 hover:underline">全选</button> |
        <button @click="sourceFileIds = []" class="text-blue-500 hover:underline">清除</button>
        <span class="ml-4">预览行数：</span>
        <input type="number" v-model.number="maxRows" min="1" max="500"
          class="w-16 px-2 py-0.5 border border-gray-200 rounded text-xs text-center" />
        <span class="ml-2">回填行数：</span>
        <select v-model.number="fillRows" class="w-16 px-1 py-0.5 border border-gray-200 rounded text-xs text-center">
          <option :value="0">全部</option>
          <option :value="10">10</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="500">500</option>
        </select>
      </div>

      <!-- 用户自定义筛选条件 -->
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">
          填表条件（可选）
          <span class="text-gray-400 font-normal ml-1">— 例如：只提取国家为中国和美国的数据 / 金额大于10万的记录</span>
        </label>
        <input
          v-model="userInstruction"
          type="text"
          placeholder="不填则提取全部数据，支持自然语言描述筛选条件..."
          class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-300 transition-colors"
        />
      </div>
    </div>

    <!-- ── ③ 操作按钮 ── -->
    <div v-if="fieldList.length > 0" class="flex gap-3 flex-wrap items-center">
      <!-- 智能预览（推荐两步走） -->
      <button
        @click="handleSmartPreview"
        :disabled="loading || sourceFileIds.length === 0"
        class="px-5 py-2.5 bg-purple-600 text-white font-medium rounded-md hover:bg-purple-700 disabled:opacity-40 transition-colors text-sm"
        title="先预览提取结果，确认后再生成文件"
      >
        {{ loading && step === 'preview' ? '⏳ 提取预览中...' : '🔍 智能预览（推荐）' }}
      </button>

      <!-- 逐字段提取 -->
      <button
        @click="handleExtractAll"
        :disabled="loading || sourceFileIds.length === 0"
        class="px-5 py-2.5 bg-blue-500 text-white font-medium rounded-md hover:bg-blue-600 disabled:opacity-40 transition-colors text-sm"
      >
        {{ loading && step === 'extract' ? '⏳ 提取中...' : '📋 逐字段提取' }}
      </button>

      <!-- 直接回填（不预览） -->
      <button
        @click="handleSmartFillDirect"
        :disabled="loading || sourceFileIds.length === 0"
        class="px-5 py-2.5 bg-gray-600 text-white font-medium rounded-md hover:bg-gray-700 disabled:opacity-40 transition-colors text-sm"
        title="直接生成文件，不显示预览"
      >
        {{ loading && step === 'fill' ? '⏳ 回填中...' : '⚡ 直接回填' }}
      </button>

      <!-- 用提取结果回填 -->
      <button
        v-if="allFieldsReady"
        @click="handleFill"
        :disabled="loading"
        class="px-5 py-2.5 bg-green-600 text-white font-medium rounded-md hover:bg-green-700 disabled:opacity-40 transition-colors text-sm"
      >
        ✓ 用提取结果回填
      </button>

      <button @click="handleReset" class="px-4 py-2.5 bg-white text-gray-500 font-medium rounded-md border border-gray-200 hover:bg-gray-50 transition-colors text-sm">
        重新开始
      </button>
    </div>

    <!-- ── ④ 预览面板（横表格式：表头一行 + 数据多行，与模板格式对齐） ── -->
    <div v-if="showPreview && previewFields.length > 0" class="border border-purple-200 rounded-lg overflow-hidden">
      <div class="bg-purple-50 px-4 py-3 flex items-center justify-between">
        <div class="font-semibold text-purple-700 text-sm">
          🔍 预览：{{ previewFields.length }} 个字段，共
          {{ previewRowCount }} 行数据
          <span class="text-xs font-normal text-purple-500 ml-2">（可直接编辑单元格，双击行末 ＋ 可添加行）</span>
        </div>
        <div class="flex gap-2">
          <button
            @click="handleSmartFillConfirm"
            :disabled="loading"
            class="px-4 py-1.5 bg-purple-600 text-white text-sm font-medium rounded hover:bg-purple-700 disabled:opacity-40"
          >
            {{ loading ? '⏳ 生成中...' : '✓ 确认并生成文件' }}
          </button>
          <button @click="showPreview = false" class="px-3 py-1.5 bg-white border border-gray-200 text-gray-500 text-sm rounded hover:bg-gray-50">
            取消
          </button>
        </div>
      </div>

      <!-- 横表：第一行 = 所有字段名（表头），后续行 = 数据 -->
      <div class="overflow-x-auto max-h-96 overflow-y-auto">
        <table class="text-xs border-collapse min-w-full">
          <!-- 表头行：字段名 -->
          <thead class="sticky top-0 z-10">
            <tr class="bg-purple-100">
              <th class="px-2 py-2 text-left font-semibold text-purple-700 border border-purple-200 w-8 shrink-0">#</th>
              <th
                v-for="(f, fi) in previewFields"
                :key="fi"
                class="px-3 py-2 text-left font-semibold text-purple-700 border border-purple-200 whitespace-nowrap min-w-[100px]"
              >
                {{ f.field_name }}
                <span class="ml-1 font-normal text-purple-400 text-[10px]">
                  {{ f.method === 'llm' ? '(AI)' : '(直读)' }}
                </span>
              </th>
              <!-- 操作列 -->
              <th class="px-2 py-2 border border-purple-200 w-12"></th>
            </tr>
          </thead>
          <tbody>
            <!-- 数据行：每行对应所有字段的同一 row_idx 的值 -->
            <tr
              v-for="ri in previewRowCount"
              :key="ri"
              class="hover:bg-purple-50 group"
            >
              <td class="px-2 py-1 text-gray-400 border border-gray-100 text-center">{{ ri }}</td>
              <td
                v-for="(f, fi) in previewFields"
                :key="fi"
                class="border border-gray-100 p-0"
              >
                <input
                  :value="f.values[ri - 1] ?? ''"
                  @input="setPreviewCell(fi, ri - 1, ($event.target as HTMLInputElement).value)"
                  class="w-full px-2 py-1.5 outline-none bg-transparent hover:bg-white focus:bg-white focus:ring-1 focus:ring-purple-300 transition-colors min-w-[80px]"
                  placeholder="—"
                />
              </td>
              <!-- 删除行按钮 -->
              <td class="border border-gray-100 text-center">
                <button
                  @click="removePreviewRow(ri - 1)"
                  class="text-red-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity px-1"
                  title="删除此行"
                >✕</button>
              </td>
            </tr>
            <!-- 空行提示 -->
            <tr v-if="previewRowCount === 0">
              <td :colspan="previewFields.length + 2" class="px-4 py-6 text-center text-gray-400 italic">
                未提取到任何数据行
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 添加行按钮 -->
      <div class="px-4 py-2 bg-gray-50 border-t border-gray-100">
        <button
          @click="addPreviewRow"
          class="text-purple-500 hover:text-purple-700 text-xs font-medium"
        >＋ 添加一行</button>
      </div>
    </div>

    <!-- ── ⑤ 完成 ── -->
    <div v-if="step === 'done'" class="bg-green-50 border border-green-200 rounded-lg p-5 space-y-4">
      <div class="flex items-center gap-3">
        <span class="text-4xl">🎉</span>
        <div>
          <div class="text-base font-bold text-green-700">回填完成！</div>
          <div class="text-xs text-gray-500 mt-0.5">文件已生成，点击下载按钮保存到本地</div>
        </div>
      </div>
      <div class="bg-white border border-gray-200 rounded p-3 text-xs text-gray-500 space-y-1">
        <div>输出 ID：<span class="font-mono text-blue-600">{{ outputFileId }}</span></div>
      </div>
      <div class="flex gap-3">
        <button @click="handleDownload"
          class="flex-1 px-4 py-3 bg-blue-500 text-white font-medium rounded-md hover:bg-blue-600 transition-colors flex items-center justify-center gap-2 text-sm">
          ⬇️ 下载回填文档
        </button>
        <button @click="handleReset"
          class="flex-1 px-4 py-3 bg-white text-gray-600 font-medium rounded-md border border-gray-200 hover:bg-gray-50 transition-colors text-sm">
          新建任务
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-600">
      ⚠ {{ errorMsg }}
    </div>

      </div><!-- /fill-right -->
    </div><!-- /fill-body -->
  </div>
</template>

<style scoped>
.fill-page { display: flex; flex-direction: column; gap: 16px; height: 100%; }

/* 头部 */
.fill-header { display: flex; align-items: center; gap: 12px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0; }
.fill-header-icon { width: 36px; height: 36px; background: linear-gradient(135deg,#1d4ed8,#3b82f6); border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.fill-header-icon svg { width: 20px; height: 20px; color: #fff; }
.fill-header-text h2 { font-size: 15px; font-weight: 700; color: #1e293b; margin: 0; }
.fill-header-text p  { font-size: 11px; color: #94a3b8; margin: 2px 0 0; }
.fill-steps { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.fill-step { display: flex; align-items: center; gap: 4px; font-size: 11px; color: #94a3b8; }
.fill-step-dot { width: 6px; height: 6px; border-radius: 50%; background: #cbd5e1; }
.fill-step--active .fill-step-dot { background: #1d4ed8; }
.fill-step--active .fill-step-label { color: #1d4ed8; font-weight: 600; }
.fill-step--done .fill-step-dot { background: #22c55e; }

/* 两栏布局 */
.fill-body { display: grid; grid-template-columns: 280px 1fr; gap: 16px; flex: 1; min-height: 0; }
.fill-left  { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.fill-right { display: flex; flex-direction: column; gap: 12px; min-height: 0; overflow-y: auto; }

/* 面板 */
.fill-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; }
.fill-panel--grow { flex: 1; min-height: 0; overflow-y: auto; }
.panel-label { font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }

/* 单选行 */
.radio-row { display: flex; gap: 14px; margin-bottom: 10px; }
.radio-opt { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #475569; cursor: pointer; }

/* 上传区 */
.upload-zone { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; border: 2px dashed #cbd5e1; border-radius: 10px; padding: 20px 12px; cursor: pointer; transition: border-color 0.15s; text-align: center; }
.upload-zone:hover { border-color: #3b82f6; }
.upload-zone-icon { width: 28px; height: 28px; color: #94a3b8; margin-bottom: 4px; }
.upload-zone-text { font-size: 12px; color: #475569; }
.upload-zone-sub  { font-size: 11px; color: #94a3b8; }
.upload-zone-file { font-size: 11px; color: #1d4ed8; background: #eff6ff; padding: 2px 8px; border-radius: 4px; margin-top: 4px; }

/* 按钮 */
.btn-primary { background: #1d4ed8; color: #fff; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: background 0.15s; }
.btn-primary:hover:not(:disabled) { background: #1e40af; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-full { width: 100%; margin-top: 10px; }

/* select */
.fill-select { width: 100%; padding: 7px 10px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 13px; color: #374151; outline: none; }

/* 字段统计 */
.field-stats { display: flex; gap: 10px; font-size: 11px; color: #64748b; margin-bottom: 8px; }
.stat-ok   { color: #16a34a; font-weight: 600; }
.stat-warn { color: #d97706; font-weight: 600; }
.stat-err  { color: #dc2626; font-weight: 600; }

/* 字段表格 */
.field-table-wrap { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; max-height: 260px; overflow-y: auto; }
.field-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.field-table thead tr { background: #f8fafc; }
.field-table th { padding: 7px 10px; text-align: left; font-weight: 600; color: #64748b; border-bottom: 1px solid #e2e8f0; }
.field-table td { padding: 5px 10px; border-bottom: 1px solid #f1f5f9; }
.field-table tr:last-child td { border-bottom: none; }
.field-table tr:hover td { background: #f8fafc; }
.td-num { color: #94a3b8; width: 28px; }
.td-status { text-align: center; width: 36px; }
.field-code { background: #f1f5f9; color: #1d4ed8; padding: 1px 6px; border-radius: 4px; font-size: 11px; }
.field-input { width: 100%; padding: 2px 6px; border: 1px solid #bfdbfe; border-radius: 4px; font-size: 12px; outline: none; }
.field-input:focus { border-color: #3b82f6; }
.tag-extracting { color: #3b82f6; font-size: 11px; }
.tag-warn { color: #d97706; font-size: 11px; }
.tag-err  { color: #dc2626; font-size: 11px; }
.link-btn { background: none; border: none; color: #94a3b8; font-size: 11px; cursor: pointer; text-decoration: underline; padding: 0; }
.link-btn:hover { color: #3b82f6; }

/* 字段空态 */
.field-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 32px; color: #94a3b8; font-size: 12px; border: 2px dashed #e2e8f0; border-radius: 10px; }
.field-empty svg { width: 32px; height: 32px; }

/* 右栏空态 */
.right-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; min-height: 200px; border: 2px dashed #e2e8f0; border-radius: 12px; text-align: center; padding: 40px; }
</style>
