import { defineStore } from 'pinia'
import { ref } from 'vue'

// ── 类型定义（与 Query.vue 保持一致） ───────────────────────
export interface Evidence {
  filename: string
  page: number
  content: string
  relevance: number
  confidence: number
}

export interface ConflictDetail {
  description?: string
  field?: string
  values?: string[]
}

export interface QueryResult {
  answer: string
  confidence: number
  sources: Evidence[]
  hasConflicts: boolean
  conflictCount: number
  conflictDetails: ConflictDetail[]
  explanation: {
    why: string
    alternatives: string
    credibility: string
  }
}

export interface FileItem {
  file_id: string
  filename: string
  status: string
}

// ── Store 定义 ───────────────────────────────────────────────
export const useQueryStore = defineStore(
  'query',
  () => {
    // 上次的问答输入
    const lastQuery = ref('')
    // 上次选中的文件 ID 列表
    const selectedFileIds = ref<string[]>([])
    // 上次的问答结果（切 tab 后保留）
    const lastResult = ref<QueryResult | null>(null)
    // 已索引文件列表缓存
    const filesList = ref<FileItem[]>([])

    function setQuery(q: string) {
      lastQuery.value = q
    }

    function setSelectedFileIds(ids: string[]) {
      selectedFileIds.value = ids
    }

    function setResult(r: QueryResult | null) {
      lastResult.value = r
    }

    function setFilesList(list: FileItem[]) {
      filesList.value = list
    }

    function clearResult() {
      lastResult.value = null
    }

    return {
      lastQuery,
      selectedFileIds,
      lastResult,
      filesList,
      setQuery,
      setSelectedFileIds,
      setResult,
      setFilesList,
      clearResult,
    }
  },
  {
    // 借助 pinia-plugin-persistedstate 把状态持久化到 sessionStorage
    // 用 sessionStorage 而不是 localStorage：关闭浏览器后自动清除，不会带着旧数据跨会话
    persist: {
      storage: sessionStorage,
      // 只持久化问答输入和结果，文件列表每次重新从后端拉取
      pick: ['lastQuery', 'selectedFileIds', 'lastResult'],
    },
  }
)
