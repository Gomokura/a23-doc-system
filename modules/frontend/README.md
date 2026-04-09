# A23 智能文档系统 - Vue 3 前端

基于 Vue 3 + Vite 5 + Tailwind CSS 的现代化前端。

## 快速开始

### 安装依赖

```bash
cd modules/frontend
pnpm install
```

### 开发模式

```bash
pnpm dev
```

访问 `http://localhost:5173`

### 生产构建

```bash
pnpm build
```

## 项目结构

```
modules/frontend/
├── src/
│   ├── main.ts              # 入口文件
│   ├── App.vue              # 主应用
│   ├── layout/
│   │   ├── Header.vue       # 顶部导航
│   │   ├── Sidebar.vue      # 左侧菜单
│   │   └── MainContent.vue  # 右侧内容
│   ├── pages/
│   │   ├── Upload.vue       # 文档上传
│   │   ├── Query.vue        # 智能问答
│   │   ├── Fill.vue         # 表格回填
│   │   └── Status.vue       # 系统状态
│   └── style/
│       └── index.css        # 全局样式
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── index.html
```

## 功能特性

- ✅ 文档上传（支持 PDF、DOCX、XLSX、TXT、MD）
- ✅ 智能问答（多源文档检索和证据溯源）
- ✅ 表格回填（Word 模板自动回填）
- ✅ 系统状态（服务健康检查和文档管理）

## 技术栈

- Vue 3 + TypeScript
- Vite 5
- Tailwind CSS
- Element Plus
- Fetch API

## 后端 API

确保后端运行在 `http://localhost:8000`

## 开发命令

```bash
pnpm dev          # 启动开发服务器
pnpm build        # 构建生产版本
pnpm preview      # 预览生产构建
pnpm lint         # 代码检查
pnpm format       # 代码格式化
pnpm type-check   # 类型检查
```
