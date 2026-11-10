<script setup lang="ts">
import { ref } from 'vue'

type Scene = { id: string; title: string; narration: string; visual: string; visual_text: string }
type Explanation = {
  job_id: string
  answer?: string | null
  verification_status?: 'verified' | 'unverified'
  source_type: string
  extracted_text: string
  problem_title: string
  explanation: string
  scenes: Scene[]
  video_status: string
  video_url?: string | null
}
type Job = {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  stage: string
  result?: Explanation | null
  video_url?: string | null
  error?: string | null
}

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const problemText = ref('')
const selectedFile = ref<File | null>(null)
const result = ref<Explanation | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const videoUrl = ref('')
const jobProgress = ref(0)
const jobStage = ref('')
const jobId = ref('')

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0] ?? null
  result.value = null
  videoUrl.value = ''
}

function clearFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function wait(milliseconds: number) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds))
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
  jobProgress.value = 0
  jobStage.value = '正在提交任务…'
  const body = new FormData()
  if (problemText.value.trim()) body.append('text', problemText.value.trim())
  if (selectedFile.value) body.append('file', selectedFile.value)
  try {
    const response = await fetch(apiBase + '/api/v1/problems/video', { method: 'POST', body })
    const queued = await response.json().catch(() => null) as Job | null
    if (!response.ok || !queued) {
      throw new Error((queued as any)?.detail ?? '任务提交失败（HTTP ' + response.status + '）')
    }
    jobId.value = queued.job_id
    jobStage.value = queued.stage

    while (true) {
      await wait(1500)
      const statusResponse = await fetch(apiBase + '/api/v1/problems/jobs/' + queued.job_id)
      const job = await statusResponse.json().catch(() => null) as Job | null
      if (!statusResponse.ok || !job) throw new Error('获取任务状态失败，请稍后重试。')
      jobProgress.value = job.progress
      jobStage.value = job.stage
      if (job.status === 'failed') throw new Error(job.error ?? '视频生成失败。')
      if (job.status === 'completed' && job.result) {
        result.value = job.result
        videoUrl.value = job.video_url ? apiBase + job.video_url : ''
        break
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败，请确认 API、Redis 和 Worker 已启动。'
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
          {{ loading ? '后台正在生成中文配音视频…' : '生成中文配音讲解视频' }}
        </button>
        <div v-if="loading" class="job-progress" aria-live="polite">
          <div class="progress-heading"><strong>{{ jobStage }}</strong><span>{{ jobProgress }}%</span></div>
          <div class="progress-track"><span :style="{ width: jobProgress + '%' }"></span></div>
          <small>任务编号 · {{ jobId || '提交中' }}</small>
        </div>
        <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
        <p class="hint">系统在后台完成解题、中文语音合成和 MP4 音画合成。请保持页面打开以查看实时进度。</p>
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
            <strong>生成完成：中文配音与动画已合成</strong>
            <p>{{ result.explanation }}</p>
            <small>每个分镜按语音时长自动调整画面时长，MP4 已包含中文旁白。</small>
          </div>
          <div v-if="videoUrl" class="video-output"><span class="eyebrow">MP4 VIDEO</span><h3>动画讲解视频已生成</h3><video :src="videoUrl" controls playsinline></video><a :href="videoUrl" download>下载 MP4 视频</a></div>
          <div class="job-id">任务编号 · {{ result.job_id }}</div>
        </article>
      </section>
    </section>
    <footer>EduMotion AI · Problem-to-Explanation workflow</footer>
  </main>
</template>
