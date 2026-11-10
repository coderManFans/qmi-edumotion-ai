<script setup lang="ts">
import { ref } from 'vue'

type Subject = 'mathematics' | 'chinese'
type LessonBlock = { type: string; content?: unknown }
type LessonScene = { id: string; type: string; narration?: string; blocks: LessonBlock[] }
type Lesson = {
  lesson_id: string
  subject: Subject
  title: string
  grade_level: number
  learning_objectives: string[]
  scenes: LessonScene[]
}

const subject = ref<Subject>('mathematics')
const topic = ref('认识分数')
const gradeLevel = ref(4)
const title = ref('')
const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const loading = ref(false)
const errorMessage = ref('')
const lesson = ref<Lesson | null>(null)
const apiStatus = ref('尚未检测')

async function checkApi() {
  try {
    const response = await fetch(`${apiBase}/api/v1/health`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    apiStatus.value = '已连接'
  } catch {
    apiStatus.value = '暂不可用'
  }
}

async function generateLesson() {
  loading.value = true
  errorMessage.value = ''
  lesson.value = null
  try {
    const response = await fetch(`${apiBase}/api/v1/lessons/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subject: subject.value,
        topic: topic.value,
        grade_level: gradeLevel.value,
        title: title.value || undefined,
      }),
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => null)
      throw new Error(detail?.detail?.[0]?.msg ?? `生成失败（HTTP ${response.status}）`)
    }
    lesson.value = await response.json() as Lesson
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败，请检查后端服务'
  } finally {
    loading.value = false
  }
}

function blockText(block: LessonBlock): string {
  if (typeof block.content === 'string') return block.content
  if (block.type === 'quiz' && block.content && typeof block.content === 'object') {
    const quiz = block.content as { question?: string }
    return quiz.question ?? '互动练习'
  }
  if (block.type === 'diagram') return '图解内容已包含在 Lesson IR 中'
  return JSON.stringify(block.content ?? '')
}

function quizOptions(block: LessonBlock): string[] {
  if (block.type !== 'quiz' || !block.content || typeof block.content !== 'object') return []
  return (block.content as { options?: string[] }).options ?? []
}
</script>

<template>
  <main class="shell">
    <header class="hero">
      <span class="eyebrow">AI LEARNING CONTENT STUDIO</span>
      <h1>EduMotion AI</h1>
      <p>把知识变成看得见、听得懂的学习体验。</p>
    </header>

    <section class="workspace">
      <form class="generator panel" @submit.prevent="generateLesson">
        <div class="section-heading">
          <div><span class="eyebrow">CREATE A LESSON</span><h2>生成教学内容</h2></div>
          <span class="status-dot" :class="{ online: apiStatus === '已连接' }">{{ apiStatus }}</span>
        </div>
        <label>学科</label>
        <div class="subject-switch">
          <button type="button" :class="{ selected: subject === 'mathematics' }" @click="subject = 'mathematics'; topic = '认识分数'; gradeLevel = 4">数学</button>
          <button type="button" :class="{ selected: subject === 'chinese' }" @click="subject = 'chinese'; topic = '春天的校园'; gradeLevel = 3">语文</button>
        </div>
        <label for="topic">知识主题 / 故事主题</label>
        <input id="topic" v-model.trim="topic" required minlength="2" maxlength="100" :placeholder="subject === 'mathematics' ? '例如：认识分数' : '例如：春天的校园'" />
        <div class="field-row">
          <div><label for="grade">年级</label><select id="grade" v-model.number="gradeLevel"><option v-for="grade in 12" :key="grade" :value="grade">{{ grade }} 年级</option></select></div>
          <div><label for="lesson-title">课程标题（可选）</label><input id="lesson-title" v-model.trim="title" maxlength="120" placeholder="自动生成标题" /></div>
        </div>
        <button class="primary" type="submit" :disabled="loading || topic.length < 2">{{ loading ? '正在生成…' : '生成课程内容' }}</button>
        <button class="text-button" type="button" @click="checkApi">检测后端连接</button>
        <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
        <p class="hint">当前为可运行的模板生成 MVP，后续可接入大语言模型。</p>
      </form>

      <section class="preview panel">
        <div class="section-heading"><div><span class="eyebrow">LESSON PREVIEW</span><h2>课程预览</h2></div><span v-if="lesson" class="tag">{{ lesson.scenes.length }} 个场景</span></div>
        <div v-if="!lesson" class="empty-state"><div class="empty-icon">✦</div><h3>准备好开始创作了吗？</h3><p>选择学科并输入主题，生成后将在这里展示可滚动的课程内容。</p></div>
        <article v-else class="lesson">
          <div class="lesson-meta">{{ lesson.subject === 'mathematics' ? '数学' : '语文' }} · {{ lesson.grade_level }} 年级</div>
          <h3>{{ lesson.title }}</h3>
          <div class="objectives"><strong>学习目标</strong><ul><li v-for="objective in lesson.learning_objectives" :key="objective">{{ objective }}</li></ul></div>
          <section v-for="(scene, index) in lesson.scenes" :key="scene.id" class="scene">
            <div class="scene-number">SCENE 0{{ index + 1 }}</div>
            <h4>{{ scene.type === 'story' ? '故事阅读' : scene.type === 'question' ? '互动练习' : scene.type === 'summary' ? '本课总结' : '知识讲解' }}</h4>
            <p v-if="scene.narration" class="narration">{{ scene.narration }}</p>
            <div v-for="(block, blockIndex) in scene.blocks" :key="blockIndex" class="content-block" :class="block.type">
              <template v-if="block.type === 'math'"><span class="math-expression">{{ blockText(block) }}</span></template>
              <template v-else><p>{{ blockText(block) }}</p></template>
              <ul v-if="quizOptions(block).length" class="quiz-options"><li v-for="option in quizOptions(block)" :key="option">{{ option }}</li></ul>
            </div>
          </section>
          <div class="lesson-id">Lesson ID · {{ lesson.lesson_id }}</div>
        </article>
      </section>
    </section>
    <footer>EduMotion AI · Shared Lesson IR · Web lesson + video renderer</footer>
  </main>
</template>
