<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Props { modelValue: number }
interface Emits { (e: 'update:modelValue', value: number): void }
defineProps<Props>()
const emit = defineEmits<Emits>()

const navItems = [
  { icon: 'upload', label: '文档上传', id: 0, desc: '上传并解析文档' },
  { icon: 'chat',   label: '智能问答', id: 1, desc: '多文档语义检索' },
  { icon: 'fill',   label: '表格回填', id: 2, desc: '自动填写模板' },
  { icon: 'edit',   label: '文档操作', id: 4, desc: '编辑与格式处理' },
  { icon: 'status', label: '系统状态', id: 3, desc: '索引与健康监控' },
]

const backendOk = ref(false)
let healthTimer: ReturnType<typeof setInterval> | null = null

async function checkHealth() {
  try {
    const res = await fetch('/api/health', { signal: AbortSignal.timeout(8000) })
    backendOk.value = res.ok
  } catch { backendOk.value = false }
}

onMounted(() => { checkHealth(); healthTimer = setInterval(checkHealth, 15000) })
onUnmounted(() => { if (healthTimer) clearInterval(healthTimer) })
</script>

<template>
  <aside class="sidebar">
    <!-- 导航菜单 -->
    <div class="sidebar-nav">
      <div class="nav-section-label">主菜单</div>
      <button
        v-for="item in navItems"
        :key="item.id"
        @click="emit('update:modelValue', item.id)"
        :class="['nav-item', modelValue === item.id && 'nav-item--active']"
      >
        <!-- 图标 -->
        <div class="nav-item-icon">
          <!-- upload -->
          <svg v-if="item.icon==='upload'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
          </svg>
          <!-- chat -->
          <svg v-if="item.icon==='chat'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clip-rule="evenodd"/>
          </svg>
          <!-- fill -->
          <svg v-if="item.icon==='fill'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M5 4a3 3 0 00-3 3v6a3 3 0 003 3h10a3 3 0 003-3V7a3 3 0 00-3-3H5zm-1 9v-1h5v2H5a1 1 0 01-1-1zm7 1h4a1 1 0 001-1v-1h-5v2zm0-4h5V8h-5v2zM9 8H4v2h5V8z" clip-rule="evenodd"/>
          </svg>
          <!-- edit -->
          <svg v-if="item.icon==='edit'" viewBox="0 0 20 20" fill="currentColor">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/>
          </svg>
          <!-- status -->
          <svg v-if="item.icon==='status'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7zm-3 1a1 1 0 10-2 0v3a1 1 0 102 0V8zM8 9a1 1 0 00-2 0v2a1 1 0 102 0V9z" clip-rule="evenodd"/>
          </svg>
        </div>
        <div class="nav-item-text">
          <span class="nav-item-label">{{ item.label }}</span>
          <span class="nav-item-desc">{{ item.desc }}</span>
        </div>
        <div v-if="modelValue === item.id" class="nav-item-indicator"></div>
      </button>
    </div>

    <!-- 底部状态 -->
    <div class="sidebar-footer">
      <div class="status-card" :class="backendOk ? 'status-ok' : 'status-err'">
        <div class="status-dot-wrap">
          <span class="status-pulse" :class="backendOk ? 'pulse-green' : 'pulse-red'"></span>
        </div>
        <div class="status-info">
          <span class="status-label">后端服务</span>
          <span class="status-val">{{ backendOk ? '正常运行' : '未连接' }}</span>
        </div>
      </div>
      <div class="footer-url">localhost:8000</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.sidebar-nav {
  flex: 1;
  padding: 16px 10px;
  overflow-y: auto;
}
.nav-section-label {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  padding: 0 6px;
  margin-bottom: 8px;
}
.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
  margin-bottom: 2px;
  text-align: left;
}
.nav-item:hover {
  background: #f0f6ff;
}
.nav-item--active {
  background: #eff6ff !important;
}
.nav-item-icon {
  width: 32px; height: 32px;
  border-radius: 8px;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}
.nav-item-icon svg {
  width: 15px; height: 15px;
  color: #64748b;
}
.nav-item--active .nav-item-icon {
  background: #1d4ed8;
}
.nav-item--active .nav-item-icon svg {
  color: #fff;
}
.nav-item-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.nav-item-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  line-height: 1;
}
.nav-item--active .nav-item-label {
  color: #1d4ed8;
}
.nav-item-desc {
  font-size: 10px;
  color: #94a3b8;
  line-height: 1;
}
.nav-item-indicator {
  position: absolute;
  right: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 18px;
  background: #1d4ed8;
  border-radius: 2px 0 0 2px;
}
/* 底部 */
.sidebar-footer {
  padding: 12px 10px 16px;
  border-top: 1px solid #f1f5f9;
}
.status-card {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  border-radius: 10px;
  margin-bottom: 6px;
}
.status-ok { background: #f0fdf4; border: 1px solid #bbf7d0; }
.status-err { background: #fff1f2; border: 1px solid #fecdd3; }
.status-dot-wrap { position: relative; width: 10px; height: 10px; flex-shrink: 0; }
.status-pulse {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  animation: status-ping 2s cubic-bezier(0,0,.2,1) infinite;
}
.pulse-green { background: #22c55e; }
.pulse-green::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: #22c55e;
  opacity: 0.4;
  animation: ping 2s cubic-bezier(0,0,.2,1) infinite;
}
.pulse-red { background: #ef4444; }
@keyframes ping {
  75%, 100% { transform: scale(2); opacity: 0; }
}
.status-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.status-label { font-size: 10px; color: #94a3b8; }
.status-val { font-size: 12px; font-weight: 600; color: #374151; }
.status-ok .status-val { color: #16a34a; }
.status-err .status-val { color: #dc2626; }
.footer-url {
  font-size: 10px;
  color: #cbd5e1;
  padding: 0 2px;
  text-align: center;
}
</style>
