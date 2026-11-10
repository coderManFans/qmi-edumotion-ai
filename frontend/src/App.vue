<script setup lang="ts">
import { ref } from 'vue'

const apiStatus = ref('尚未检测')
const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function checkApi() {
  try {
    const response = await fetch(`${apiBase}/api/v1/health`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    apiStatus.value = data.status === 'ok' ? '已连接' : '异常响应'
  } catch {
    apiStatus.value = '暂不可用'
  }
}
</script>

<template>
  <main class="shell">
    <header><span class="eyebrow">AI LEARNING CONTENT STUDIO</span><h1>EduMotion AI</h1><p>把知识变成看得见、听得懂的学习体验。</p></header>
    <section class="panel">
      <h2>项目工作台</h2>
      <p>数学题目讲解 · 语文故事 · 滚动图解 · 动画视频</p>
      <div class="status"><span>后端 API</span><strong>{{ apiStatus }}</strong><button @click="checkApi">检测连接</button></div>
    </section>
    <footer>初始项目骨架 · Web lesson + video renderer</footer>
  </main>
</template>
