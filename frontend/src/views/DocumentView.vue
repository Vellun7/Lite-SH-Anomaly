<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import mermaid from 'mermaid'
import { ArrowLeft, Document, List } from '@element-plus/icons-vue'
import docContent from '../../../docs/异常检测流程详解.md?raw'

const router = useRouter()

// 初始化 Mermaid 配置
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
  sequence: {
    diagramMarginX: 50,
    diagramMarginY: 10,
    actorMargin: 50,
    width: 150,
    height: 65,
    boxMargin: 10,
    boxTextMargin: 5,
    noteMargin: 10,
    messageMargin: 35,
    mirrorActors: true,
    useMaxWidth: true
  },
  flowchart: {
    htmlLabels: true,
    curve: 'basis'
  }
})

// 阅读进度
const readingProgress = ref(0)

// 目录数据
interface TocItem {
  id: string
  text: string
  level: number
}
const tocItems = ref<TocItem[]>([])
const activeSection = ref('')
const showToc = ref(true)

// 页面加载动画
const isLoaded = ref(false)

// 自定义 marked 渲染器，处理 mermaid 代码块
const renderer = new marked.Renderer()
const originalCodeRenderer = renderer.code.bind(renderer)

renderer.code = function(code: string, language: string | undefined) {
  if (language === 'mermaid') {
    // 为 mermaid 代码块创建特殊容器
    return `<div class="mermaid-container"><pre class="mermaid">${code}</pre></div>`
  }
  return originalCodeRenderer(code, language)
}

marked.setOptions({ renderer })

// 渲染 Markdown 文档
const renderedDoc = computed(() => {
  return marked(docContent) as string
})

// 渲染 Mermaid 图表
const renderMermaidCharts = async () => {
  await nextTick()
  const mermaidElements = document.querySelectorAll('.mermaid')
  if (mermaidElements.length > 0) {
    try {
      // 清除之前的渲染状态
      mermaidElements.forEach((el, index) => {
        el.removeAttribute('data-processed')
        el.id = `mermaid-${index}`
      })
      await mermaid.run({
        nodes: mermaidElements as NodeListOf<HTMLElement>
      })
    } catch (error) {
      console.error('Mermaid 渲染错误:', error)
    }
  }
}

// 提取目录
const extractToc = () => {
  const headingRegex = /^(#{1,3})\s+(.+)$/gm
  const toc: TocItem[] = []
  let match

  while ((match = headingRegex.exec(docContent)) !== null) {
    const level = match[1].length
    const text = match[2].trim()
    const id = text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\-\u4e00-\u9fa5]/g, '')
    toc.push({ id, text, level })
  }

  tocItems.value = toc
}

// 滚动到指定章节
const scrollToSection = (id: string) => {
  const element = document.getElementById(id)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 处理滚动事件
const handleScroll = () => {
  const scrollTop = window.scrollY
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  readingProgress.value = Math.min((scrollTop / docHeight) * 100, 100)

  // 更新当前活跃章节
  const headings = document.querySelectorAll('.markdown-body h1, .markdown-body h2, .markdown-body h3')
  for (let i = headings.length - 1; i >= 0; i--) {
    const heading = headings[i] as HTMLElement
    if (heading.offsetTop <= scrollTop + 100) {
      activeSection.value = heading.id
      break
    }
  }
}

// 为标题添加 ID
const addHeadingIds = () => {
  nextTick(() => {
    const headings = document.querySelectorAll('.markdown-body h1, .markdown-body h2, .markdown-body h3')
    headings.forEach((heading) => {
      const text = heading.textContent || ''
      const id = text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\-\u4e00-\u9fa5]/g, '')
      heading.id = id
    })
  })
}

// 返回上一页
const goBack = () => {
  router.back()
}

// 切换目录显示
const toggleToc = () => {
  showToc.value = !showToc.value
}

onMounted(async () => {
  extractToc()
  addHeadingIds()
  window.addEventListener('scroll', handleScroll)
  
  // 渲染 Mermaid 图表
  await renderMermaidCharts()
  
  // 触发入场动画
  setTimeout(() => {
    isLoaded.value = true
  }, 100)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <div class="document-view" :class="{ 'is-loaded': isLoaded }">
    <!-- 阅读进度条 -->
    <div class="reading-progress">
      <div class="progress-bar" :style="{ width: `${readingProgress}%` }"></div>
    </div>

    <!-- 页面头部 -->
    <header class="doc-header">
      <div class="header-left">
        <button class="back-btn" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          <span>返回</span>
        </button>
      </div>
      
      <div class="header-center">
        <div class="doc-icon">
          <el-icon><Document /></el-icon>
        </div>
        <h1 class="doc-title">异常检测流程详解</h1>
      </div>
      
      <div class="header-right">
        <button class="toc-toggle" @click="toggleToc" :class="{ active: showToc }">
          <el-icon><List /></el-icon>
          <span>目录</span>
        </button>
      </div>
    </header>

    <!-- 主内容区 -->
    <div class="doc-main" :class="{ 'toc-visible': showToc }">
      <!-- 目录侧边栏 -->
      <aside class="doc-sidebar" v-show="showToc">
        <div class="toc-wrapper">
          <div class="toc-header">
            <span class="toc-label">文档目录</span>
            <span class="toc-count">{{ tocItems.length }} 个章节</span>
          </div>
          <nav class="toc-nav">
            <a
              v-for="item in tocItems"
              :key="item.id"
              :href="`#${item.id}`"
              class="toc-item"
              :class="[
                `level-${item.level}`,
                { active: activeSection === item.id }
              ]"
              @click.prevent="scrollToSection(item.id)"
            >
              <span class="toc-indicator"></span>
              <span class="toc-text">{{ item.text }}</span>
            </a>
          </nav>
        </div>
      </aside>

      <!-- 文档内容 -->
      <main class="doc-content">
        <article class="markdown-body" v-html="renderedDoc"></article>
        
        <!-- 文档底部 -->
        <footer class="doc-footer">
          <div class="footer-decoration"></div>
          <p class="footer-text">— 文档结束 —</p>
          <button class="back-to-top" @click="window.scrollTo({ top: 0, behavior: 'smooth' })">
            回到顶部
          </button>
        </footer>
      </main>
    </div>

    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="bg-gradient"></div>
      <div class="bg-grid"></div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
// ==========================================
// 变量定义
// ==========================================
$header-height: 64px;
$sidebar-width: 280px;
$content-max-width: 820px;
$transition-base: 0.3s cubic-bezier(0.4, 0, 0.2, 1);

// ==========================================
// 页面容器
// ==========================================
.document-view {
  min-height: 100vh;
  background: var(--bg-base);
  position: relative;
  overflow-x: hidden;

  // 入场动画
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.6s ease, transform 0.6s ease;

  &.is-loaded {
    opacity: 1;
    transform: translateY(0);
  }
}

// ==========================================
// 阅读进度条
// ==========================================
.reading-progress {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(var(--primary-rgb), 0.1);
  z-index: 1001;

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--primary-color), var(--primary-light));
    transition: width 0.1s linear;
    box-shadow: 0 0 10px rgba(var(--primary-rgb), 0.5);
  }
}

// ==========================================
// 页面头部
// ==========================================
.doc-header {
  position: fixed;
  top: 3px;
  left: 0;
  right: 0;
  height: $header-height;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(var(--card-bg-rgb, 255, 255, 255), 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(var(--border-rgb), 0.5);
  z-index: 1000;

  .header-left, .header-right {
    flex: 0 0 auto;
    min-width: 120px;
  }

  .header-center {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  .header-right {
    display: flex;
    justify-content: flex-end;
  }
}

.back-btn, .toc-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all $transition-base;

  .el-icon {
    font-size: 16px;
  }

  &:hover {
    color: var(--primary-color);
    border-color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.05);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(var(--primary-rgb), 0.15);
  }

  &.active {
    color: var(--primary-color);
    border-color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.08);
  }
}

.doc-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--primary-color), var(--primary-light));
  border-radius: 12px;
  color: white;
  font-size: 20px;
  box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.35);
}

.doc-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

// ==========================================
// 主内容区布局
// ==========================================
.doc-main {
  display: flex;
  padding-top: calc($header-height + 3px);
  min-height: 100vh;
  transition: all $transition-base;

  &.toc-visible {
    .doc-content {
      margin-left: $sidebar-width;
    }
  }
}

// ==========================================
// 目录侧边栏
// ==========================================
.doc-sidebar {
  position: fixed;
  top: calc($header-height + 3px);
  left: 0;
  width: $sidebar-width;
  height: calc(100vh - $header-height - 3px);
  background: var(--card-bg);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  z-index: 100;

  // 自定义滚动条
  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 2px;
  }
}

.toc-wrapper {
  padding: 24px;
}

.toc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.toc-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.toc-count {
  font-size: 12px;
  color: var(--text-tertiary);
  background: var(--bg-elevated);
  padding: 4px 10px;
  border-radius: 20px;
}

.toc-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  line-height: 1.4;
  transition: all $transition-base;
  position: relative;

  &.level-1 {
    font-weight: 600;
    color: var(--text-primary);
  }

  &.level-2 {
    padding-left: 28px;
    font-size: 13px;
  }

  &.level-3 {
    padding-left: 42px;
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .toc-indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--border-color);
    flex-shrink: 0;
    transition: all $transition-base;
  }

  .toc-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &:hover {
    background: var(--bg-hover);
    color: var(--primary-color);

    .toc-indicator {
      background: var(--primary-color);
      transform: scale(1.3);
    }
  }

  &.active {
    background: rgba(var(--primary-rgb), 0.1);
    color: var(--primary-color);

    .toc-indicator {
      background: var(--primary-color);
      box-shadow: 0 0 8px rgba(var(--primary-rgb), 0.5);
    }
  }
}

// ==========================================
// 文档内容区
// ==========================================
.doc-content {
  flex: 1;
  max-width: calc($content-max-width + 120px);
  margin: 0 auto;
  padding: 48px 60px 80px;
  transition: all $transition-base;
}

// ==========================================
// Markdown 样式 - 编辑风格
// ==========================================
.markdown-body {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.85;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;

  // 一级标题
  :deep(h1) {
    font-size: 32px;
    font-weight: 800;
    margin: 56px 0 24px;
    padding-bottom: 16px;
    color: var(--text-primary);
    letter-spacing: -0.03em;
    position: relative;

    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      width: 80px;
      height: 4px;
      background: linear-gradient(90deg, var(--primary-color), transparent);
      border-radius: 2px;
    }

    &:first-child {
      margin-top: 0;
    }
  }

  // 二级标题
  :deep(h2) {
    font-size: 24px;
    font-weight: 700;
    margin: 48px 0 20px;
    padding: 16px 0 16px 20px;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    border-left: 4px solid var(--primary-color);
    background: linear-gradient(90deg, rgba(var(--primary-rgb), 0.06), transparent);
    border-radius: 0 8px 8px 0;
  }

  // 三级标题
  :deep(h3) {
    font-size: 20px;
    font-weight: 600;
    margin: 40px 0 16px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 12px;

    &::before {
      content: '';
      width: 8px;
      height: 8px;
      background: var(--primary-color);
      border-radius: 50%;
      flex-shrink: 0;
    }
  }

  // 四级标题
  :deep(h4) {
    font-size: 17px;
    font-weight: 600;
    margin: 32px 0 14px;
    color: var(--text-secondary);
  }

  // 段落
  :deep(p) {
    margin: 16px 0;
    color: var(--text-secondary);
    text-align: justify;
  }

  // 强调
  :deep(strong) {
    color: var(--text-primary);
    font-weight: 600;
    background: linear-gradient(180deg, transparent 60%, rgba(var(--primary-rgb), 0.2) 60%);
    padding: 0 2px;
  }

  // 链接
  :deep(a) {
    color: var(--primary-color);
    text-decoration: none;
    border-bottom: 1px dashed var(--primary-color);
    transition: all $transition-base;

    &:hover {
      border-bottom-style: solid;
      background: rgba(var(--primary-rgb), 0.1);
    }
  }

  // 列表
  :deep(ul), :deep(ol) {
    padding-left: 0;
    margin: 20px 0;
    list-style: none;

    li {
      position: relative;
      padding-left: 32px;
      margin: 12px 0;
      color: var(--text-secondary);
      line-height: 1.8;

      &::before {
        content: '';
        position: absolute;
        left: 8px;
        top: 10px;
        width: 8px;
        height: 8px;
        background: linear-gradient(135deg, var(--primary-color), var(--primary-light));
        border-radius: 3px;
        transform: rotate(45deg);
      }
    }
  }

  :deep(ol) {
    counter-reset: list-counter;

    li {
      counter-increment: list-counter;

      &::before {
        content: counter(list-counter);
        width: 24px;
        height: 24px;
        background: var(--primary-color);
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 600;
        transform: none;
        left: 0;
        top: 4px;
      }
    }
  }

  // 引用块
  :deep(blockquote) {
    margin: 28px 0;
    padding: 24px 28px;
    background: linear-gradient(135deg, rgba(var(--primary-rgb), 0.08), rgba(var(--primary-rgb), 0.02));
    border-left: 4px solid var(--primary-color);
    border-radius: 0 16px 16px 0;
    position: relative;
    overflow: hidden;

    &::before {
      content: '"';
      position: absolute;
      top: -10px;
      left: 20px;
      font-size: 80px;
      color: rgba(var(--primary-rgb), 0.1);
      font-family: Georgia, serif;
      line-height: 1;
    }

    p {
      margin: 10px 0;
      position: relative;
      z-index: 1;
      font-style: italic;
    }
  }

  // 行内代码
  :deep(code) {
    font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
    font-size: 13px;
    padding: 4px 10px;
    background: rgba(var(--primary-rgb), 0.08);
    border: 1px solid rgba(var(--primary-rgb), 0.15);
    border-radius: 6px;
    color: var(--primary-color);
    font-weight: 500;
  }

  // 代码块
  :deep(pre) {
    margin: 28px 0;
    padding: 0;
    background: #1e1e2e;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
    position: relative;

    &::before {
      content: '';
      display: block;
      height: 40px;
      background: linear-gradient(90deg, #ff5f57, #febc2e, #28c840);
      background-size: 12px 12px;
      background-position: 16px center;
      background-repeat: no-repeat;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    code {
      display: block;
      padding: 20px 24px 24px;
      background: none;
      border: none;
      color: #cdd6f4;
      font-size: 13px;
      line-height: 1.75;
      overflow-x: auto;

      &::-webkit-scrollbar {
        height: 6px;
      }

      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 3px;
      }
    }
  }

  // 表格
  :deep(table) {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 28px 0;
    font-size: 14px;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);

    th {
      background: linear-gradient(135deg, var(--primary-color), var(--primary-light));
      color: white;
      font-weight: 600;
      padding: 14px 20px;
      text-align: left;
      letter-spacing: 0.02em;
    }

    td {
      padding: 14px 20px;
      border-bottom: 1px solid var(--border-color);
      color: var(--text-secondary);
      background: var(--card-bg);
    }

    tr:last-child td {
      border-bottom: none;
    }

    tr:hover td {
      background: rgba(var(--primary-rgb), 0.04);
    }
  }

  // 分割线
  :deep(hr) {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-color), transparent);
    margin: 48px 0;
  }

  // 图片
  :deep(img) {
    max-width: 100%;
    border-radius: 12px;
    margin: 24px 0;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  }

  // Mermaid 图表容器
  :deep(.mermaid-container) {
    margin: 28px 0;
    padding: 24px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    overflow-x: auto;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);

    .mermaid {
      display: flex;
      justify-content: center;
      background: transparent !important;
      
      svg {
        max-width: 100%;
        height: auto;
      }
    }
  }

  // Mermaid 图表样式覆盖
  :deep(.mermaid) {
    // 时序图样式
    .actor {
      fill: var(--primary-color) !important;
      stroke: var(--primary-color) !important;
    }

    .actor-line {
      stroke: var(--border-color) !important;
    }

    text.actor {
      fill: white !important;
      font-weight: 600 !important;
    }

    .messageLine0, .messageLine1 {
      stroke: var(--text-secondary) !important;
    }

    .messageText {
      fill: var(--text-primary) !important;
      font-size: 13px !important;
    }

    .note {
      fill: rgba(var(--primary-rgb), 0.1) !important;
      stroke: var(--primary-color) !important;
    }

    .noteText {
      fill: var(--text-primary) !important;
    }

    // 流程图样式
    .node rect, .node circle, .node ellipse, .node polygon {
      fill: rgba(var(--primary-rgb), 0.1) !important;
      stroke: var(--primary-color) !important;
    }

    .node .label {
      color: var(--text-primary) !important;
    }

    .edgePath .path {
      stroke: var(--text-secondary) !important;
    }

    .edgeLabel {
      background: var(--card-bg) !important;
      color: var(--text-secondary) !important;
    }

    // 类图样式
    .classGroup rect {
      fill: rgba(var(--primary-rgb), 0.1) !important;
      stroke: var(--primary-color) !important;
    }

    .classGroup text {
      fill: var(--text-primary) !important;
    }
  }
}

// ==========================================
// 文档底部
// ==========================================
.doc-footer {
  margin-top: 80px;
  padding-top: 40px;
  text-align: center;

  .footer-decoration {
    width: 60px;
    height: 4px;
    background: linear-gradient(90deg, var(--primary-color), var(--primary-light));
    border-radius: 2px;
    margin: 0 auto 24px;
  }

  .footer-text {
    color: var(--text-tertiary);
    font-size: 14px;
    margin-bottom: 24px;
  }

  .back-to-top {
    padding: 12px 28px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 24px;
    color: var(--text-secondary);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all $transition-base;

    &:hover {
      color: var(--primary-color);
      border-color: var(--primary-color);
      transform: translateY(-3px);
      box-shadow: 0 8px 20px rgba(var(--primary-rgb), 0.2);
    }
  }
}

// ==========================================
// 背景装饰
// ==========================================
.bg-decoration {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: -1;
}

.bg-gradient {
  position: absolute;
  top: 0;
  right: 0;
  width: 50%;
  height: 50%;
  background: radial-gradient(ellipse at top right, rgba(var(--primary-rgb), 0.05), transparent 60%);
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(var(--border-rgb), 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--border-rgb), 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
}

// ==========================================
// 响应式设计
// ==========================================
@media (max-width: 1200px) {
  .doc-sidebar {
    width: 240px;
  }

  .doc-main.toc-visible .doc-content {
    margin-left: 240px;
  }
}

@media (max-width: 992px) {
  .doc-sidebar {
    transform: translateX(-100%);
    transition: transform $transition-base;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.1);

    &:has(+ .doc-content) {
      transform: translateX(0);
    }
  }

  .doc-main.toc-visible .doc-sidebar {
    transform: translateX(0);
  }

  .doc-main.toc-visible .doc-content {
    margin-left: 0;
  }

  .doc-content {
    padding: 40px 40px 60px;
  }
}

@media (max-width: 768px) {
  .doc-header {
    padding: 0 16px;

    .header-left, .header-right {
      min-width: auto;
    }

    .back-btn span, .toc-toggle span {
      display: none;
    }

    .back-btn, .toc-toggle {
      padding: 10px 12px;
    }

    .doc-icon {
      width: 32px;
      height: 32px;
      font-size: 16px;
    }

    .doc-title {
      font-size: 16px;
    }
  }

  .doc-content {
    padding: 24px 20px 48px;
  }

  .markdown-body {
    font-size: 14px;

    :deep(h1) {
      font-size: 24px;
      margin: 40px 0 20px;
    }

    :deep(h2) {
      font-size: 20px;
      margin: 36px 0 16px;
      padding: 12px 0 12px 16px;
    }

    :deep(h3) {
      font-size: 17px;
      margin: 28px 0 14px;
    }

    :deep(pre) {
      border-radius: 12px;

      code {
        padding: 16px 18px 20px;
        font-size: 12px;
      }
    }

    :deep(blockquote) {
      padding: 20px 22px;
    }

    :deep(table) {
      font-size: 13px;

      th, td {
        padding: 10px 14px;
      }
    }
  }
}

// ==========================================
// 暗色主题适配
// ==========================================
:root[data-theme='dark'] {
  .doc-header {
    background: rgba(30, 30, 46, 0.9);
  }

  .doc-sidebar {
    background: var(--card-bg);
  }

  .markdown-body {
    :deep(pre) {
      background: #11111b;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    :deep(table) {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    }

    // 暗色主题 Mermaid 样式
    :deep(.mermaid-container) {
      background: rgba(30, 30, 46, 0.6);
      border-color: rgba(255, 255, 255, 0.1);
    }

    :deep(.mermaid) {
      .actor {
        fill: var(--primary-color) !important;
      }

      text {
        fill: #cdd6f4 !important;
      }

      .note {
        fill: rgba(var(--primary-rgb), 0.2) !important;
      }

      .messageLine0, .messageLine1, .actor-line {
        stroke: #6c7086 !important;
      }
    }
  }
}
</style>
