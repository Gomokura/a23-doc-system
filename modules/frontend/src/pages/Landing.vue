<script setup lang="ts">
defineEmits<{ (e: 'enter'): void }>()
</script>

<template>
  <div class="landing-root">

    <!-- ══ 顶部导航栏 ══ -->
    <nav class="landing-nav">
      <div class="nav-inner">
        <div class="nav-brand">
          <div class="nav-logo">
            <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="32" height="32" rx="8" fill="url(#g1)"/>
              <path d="M9 10h14M9 16h10M9 22h12" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>
              <circle cx="23" cy="22" r="4" fill="#60a5fa"/>
              <path d="M21.5 22l1 1 2-2" stroke="#fff" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#1d4ed8"/>
                  <stop offset="1" stop-color="#3b82f6"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span class="nav-title">DocuMind AI</span>
          <span class="nav-badge">A23</span>
        </div>
        <div class="nav-links">
          <a href="#features">功能特性</a>
          <a href="#flow">使用流程</a>
          <a href="#tech">技术栈</a>
        </div>
        <button class="nav-cta" @click="$emit('enter')">
          进入系统 →
        </button>
      </div>
    </nav>

    <!-- ══ Hero 区域 ══ -->
    <section class="hero">
      <!-- 背景网格 + 光晕 -->
      <div class="hero-bg">
        <div class="hero-grid"></div>
        <div class="hero-glow hero-glow-1"></div>
        <div class="hero-glow hero-glow-2"></div>
      </div>

      <div class="hero-inner">
        <!-- 标签 -->
        <div class="hero-chip">
          <span class="chip-dot"></span>
          基于大语言模型 · 吉林大学软件学院
        </div>

        <!-- 主标题 -->
        <h1 class="hero-title">
          让文档理解<br/>
          <span class="title-gradient">真正智能化</span>
        </h1>

        <!-- 副标题 -->
        <p class="hero-sub">
          上传多源文档，系统自动解析、建索引、智能问答，<br/>
          并根据您提供的模板 <strong>一键自动填写表格</strong>——无需手动操作。
        </p>

        <!-- CTA 按钮组 -->
        <div class="hero-actions">
          <button class="btn-primary" @click="$emit('enter')">
            <svg class="btn-icon" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z" clip-rule="evenodd"/>
            </svg>
            立即开始使用
          </button>
          <button class="btn-secondary" @click="document.getElementById('features')?.scrollIntoView({behavior:'smooth'})">
            了解功能特性
          </button>
        </div>

        <!-- 数据指标 -->
        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-num">5+</span>
            <span class="stat-label">文档格式支持</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num">≥80%</span>
            <span class="stat-label">填表准确率</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num">≤90s</span>
            <span class="stat-label">单次响应时间</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num">全自动</span>
            <span class="stat-label">零人工干预</span>
          </div>
        </div>
      </div>

      <!-- 预览卡片 -->
      <div class="hero-preview">
        <div class="preview-card">
          <div class="preview-bar">
            <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
            <span class="preview-title-bar">DocuMind AI — 文档工作台</span>
          </div>
          <div class="preview-body">
            <!-- 模拟侧边栏 -->
            <div class="mock-sidebar">
              <div class="mock-nav active">📤 文档上传</div>
              <div class="mock-nav">💬 智能问答</div>
              <div class="mock-nav active-fill">📋 表格回填</div>
              <div class="mock-nav">🖥️ 文档操作</div>
              <div class="mock-status">
                <span class="status-dot"></span> 后端已连接
              </div>
            </div>
            <!-- 模拟主内容 -->
            <div class="mock-main">
              <div class="mock-header">📋 智能表格回填</div>
              <div class="mock-step">① 上传模板 → 自动识别字段</div>
              <div class="mock-tags">
                <span class="tag blue">日期</span>
                <span class="tag blue">姓名</span>
                <span class="tag blue">金额</span>
                <span class="tag blue">部门</span>
                <span class="tag gray">+3 个字段</span>
              </div>
              <div class="mock-progress-row">
                <span>自动提取中</span>
                <div class="mock-progress-bar"><div class="mock-progress-fill" style="width:72%"></div></div>
                <span>72%</span>
              </div>
              <div class="mock-table-head">
                <span>日期</span><span>姓名</span><span>金额</span><span>状态</span>
              </div>
              <div class="mock-table-row">
                <span>2024/01/15</span><span>张三</span><span>¥12,500</span><span class="tag-ok">✓ 完成</span>
              </div>
              <div class="mock-table-row muted">
                <span>2024/01/16</span><span>李四</span><span>¥8,300</span><span class="tag-ok">✓ 完成</span>
              </div>
              <div class="mock-dl">
                <span class="dl-btn">⬇ 下载填好的表格</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ══ 功能特性 ══ -->
    <section class="section" id="features">
      <div class="section-inner">
        <div class="section-label">核心功能</div>
        <h2 class="section-title">三大能力，覆盖完整文档工作流</h2>
        <p class="section-sub">从文档入库到信息提取、从智能问答到自动填表，一个平台搞定全流程</p>

        <div class="features-grid">
          <div class="feature-card card-blue">
            <div class="feat-icon-wrap blue-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
            </div>
            <h3>非结构化文档解析</h3>
            <p>支持 PDF、Word、Excel、TXT、Markdown 五种格式，智能分块、向量化建索引，毫秒级语义检索。</p>
            <ul class="feat-list">
              <li>✦ PDF 图文混排 OCR</li>
              <li>✦ 表格结构保留</li>
              <li>✦ 自动去重 (MD5)</li>
            </ul>
          </div>

          <div class="feature-card card-indigo">
            <div class="feat-icon-wrap indigo-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
              </svg>
            </div>
            <h3>多文档智能问答</h3>
            <p>基于 RAG 架构，BM25 + 向量混合检索，支持跨文档关联推理，准确溯源到具体段落。</p>
            <ul class="feat-list">
              <li>✦ 混合检索 + MMR 去重</li>
              <li>✦ 精准段落溯源</li>
              <li>✦ 流式输出响应</li>
            </ul>
          </div>

          <div class="feature-card card-cyan">
            <div class="feat-icon-wrap cyan-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
              </svg>
            </div>
            <h3>全自动表格回填</h3>
            <p>上传模板后，系统自动匹配数据源字段，支持任意自然语言筛选条件，一键生成填好的 Excel/Word。</p>
            <ul class="feat-list">
              <li>✦ 任意条件筛选</li>
              <li>✦ 多文件行对齐</li>
              <li>✦ 预览后二次确认</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- ══ 使用流程 ══ -->
    <section class="section section-dark" id="flow">
      <div class="section-inner">
        <div class="section-label light">使用流程</div>
        <h2 class="section-title light">四步完成，无需专业背景</h2>

        <div class="flow-steps">
          <div class="flow-step" v-for="(step, i) in steps" :key="i">
            <div class="flow-num">{{ i + 1 }}</div>
            <div class="flow-connector" v-if="i < steps.length - 1"></div>
            <div class="flow-icon">{{ step.icon }}</div>
            <div class="flow-name">{{ step.name }}</div>
            <div class="flow-desc">{{ step.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ══ 技术栈 ══ -->
    <section class="section" id="tech">
      <div class="section-inner">
        <div class="section-label">技术架构</div>
        <h2 class="section-title">全栈自研，端到端大模型驱动</h2>

        <div class="tech-grid">
          <div class="tech-col">
            <div class="tech-col-title">前端</div>
            <div class="tech-tags">
              <span class="tech-tag">Vue 3</span>
              <span class="tech-tag">TypeScript</span>
              <span class="tech-tag">Vite</span>
              <span class="tech-tag">TailwindCSS</span>
              <span class="tech-tag">Element Plus</span>
            </div>
          </div>
          <div class="tech-col">
            <div class="tech-col-title">后端</div>
            <div class="tech-tags">
              <span class="tech-tag">FastAPI</span>
              <span class="tech-tag">Python 3.11</span>
              <span class="tech-tag">SQLite</span>
              <span class="tech-tag">ChromaDB</span>
              <span class="tech-tag">BM25S</span>
            </div>
          </div>
          <div class="tech-col">
            <div class="tech-col-title">AI 能力</div>
            <div class="tech-tags">
              <span class="tech-tag">Qwen2.5-72B</span>
              <span class="tech-tag">BAAI/bge-m3</span>
              <span class="tech-tag">Docling</span>
              <span class="tech-tag">RAG</span>
              <span class="tech-tag">硅基流动</span>
            </div>
          </div>
          <div class="tech-col">
            <div class="tech-col-title">文档处理</div>
            <div class="tech-tags">
              <span class="tech-tag">pdfplumber</span>
              <span class="tech-tag">python-docx</span>
              <span class="tech-tag">openpyxl</span>
              <span class="tech-tag">pandas</span>
              <span class="tech-tag">Markdown</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ══ CTA 底部 ══ -->
    <section class="cta-section">
      <div class="cta-glow"></div>
      <div class="cta-inner">
        <h2>准备好了吗？</h2>
        <p>上传您的文档，让 AI 帮您完成繁琐的信息提取与表格填写</p>
        <button class="btn-primary btn-large" @click="$emit('enter')">
          立即开始使用 →
        </button>
      </div>
    </section>

    <!-- ══ Footer ══ -->
    <footer class="landing-footer">
      <span>© 2025 DocuMind AI · A23 Project · 吉林大学软件学院</span>
    </footer>

  </div>
</template>

<script lang="ts">
export default {
  data() {
    return {
      steps: [
        { icon: '📁', name: '上传文档', desc: '批量上传 PDF/Word/Excel 等数据源文档，系统自动解析建立索引' },
        { icon: '📋', name: '上传模板', desc: '提供需要填写的 Excel 或 Word 模板，系统自动识别所有表头字段' },
        { icon: '⚡', name: '自动提取', desc: '填写筛选条件（可选），系统从所有文档中提取匹配数据，行对齐组装' },
        { icon: '⬇️', name: '下载结果', desc: '预览提取结果，确认无误后一键生成并下载填好的文件' },
      ]
    }
  }
}
</script>

<style scoped>
/* ── 全局基础 ── */
.landing-root {
  min-height: 100vh;
  background: #f8faff;
  font-family: 'Noto Sans SC', -apple-system, 'PingFang SC', sans-serif;
  color: #0f172a;
}

/* ── 导航栏 ── */
.landing-nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  background: rgba(248, 250, 255, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(59, 130, 246, 0.12);
}
.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 40px;
}
.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.nav-logo {
  width: 32px;
  height: 32px;
}
.nav-logo svg { width: 100%; height: 100%; }
.nav-title {
  font-size: 16px;
  font-weight: 700;
  color: #1d4ed8;
  letter-spacing: -0.3px;
}
.nav-badge {
  background: #eff6ff;
  color: #3b82f6;
  border: 1px solid #bfdbfe;
  padding: 1px 7px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
}
.nav-links {
  display: flex;
  gap: 28px;
  flex: 1;
}
.nav-links a {
  font-size: 14px;
  color: #475569;
  text-decoration: none;
  transition: color 0.2s;
}
.nav-links a:hover { color: #1d4ed8; }
.nav-cta {
  background: #1d4ed8;
  color: #fff;
  border: none;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
  white-space: nowrap;
}
.nav-cta:hover { background: #1e40af; transform: translateY(-1px); }

/* ── Hero ── */
.hero {
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: 120px 32px 80px;
  position: relative;
  overflow: hidden;
  max-width: 1200px;
  margin: 0 auto;
}
.hero-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.hero-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(59,130,246,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59,130,246,0.05) 1px, transparent 1px);
  background-size: 40px 40px;
}
.hero-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
}
.hero-glow-1 {
  width: 600px; height: 600px;
  background: radial-gradient(circle, #3b82f6 0%, transparent 70%);
  top: -200px; left: -100px;
}
.hero-glow-2 {
  width: 400px; height: 400px;
  background: radial-gradient(circle, #818cf8 0%, transparent 70%);
  top: 200px; right: -50px;
}
.hero-inner {
  flex: 1;
  position: relative;
  z-index: 1;
  max-width: 560px;
}
.hero-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 28px;
}
.chip-dot {
  width: 7px; height: 7px;
  background: #3b82f6;
  border-radius: 50%;
  animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}
.hero-title {
  font-size: 52px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -1px;
  color: #0f172a;
  margin: 0 0 20px;
}
.title-gradient {
  background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 50%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-sub {
  font-size: 17px;
  color: #475569;
  line-height: 1.75;
  margin: 0 0 36px;
}
.hero-sub strong { color: #1d4ed8; font-weight: 600; }
.hero-actions {
  display: flex;
  gap: 14px;
  margin-bottom: 48px;
  flex-wrap: wrap;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  color: #fff;
  border: none;
  padding: 14px 28px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(29, 78, 216, 0.35);
  transition: all 0.2s;
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 28px rgba(29, 78, 216, 0.45);
}
.btn-icon { width: 18px; height: 18px; }
.btn-secondary {
  background: #fff;
  color: #374151;
  border: 1.5px solid #d1d5db;
  padding: 14px 28px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-secondary:hover {
  border-color: #3b82f6;
  color: #1d4ed8;
  background: #eff6ff;
}
.btn-large { padding: 16px 36px; font-size: 16px; }
.hero-stats {
  display: flex;
  align-items: center;
  gap: 0;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 20px 28px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.stat-item {
  flex: 1;
  text-align: center;
}
.stat-num {
  display: block;
  font-size: 22px;
  font-weight: 800;
  color: #1d4ed8;
  letter-spacing: -0.5px;
}
.stat-label {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}
.stat-divider {
  width: 1px;
  height: 36px;
  background: #e2e8f0;
  margin: 0 4px;
}

/* ── Hero 预览卡片 ── */
.hero-preview {
  flex-shrink: 0;
  width: 500px;
  margin-left: 60px;
  position: relative;
  z-index: 1;
}
.preview-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(0,0,0,0.05);
  overflow: hidden;
}
.preview-bar {
  background: #f1f5f9;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid #e2e8f0;
}
.dot { width: 11px; height: 11px; border-radius: 50%; }
.dot.red { background: #f87171; }
.dot.yellow { background: #fbbf24; }
.dot.green { background: #34d399; }
.preview-title-bar {
  margin-left: 10px;
  font-size: 12px;
  color: #94a3b8;
}
.preview-body {
  display: flex;
  height: 340px;
}
.mock-sidebar {
  width: 120px;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  padding: 12px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.mock-nav {
  padding: 7px 12px;
  font-size: 11px;
  color: #64748b;
  cursor: default;
  border-radius: 6px;
  margin: 0 6px;
}
.mock-nav.active { background: #eff6ff; color: #3b82f6; }
.mock-nav.active-fill { background: #f0fdf4; color: #16a34a; font-weight: 600; }
.mock-status {
  margin-top: auto;
  padding: 8px 12px;
  font-size: 10px;
  color: #22c55e;
  display: flex;
  align-items: center;
  gap: 5px;
}
.status-dot {
  width: 6px; height: 6px;
  background: #22c55e;
  border-radius: 50%;
}
.mock-main {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}
.mock-header {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}
.mock-step {
  font-size: 11px;
  color: #64748b;
  background: #f8fafc;
  padding: 5px 8px;
  border-radius: 6px;
}
.mock-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.tag {
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 500;
}
.tag.blue { background: #eff6ff; color: #3b82f6; border: 1px solid #bfdbfe; }
.tag.gray { background: #f1f5f9; color: #94a3b8; border: 1px solid #e2e8f0; }
.mock-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: #64748b;
}
.mock-progress-bar {
  flex: 1;
  height: 5px;
  background: #e2e8f0;
  border-radius: 99px;
  overflow: hidden;
}
.mock-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 99px;
  animation: progress-anim 3s ease-in-out infinite alternate;
}
@keyframes progress-anim {
  from { width: 55%; }
  to { width: 92%; }
}
.mock-table-head {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  background: #f8fafc;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
}
.mock-table-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 5px 8px;
  font-size: 10px;
  color: #374151;
  border-bottom: 1px solid #f1f5f9;
  align-items: center;
}
.mock-table-row.muted { opacity: 0.5; }
.tag-ok {
  color: #16a34a;
  font-weight: 600;
  font-size: 10px;
}
.mock-dl {
  margin-top: auto;
}
.dl-btn {
  display: inline-block;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  color: #fff;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

/* ── 通用 section ── */
.section {
  padding: 90px 32px;
  background: #f8faff;
}
.section-dark {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
}
.section-inner {
  max-width: 1100px;
  margin: 0 auto;
}
.section-label {
  display: inline-block;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 16px;
}
.section-label.light {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.2);
  color: #93c5fd;
}
.section-title {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin: 0 0 12px;
  color: #0f172a;
}
.section-title.light { color: #f1f5f9; }
.section-sub {
  font-size: 16px;
  color: #64748b;
  margin: 0 0 48px;
}

/* ── 功能卡片 ── */
.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.feature-card {
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  border: 1px solid #e2e8f0;
  transition: transform 0.2s, box-shadow 0.2s;
}
.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 48px rgba(0,0,0,0.1);
}
.feat-icon-wrap {
  width: 52px; height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}
.feat-icon-wrap svg { width: 26px; height: 26px; }
.blue-icon  { background: #eff6ff; color: #3b82f6; }
.indigo-icon { background: #eef2ff; color: #6366f1; }
.cyan-icon  { background: #ecfeff; color: #06b6d4; }
.feature-card h3 {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 10px;
}
.feature-card p {
  font-size: 14px;
  color: #64748b;
  line-height: 1.7;
  margin: 0 0 16px;
}
.feat-list {
  list-style: none;
  padding: 0; margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.feat-list li {
  font-size: 13px;
  color: #475569;
}

/* ── 流程步骤 ── */
.flow-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  position: relative;
  margin-top: 48px;
}
.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  position: relative;
  padding: 0 16px;
}
.flow-num {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1d4ed8, #60a5fa);
  color: #fff;
  font-size: 16px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
  box-shadow: 0 4px 16px rgba(29, 78, 216, 0.4);
}
.flow-connector {
  position: absolute;
  top: 20px;
  left: calc(50% + 20px);
  right: calc(-50% + 20px);
  height: 2px;
  background: linear-gradient(90deg, rgba(59,130,246,0.5), rgba(59,130,246,0.2));
}
.flow-icon {
  font-size: 36px;
  margin-bottom: 14px;
}
.flow-name {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 8px;
}
.flow-desc {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.65;
}

/* ── 技术栈 ── */
.tech-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-top: 48px;
}
.tech-col {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 24px;
}
.tech-col-title {
  font-size: 13px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 14px;
}
.tech-tags {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.tech-tag {
  display: inline-block;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #374151;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
}
.tech-tag:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

/* ── CTA ── */
.cta-section {
  padding: 100px 32px;
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
  text-align: center;
  position: relative;
  overflow: hidden;
}
.cta-glow {
  position: absolute;
  width: 600px; height: 600px;
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
}
.cta-inner {
  position: relative;
  z-index: 1;
}
.cta-inner h2 {
  font-size: 40px;
  font-weight: 800;
  color: #fff;
  margin: 0 0 12px;
  letter-spacing: -0.5px;
}
.cta-inner p {
  font-size: 16px;
  color: rgba(255,255,255,0.75);
  margin: 0 0 36px;
}
.cta-section .btn-primary {
  background: #fff;
  color: #1d4ed8;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.cta-section .btn-primary:hover {
  background: #eff6ff;
  box-shadow: 0 12px 40px rgba(0,0,0,0.25);
}

/* ── Footer ── */
.landing-footer {
  background: #0f172a;
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #475569;
}

/* ── 响应式 ── */
@media (max-width: 900px) {
  .hero { flex-direction: column; }
  .hero-preview { display: none; }
  .hero-title { font-size: 36px; }
  .features-grid { grid-template-columns: 1fr; }
  .flow-steps { grid-template-columns: 1fr 1fr; gap: 32px; }
  .tech-grid { grid-template-columns: 1fr 1fr; }
  .nav-links { display: none; }
}
</style>
