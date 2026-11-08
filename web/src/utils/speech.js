/**
 * 语音朗读：优先调用后端 CosyVoice2（音色更自然），失败时回退浏览器系统语音。
 *
 * - 后端接口 /api/v1/audio/speech 返回 audio/mpeg，不落盘；
 * - 系统语音使用 speechSynthesis，长文本按句切块，避免 Chrome 截断。
 */
import { ref } from 'vue'

export const speechSupported =
  typeof window !== 'undefined' &&
  ('speechSynthesis' in window || typeof window.Audio !== 'undefined')

export const speaking = ref(false)
// 空字符串表示“跟随服务端 .env 的 TTS_VOICE”，避免前端旧缓存覆盖配置
export const ttsVoice = ref(localStorage.getItem('pojian_tts_voice_v2') || '')
export const ttsVoices = ref([
  'FunAudioLLM/CosyVoice2-0.5B:diana',
  'FunAudioLLM/CosyVoice2-0.5B:claire',
  'FunAudioLLM/CosyVoice2-0.5B:alex'
])
export const ttsDefaultVoice = ref('')

export function setTtsVoice(voice) {
  ttsVoice.value = voice
  if (voice) localStorage.setItem('pojian_tts_voice_v2', voice)
  else localStorage.removeItem('pojian_tts_voice_v2')
}

export async function loadTtsVoices() {
  try {
    const response = await fetch('/api/v1/audio/tts/health')
    if (!response.ok) return
    const data = await response.json()
    ttsVoices.value = data.voices || []
    ttsDefaultVoice.value = data.default_voice || ''
  } catch {
    /* 后端不可用时使用 .env 默认音色 */
  }
}

let voices = []
let browserSession = 0
let generation = 0
let currentAudio = null
let currentUrl = null

function refreshVoices() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
  voices = window.speechSynthesis.getVoices() || []
}

if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
  refreshVoices()
  window.speechSynthesis.onvoiceschanged = refreshVoices
}

function pickChineseVoice() {
  return (
    voices.find((voice) => /^zh(-|_)/i.test(voice.lang)) ||
    voices.find((voice) => /chinese|中文|普通话|xiaoxiao|huihui|yaoyao/i.test(voice.name)) ||
    null
  )
}

function cleanText(text) {
  return String(text || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\[(\d+)\]/g, ' ')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/[*_#>`~]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function splitText(text, maxLength = 110) {
  const sentences = text.split(/(?<=[。！？!?；;\n])/)
  const chunks = []
  let current = ''
  for (const sentence of sentences) {
    if (!sentence) continue
    if (current && (current + sentence).length > maxLength) {
      chunks.push(current)
      current = ''
    }
    current += sentence
    if (current.length >= maxLength) {
      chunks.push(current)
      current = ''
    }
  }
  if (current.trim()) chunks.push(current)
  return chunks.map((item) => item.trim()).filter(Boolean)
}

function cleanupAudio() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.src = ''
    currentAudio = null
  }
  if (currentUrl) {
    URL.revokeObjectURL(currentUrl)
    currentUrl = null
  }
}

export function stopSpeaking() {
  generation += 1
  browserSession += 1
  cleanupAudio()
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
  speaking.value = false
}

function playBlob(blob, token) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob)
    currentUrl = url
    const audio = new Audio(url)
    currentAudio = audio
    audio.onended = () => {
      if (token === generation) {
        speaking.value = false
        cleanupAudio()
      }
      resolve(true)
    }
    audio.onerror = () => reject(new Error('audio playback failed'))
    audio.play().catch(reject)
  })
}

async function fetchSpeech(text) {
  const token = localStorage.getItem('pojian_token')
  const headers = {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true'
  }
  if (token) headers.Authorization = `Bearer ${token}`
  const payload = { text }
  if (ttsVoice.value) payload.voice = ttsVoice.value
  const response = await fetch('/api/v1/audio/speech', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  })
  if (!response.ok) throw new Error(`TTS ${response.status}`)
  return response.blob()
}

async function speakCloud(content, token) {
  // 分句流水线：第一句合成好就开始播，后面的边播边合成。
  // 供应商（硅基流动）不支持真流式，但短句并行预取 + 顺序播放，
  // 可以把「等 N 句合成完再出声」变成「等 1 句就出声」。
  const chunks = splitText(content, 60)
  if (!chunks.length) return false

  const pending = new Map()
  const ensure = (index) => {
    if (!pending.has(index)) {
      pending.set(index, fetchSpeech(chunks[index]))
    }
    return pending.get(index)
  }

  ensure(0)
  if (chunks.length > 1) ensure(1)

  for (let index = 0; index < chunks.length; index += 1) {
    const blob = await ensure(index)
    if (token !== generation) return false
    if (!(blob instanceof Blob)) throw new Error('invalid audio response')
    // 播放当前句的同时，预取后面两句
    for (let ahead = index + 1; ahead <= index + 2 && ahead < chunks.length; ahead += 1) {
      ensure(ahead)
    }
    await playBlob(blob, token)
  }
  if (token === generation) speaking.value = false
  return true
}

/**
 * 预取朗读音频：用户还没点喇叭时先把前几句合成好。
 * 服务端按文本缓存，真正点击时直接命中（毫秒级）。
 */
export async function prefetchSpeech(text, sentences = 2) {
  const content = cleanText(text)
  if (!content) return
  const chunks = splitText(content, 60).slice(0, Math.max(1, sentences))
  await Promise.allSettled(chunks.map((chunk) => fetchSpeech(chunk)))
}

function speakWithBrowser(content) {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false
  const chunkList = splitText(content)
  if (!chunkList.length) return false
  const currentSession = ++browserSession
  window.speechSynthesis.cancel()
  speaking.value = true
  const voice = pickChineseVoice()
  chunkList.forEach((chunk, index) => {
    const utterance = new SpeechSynthesisUtterance(chunk)
    if (voice) utterance.voice = voice
    utterance.lang = 'zh-CN'
    utterance.rate = 1
    utterance.pitch = 1
    utterance.onend = () => {
      if (currentSession === browserSession && index === chunkList.length - 1) {
        speaking.value = false
      }
    }
    utterance.onerror = () => {
      if (currentSession === browserSession) speaking.value = false
    }
    window.speechSynthesis.speak(utterance)
  })
  return true
}

export async function speak(text, options = {}) {
  const content = cleanText(text)
  if (!content) return false
  stopSpeaking()
  generation += 1
  const token = generation
  speaking.value = true
  try {
    return await speakCloud(content, token)
  } catch (error) {
    if (token !== generation) return false
    speaking.value = false
    return speakWithBrowser(content)
  }
}

export async function toggleSpeak(text) {
  if (speaking.value) {
    stopSpeaking()
    return
  }
  await speak(text)
}
