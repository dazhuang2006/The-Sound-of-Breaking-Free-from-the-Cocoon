<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { audioApi } from '../api'
import { apiError } from '../api/client'

const props = defineProps({
  maxSeconds: { type: Number, default: 120 },
  compact: { type: Boolean, default: false }
})
const emit = defineEmits(['transcribed'])

const state = ref('idle') // idle | recording | paused | recorded | uploading | done | error
const seconds = ref(0)
const progress = ref(0)
const transcript = ref('')
const errorMessage = ref('')
const audioUrl = ref('')

let recorder = null
let stream = null
let chunks = []
let timer = null
let blob = null
let startedAt = 0
let elapsedBeforePause = 0
let mimeType = ''

const supported = computed(
  () =>
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia
)
const timeText = computed(() => {
  const total = Math.floor(seconds.value)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})
const maxText = computed(() => {
  const total = Math.floor(props.maxSeconds)
  return `${Math.floor(total / 60)} 分 ${total % 60} 秒`
})
const title = computed(() => {
  if (state.value === 'idle') return '用说的，更快'
  if (state.value === 'recording') return '正在录音'
  if (state.value === 'paused') return '已暂停'
  if (state.value === 'recorded') return '录好了，可以试听'
  if (state.value === 'uploading') return '正在识别语音'
  if (state.value === 'done') return '识别完成，请核对文字'
  return '录音遇到问题'
})
const subtitle = computed(() => {
  if (state.value === 'idle') return `点击麦克风开始，最长 ${maxText.value}；录音只在点击后发生`
  if (state.value === 'recording') return '说完后点“停止”，不会自动上传'
  if (state.value === 'paused') return '可以继续录制，或直接停止'
  if (state.value === 'recorded') return '先听听是否清楚，再提交识别'
  if (state.value === 'uploading') return '音频只用于本次识别，完成后立即删除'
  if (state.value === 'done') return '机器识别可能有误，请修改后再交给 AI 整理'
  return '可以重新录制，已录内容不会丢失'
})

function pickMime() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/mp4'
  ]
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || ''
}

function extFor(type) {
  if (type.includes('ogg')) return '.ogg'
  if (type.includes('mp4')) return '.m4a'
  if (type.includes('wav')) return '.wav'
  return '.webm'
}

function stopTracks() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
    stream = null
  }
}

function tick() {
  if (state.value !== 'recording') return
  seconds.value = Math.min(props.maxSeconds, elapsedBeforePause + (Date.now() - startedAt) / 1000)
  if (seconds.value >= props.maxSeconds) stop()
}

async function start() {
  if (!supported.value) {
    state.value = 'error'
    errorMessage.value = '当前浏览器不支持录音，请使用最新版 Chrome / Edge'
    return
  }
  errorMessage.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })
    mimeType = pickMime()
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    chunks = []
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size) chunks.push(event.data)
    }
    recorder.onstop = finalize
    elapsedBeforePause = 0
    seconds.value = 0
    startedAt = Date.now()
    recorder.start(200)
    state.value = 'recording'
    timer = window.setInterval(tick, 200)
  } catch (error) {
    stopTracks()
    state.value = 'error'
    errorMessage.value =
      error?.name === 'NotAllowedError'
        ? '麦克风权限被拒绝。请点击地址栏的麦克风图标允许后重试。'
        : `无法访问麦克风：${error?.message || error?.name || '未知错误'}`
  }
}

function pause() {
  if (!recorder || recorder.state !== 'recording') return
  recorder.pause()
  elapsedBeforePause = seconds.value
  window.clearInterval(timer)
  state.value = 'paused'
}

function resume() {
  if (!recorder || recorder.state !== 'paused') return
  recorder.resume()
  startedAt = Date.now()
  timer = window.setInterval(tick, 200)
  state.value = 'recording'
}

function stop() {
  window.clearInterval(timer)
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  stopTracks()
}

function finalize() {
  blob = new Blob(chunks, { type: mimeType || 'audio/webm' })
  if (!blob.size) {
    state.value = 'error'
    errorMessage.value = '没有录到声音，请靠近麦克风重试'
    return
  }
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
  audioUrl.value = URL.createObjectURL(blob)
  state.value = 'recorded'
  if (props.compact) transcribe()
}

async function transcribe() {
  if (!blob) return
  state.value = 'uploading'
  progress.value = 0
  errorMessage.value = ''
  const file = new File([blob], `voice${extFor(mimeType)}`, { type: mimeType || 'audio/webm' })
  try {
    const { data } = await audioApi.transcribe(file, (event) => {
      if (event.total) progress.value = Math.min(99, Math.round((event.loaded / event.total) * 100))
    })
    transcript.value = data.transcription || ''
    if (props.compact) {
      emit('transcribed', transcript.value)
      reset()
      return
    }
    state.value = 'done'
  } catch (error) {
    state.value = 'error'
    errorMessage.value = apiError(error)
  }
}

function useTranscript() {
  const text = transcript.value.trim()
  if (!text) return
  emit('transcribed', text)
}

function reset() {
  window.clearInterval(timer)
  stopTracks()
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
  recorder = null
  audioUrl.value = ''
  blob = null
  chunks = []
  seconds.value = 0
  progress.value = 0
  transcript.value = ''
  errorMessage.value = ''
  state.value = 'idle'
}

onBeforeUnmount(() => {
  window.clearInterval(timer)
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  stopTracks()
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
})
</script>

<template>
  <div class="recorder" :class="[state, { compact }]">
    <div class="rec-main">
      <button
        v-if="state === 'idle' || state === 'error'"
        class="rec-mic"
        :disabled="!supported"
        title="开始录音"
        @click="start"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" stroke-linecap="round" />
        </svg>
      </button>
      <button
        v-else-if="state === 'recording' || state === 'paused'"
        class="rec-mic active"
        title="停止录音"
        @click="stop"
      >
        <span class="rec-square"></span>
      </button>
      <div v-else class="rec-badge">
        <span v-if="state === 'uploading'" class="rec-spinner"></span>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="m5 13 4 4L19 7" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </div>

      <div class="rec-info">
        <div class="rec-title">
          {{ title }}
          <span v-if="state === 'recording' || state === 'paused'" class="rec-timer">{{ timeText }}</span>
        </div>
        <div class="rec-sub">{{ subtitle }}</div>
      </div>
    </div>

    <div v-if="state === 'recording' || state === 'paused'" class="rec-live">
      <span v-for="index in 12" :key="index" class="wave" :class="{ run: state === 'recording' }"></span>
    </div>

    <div v-if="state === 'recording' || state === 'paused'" class="rec-actions">
      <button v-if="state === 'recording'" class="btn ghost small" @click="pause">暂停</button>
      <button v-else class="btn ghost small" @click="resume">继续</button>
      <button class="btn small" @click="stop">停止</button>
      <button class="btn ghost small" @click="reset">取消</button>
    </div>

    <template v-if="state === 'recorded'">
      <audio class="rec-audio" :src="audioUrl" controls preload="metadata"></audio>
      <div class="rec-actions">
        <button class="btn small" @click="transcribe">提交识别</button>
        <button class="btn ghost small" @click="reset">重新录制</button>
      </div>
    </template>

    <div v-if="state === 'uploading'" class="rec-progress">
      <span :style="{ width: Math.max(progress, 8) + '%' }"></span>
    </div>

    <template v-if="state === 'done'">
      <textarea
        v-model="transcript"
        class="textarea rec-text"
        rows="4"
        placeholder="识别结果会出现在这里，可以直接修改"
      ></textarea>
      <div class="rec-meta">{{ transcript.length }} 字 · 机器识别结果，请核对后使用</div>
      <div class="rec-actions">
        <button class="btn small" :disabled="!transcript.trim()" @click="useTranscript">使用这段文字</button>
        <button class="btn ghost small" @click="transcribe">重新识别</button>
        <button class="btn ghost small" @click="reset">重新录制</button>
      </div>
    </template>

    <div v-if="state === 'error'" class="rec-error">
      {{ errorMessage }}
      <div class="rec-actions">
        <button v-if="blob" class="btn small" @click="transcribe">重试识别</button>
        <button class="btn ghost small" @click="reset">重新录制</button>
      </div>
    </div>

    <div v-if="!supported" class="rec-error">
      当前浏览器不支持录音，请使用最新版 Chrome 或 Edge。
    </div>
  </div>
</template>
