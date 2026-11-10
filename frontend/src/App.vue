<script setup lang="ts">
import { ref } from 'vue'

type Scene = { id: string; title: string; narration: string; visual: string; visual_text: string }
type Explanation = {
  job_id: string
  source_type: string
  extracted_text: string
  problem_title: string
  explanation: string
  scenes: Scene[]
  video_status: string
  video_url?: string | null
}

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const problemText = ref('')
const selectedFile = ref<File | null>(null)
const result = ref<Explanation | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const videoUrl = ref('')

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0] ?? null
  result.value = null
}

function clearFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function generateExplanation() {
  if (!problemText.value.trim() && !selectedFile.value) {
    errorMessage.value = '请先粘贴题目，或上传题目文件。'
    return
  }
  loading.value = true
  errorMessage.value = ''
  result.value = null
  videoUrl.value = ''
  const body = new FormData()
  if (problemText.value.trim()) body.append('text', problemText.value.trim())
  if (selectedFile.value) body.append('file', selectedFile.value)
  try {
    const response = await fetch(`${apiBase}/api/v1/problems/video`, { method: 'POST', body })
    const data = await response.json().catch(() => null)
    if (!response.ok) throw new Error(data?.detail ?? `处理失败（HTTP ${response.status}）`)
    result.value = data as Explanation
    videoUrl.value = data.video_url ? `${apiBase}${data.video_url}` : ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败，请确认后端服务已启动。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="shell">
    <header class="hero">
      <span class="eyebrow">PROBLEM → EXPLANATION VIDEO</span>
      <h1>EduMotion AI</h1>
      <p>上传一道题，让它变成一步一步看得懂的讲解。</p>
    </header>

    <section class="workspace">
      <section class="panel input-panel">
        <div class="section-heading">
          <div><span class="eyebrow">STEP 01</span><h2>导入题目</h2></div>
          <span class="tag">文字 / 图片 / PDF</span>
        </div>
        <label for="problem">直接粘贴题目</label>
        <textarea id="problem" v-model="problemText" rows="7" maxlength="12000" placeholder="例如：一个长方形的长是 8 厘米，宽是 5 厘米，它的面积是多少？"></textarea>
        <div class="or-divider"><span>或者上传题目文件</span></div>
        <label class="upload-zone" for="problem-file">
          <span class="upload-icon">↑</span>
          <strong>{{ selectedFile ? selectedFile.name : '选择题目图片或 PDF' }}</strong>
          <small>支持 TXT、PDF、PNG、JPG、WEBP，最大 15 MB</small>
          <input id="problem-file" ref="fileInput" type="file" accept=".txt,.pdf,.png,.jpg,.jpeg,.webp,image/*,application/pdf,text/plain" @change="onFileChange" />
        </label>
        <button v-if="selectedFile" class="text-button" type="button" @click="clearFile">移除文件</button>
        <button class="primary" type="button" :disabled="loading || (!problemText.trim() && !selectedFile)" @click="generateExplanation">
          {{ loading ? '正在解题、绘制动画并合成 MP4…' : '生成动画讲解视频' }}
        </button>
        <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
        <p class="hint">支持基础数量关系规则解题；配置 LLM 后可调用兼容 OpenAI 的模型服务。视频由 Pillow 绘制动画帧并通过 FFmpeg 导出。当前 MP4 暂无语音旁白。</p>
      </section>

      <section class="panel preview-panel">
        <div class="section-heading">
          <div><span class="eyebrow">STEP 02</span><h2>动画讲解分镜</h2></div>
          <span v-if="result" class="tag">{{ result.scenes.length }} 个镜头</span>
        </div>
        <div v-if="!result" class="empty-state">
          <div class="empty-icon">▶</div>
          <h3>讲解将在这里呈现</h3>
          <p>提交题目后，系统会展示识别结果与逐步讲解分镜。</p>
        </div>
        <article v-else class="storyboard">
          <div class="problem-card">
            <span class="eyebrow">识别到的题目</span>
            <h3>{{ result.problem_title }}</h3>
            <p>{{ result.extracted_text }}</p>
          </div>
          <div v-if="result.answer" class="answer-banner"><span class="eyebrow">当前答案</span><strong>{{ result.answer }}</strong><small>{{ result.verification_status === 'verified' ? '规则计算已验证' : '尚未验证，请人工核对' }}</small></div>
          <div class="timeline">
            <article v-for="(scene, index) in result.scenes" :key="scene.id" class="scene-card">
              <div class="scene-visual" :class="scene.visual">
                <span class="scene-index">0{{ index + 1 }}</span>
                <strong>{{ scene.visual_text }}</strong>
              </div>
              <div class="scene-copy">
                <span class="eyebrow">镜头 0{{ index + 1 }}</span>
                <h3>{{ scene.title }}</h3>
                <p>{{ scene.narration }}</p>
              </div>
            </article>
          </div>
          <div class="pipeline-note">
            <strong>当前进度：讲解分镜已生成</strong>
            <p>{{ result.explanation }}</p>
            <small>下一阶段：接入题目求解模型、动画渲染引擎、语音合成与 MP4 导出。</small>
          </div>
          <div v-if="videoUrl" class="video-output"><span class="eyebrow">MP4 VIDEO</span><h3>动画讲解视频已生成</h3><video :src="videoUrl" controls playsinline></video><a :href="videoUrl" download>下载 MP4 视频</a></div>
          <div class="job-id">任务编号 · {{ result.job_id }}</div>
        </article>
      </section>
    </section>
    <footer>EduMotion AI · Problem-to-Explanation workflow</footer>
  </main>
</template>
