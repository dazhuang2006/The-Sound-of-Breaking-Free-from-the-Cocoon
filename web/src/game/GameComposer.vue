<script setup>
/**
 * 作答面板：文字 / 语音（复用后端 ASR）/ 非语言表达按钮。
 *
 * 语音识别只把文字填进输入框，由孩子或家长确认后再发送 ——
 * 与项目原有「机器识别可能有误，请核对后使用」的原则一致。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { audioApi } from '../api'
import { apiError } from '../api/client'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  nearFocus: { type: Boolean, default: false },
  gestures: { type: Array, default: () => [] },
  focusName: { type: String, default: '' },
  placeholder: { type: String, default: '孩子说了什么？也可以写下「点点头」这样的回应' }
})

const emit = defineEmits(['submit', 'approach'])

const text = ref('')
const state = ref('idle') // idle | recording | uploading
const seconds = ref(0)
const notice = ref('')
const error = ref('')

let recorder = null
let stream = null
let chunks = []
let timer = null
let blob = null
let mimeType = ''

const supported = computed(
  () =>
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia
)

const canSend = computed(
  () => !props.disabled && !props.busy && props.nearFocus && text.value.trim().length > 0
)

function pickMime() {
  const list = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return list.find((type) => MediaRecorder.isTypeSupported(type)) || ''
}

function extFor(type) {
  if (type.includes('ogg')) return '.ogg'
  if (type.includes('mp4')) return '.m4a'
  return '.webm'
}

function stopTracks() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
    stream = null
  }
}

function stopTimer() {
  if (timer) window.clearInterval(timer)
  timer = null
}

async function startRecording() {
  error.value = ''
  notice.value = ''
  if (!supported.value) {
    error.value = '当前浏览器不支持录音，可以先用文字作答'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })
    mimeType = pickMime()
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    chunks = []
    seconds.value = 0
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size) chunks.push(event.data)
    }
    recorder.onstop = () => {
      stopTracks()
      blob = new Blob(chunks, { type: mimeType || 'audio/webm' })
      if (!blob.size) {
        error.value = '没有录到声音，请靠近麦克风再试一次'
        state.value = 'idle'
        return
      }
      transcribe()
    }
    recorder.start(200)
    state.value = 'recording'
    timer = window.setInterval(() => {
      seconds.value += 1
      if (seconds.value >= 15) stopRecording()
    }, 1000)
  } catch (err) {
    stopTracks()
    state.value = 'idle'
    error.value =
      err?.name === 'NotAllowedError'
        ? '麦克风权限被拒绝，可以先用文字作答'
        : '无法访问麦克风，可以先用文字作答'
  }
}

function stopRecording() {
  stopTimer()
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  state.value = 'uploading'
}

async function transcribe() {
  if (!blob) return
  state.value = 'uploading'
  error.value = ''
  const file = new File([blob], `game${extFor(mimeType)}`, { type: mimeType || 'audio/webm' })
  try {
    const { data } = await audioApi.transcribe(file)
    const result = (data.transcription || '').trim()
    if (result) {
      text.value = result
      notice.value = '已识别成文字，核对没问题再点「说出来」'
    } else {
      error.value = '没有识别到内容，可以再试一次或直接打字'
    }
  } catch (err) {
    error.value = apiError(err)
  } finally {
    state.value = 'idle'
    blob = null
  }
}

function send() {
  const value = text.value.trim()
  if (!value || !canSend.value) return
  emit('submit', value, 'text')
  text.value = ''
  notice.value = ''
}

function pickGesture(phrase) {
  if (props.disabled || props.busy || !props.nearFocus) return
  emit('submit', phrase, 'gesture')
}

onBeforeUnmount(() => {
  stopTimer()
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  stopTracks()
})
</script>

<template>
  <div class="game-composer" :class="{ locked: !nearFocus }">
    <div v-if="!nearFocus" class="composer-lock">
      <span>先走到{{ focusName || '要说话的人' }}身边，再开口</span>
      <button class="mini-btn" @click="emit('approach')">带我过去</button>
    </div>

    <div class="composer-row">
      <textarea
        v-model="text"
        class="composer-input"
        rows="1"
        :placeholder="placeholder"
        :disabled="disabled || busy"
        @keydown.enter.exact.prevent="send"
      ></textarea>

      <button
        v-if="supported"
        class="mic-btn"
        :class="state"
        :disabled="disabled || busy"
        :title="state === 'recording' ? '停止录音' : '按住说一句'"
        @click="state === 'recording' ? stopRecording() : startRecording()"
      >
        <span v-if="state === 'recording'" class="rec-dot"></span>
        <span v-else-if="state === 'uploading'" class="rec-spin"></span>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" stroke-linecap="round" />
        </svg>
      </button>

      <button class="send-btn" :disabled="!canSend" @click="send">
        {{ busy ? '想一想…' : '说出来' }}
      </button>
    </div>

    <div v-if="gestures.length && nearFocus" class="gesture-row">
      <span class="gesture-label">不想说话？也可以——</span>
      <button
        v-for="phrase in gestures"
        :key="phrase"
        class="gesture-btn"
        :disabled="disabled || busy || !nearFocus"
        @click="pickGesture(phrase)"
      >
        {{ phrase }}
      </button>
    </div>

    <div v-if="state === 'recording'" class="recording-tip">
      正在录音 {{ seconds }}s，说完点一下麦克风停止
    </div>
    <div v-else-if="state === 'uploading'" class="recording-tip">正在把语音转成文字…</div>
    <div v-else-if="notice" class="composer-notice">{{ notice }}</div>
    <div v-if="error" class="composer-error">{{ error }}</div>
  </div>
</template>
