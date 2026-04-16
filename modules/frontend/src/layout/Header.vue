<script setup lang="ts">
defineEmits<{ (e: 'back'): void }>()
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <!-- 左：品牌 + 返回 -->
      <div class="header-left">
        <button class="back-btn" @click="$emit('back')" title="返回首页">
          <svg viewBox="0 0 20 20" fill="currentColor" class="back-icon">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd"/>
          </svg>
        </button>
        <div class="divider-v"></div>
        <div class="brand">
          <div class="brand-logo">
            <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="32" height="32" rx="8" fill="url(#hg1)"/>
              <path d="M9 10h14M9 16h10M9 22h12" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>
              <circle cx="23" cy="22" r="4" fill="#60a5fa"/>
              <path d="M21.5 22l1 1 2-2" stroke="#fff" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <defs>
                <linearGradient id="hg1" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#1d4ed8"/><stop offset="1" stop-color="#3b82f6"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span class="brand-name">DocuMind AI</span>
          <span class="brand-sub">文档工作台</span>
        </div>
      </div>

      <!-- 中：面包屑标签 -->
      <div class="header-center">
        <span class="workspace-chip">智能文档处理平台</span>
      </div>

      <!-- 右：状态 + 标记 -->
      <div class="header-right">
        <div class="project-tag">A23 PROJECT</div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 8px rgba(29, 78, 216, 0.06);
  position: sticky;
  top: 0;
  z-index: 50;
}
.header-inner {
  height: 100%;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.back-btn {
  width: 30px; height: 30px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8faff;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.back-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}
.back-icon { width: 14px; height: 14px; }
.divider-v {
  width: 1px; height: 20px;
  background: #e2e8f0;
}
.brand {
  display: flex;
  align-items: center;
  gap: 9px;
}
.brand-logo {
  width: 28px; height: 28px; flex-shrink: 0;
}
.brand-logo svg { width: 100%; height: 100%; }
.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: #1d4ed8;
  letter-spacing: -0.3px;
}
.brand-sub {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 400;
}
.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}
.workspace-chip {
  background: #f0f6ff;
  border: 1px solid #dbeafe;
  color: #3b82f6;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.project-tag {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
</style>
