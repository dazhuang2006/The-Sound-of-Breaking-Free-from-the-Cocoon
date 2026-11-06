<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { chatApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import SafetyBanner from '../components/SafetyBanner.vue'
import VoiceRecorder from '../components/VoiceRecorder.vue'
import AppIcon from '../components/AppIcon.vue'
import {
  speak,
  speechSupported,
  speaking,
  stopSpeaking,
  toggleSpeak,
  ttsVoice,
  ttsVoices,
  ttsDefaultVoice,
  setTtsVoice,
  loadTtsVoices
} from '../utils/speech'

const route = useRoute()

const INTENT_LABEL = {
  qa: '康复答疑',
  training_start: '开始训练',
  training_turn: '训练互动',
  training_end: '训练小结',
  followup_record: '随访记录',
  followup_summary: '阶段总结',
  chat: '对话',
  safety: '安全提示'
}

const sessions = ref([])
const sessionId = ref(null)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const error = ref('')
const messagesEl = ref(null)
const showVoice = ref(false)
const autoRead = ref(localStorage.getItem('pojian_autoread') !== '0')

function toggleAutoRead() {
  autoRead.value = !autoRead.value
  localStorage.setItem('pojian_autoread', autoRead.value ? '1' : '0')
  if (!autoRead.value) stopSpeaking()
}

function voiceLabel(voice) {
  const name = String(voice || '').split(':').pop() || '默认'
  return name.charAt(0).toUpperCase() + name.slice(1)
}

const chips = [
  '孩子晚上不肯睡觉怎么办',
  '孩子在超市突然躺地上怎么处理',
  '开始训练：道谢',
  '结束训练',
  '生成阶段总结'
]

const starters = [
  {
    title: '睡前情绪',
    question: '孩子晚上特别兴奋，怎么安排睡前流程？',
    desc: '把睡前拆成固定、可预测的小步骤'
  },
  {
    title: '公共场所行为',
    question: '孩子在超市突然躺地上，我该怎么处理？',
    desc: '先保证安全，再减少围观压力'
  },
  {
    title: '主动表达',
    question: '怎么在家练习主动说「谢谢」？',
    desc: '从一次具体的小帮忙开始'
  }
]

const modeLabel = computed(() => {
  const last = [...messages.value].reverse().find((item) => item.role === 'assistant')
  if (last?.training?.status === 'active') return '情景训练中'
  if (last?.intent === 'safety' || last?.safety?.level === 'emergency') return '安全模式'
  return '居家答疑'
})

onMounted(() => {
  loadSessions()
  loadTtsVoices()
  const question = route.query.q
  if (typeof question === 'string' && question.trim()) input.value = question.trim()
})

watch(
  () => route.query.q,
  (question) => {
    if (typeof question === 'string' && question.trim()) input.value = question.trim()
  }
)

onBeforeUnmount(stopSpeaking)

async function loadSessions() {
  try {
    const { data } = await chatApi.sessions()
    sessions.value = data
  } catch {
    /* 会话列表失败不阻塞主流程 */
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

async function openSession(id) {
  if (sending.value) return
  stopSpeaking()
  error.value = ''
  try {
    const { data } = await chatApi.session(id)
    sessionId.value = data.id
    messages.value = data.messages
      .filter((item) => item.role !== 'system')
      .map((item) => ({
        role: item.role,
        content: item.content,
        citations: item.citations || [],
        safety: item.safety_level && item.safety_level !== 'normal' ? { level: item.safety_level } : null,
        intent: item.intent
      }))
    await scrollToBottom()
  } catch (e) {
    error.value = apiError(e)
  }
}

function newChat() {
  if (sending.value) return
  stopSpeaking()
  sessionId.value = null
  messages.value = []
  error.value = ''
}

async function send(text) {
  const content = (typeof text === 'string' ? text : input.value).trim()
  if (!content || sending.value) return
  stopSpeaking()
  error.value = ''
  messages.value.push({ role: 'user', content })
  input.value = ''
  sending.value = true
  await scrollToBottom()
  try {
    const { data } = await chatApi.send({
      message: content,
      session_id: sessionId.value,
      child_id: store.childId
    })
    sessionId.value = data.session_id
    messages.value.push({
      role: 'assistant',
      content: data.reply,
      citations: data.citations || [],
      safety: data.safety,
      intent: data.intent,
      meta: data.meta,
      training: data.training
    })
    if (autoRead.value) {
      setTimeout(() => speak(data.reply), 300)
    }
    await loadSessions()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function resize(event) {
  const el = event.target
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 150)}px`
}

function onVoiceTranscript(text) {
  input.value = input.value.trim() ? `${input.value.trim()}${text}` : text
  showVoice.value = false
  nextTick(() => {
    const el = document.querySelector('.composer-box textarea')
    if (el) el.focus()
  })
}

function timeLabel(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : `${date.getMonth() + 1}/${date.getDate()}`
}
</script>

<template>
  <div class="chat-page">
    <aside class="chat-aside">
      <div class="chat-aside-head">
        <div class="chat-aside-title">对话记录</div>
        <button class="btn soft small" @click="newChat">
          <AppIcon name="plus" :size="14" />
          新对话
        </button>
      </div>
      <div class="session-list">
        <button
          v-for="item in sessions"
          :key="item.id"
          class="session-item"
          :class="{ active: item.id === sessionId }"
          :title="item.title"
          @click="openSession(item.id)"
        >
          {{ timeLabel(item.updated_at) }} · {{ item.title }}
        </button>
        <div v-if="!sessions.length" class="session-empty">还没有对话，先问一个问题吧。</div>
      </div>
    </aside>

    <section class="chat-main">
      <header class="chat-head">
        <div>
          <h2>
            新的对话
            <span class="mode-pill">{{ modeLabel }}</span>
          </h2>
          <div class="sub">
            {{ store.childId ? '已关联孩子档案，回答会参考近期随访记录' : '未选择孩子档案，回答为通用建议' }}
          </div>
        </div>
        <div class="row center" style="gap: 8px">
          <button
            v-if="speechSupported"
            class="badge toggle"
            :class="{ on: autoRead }"
            :title="autoRead ? '关闭自动朗读' : '开启自动朗读'"
            @click="toggleAutoRead"
          >
            <AppIcon name="volume" :size="13" />
            {{ autoRead ? '自动朗读 开' : '自动朗读 关' }}
          </button>
          <select
            v-if="speechSupported"
            class="voice-select"
            :value="ttsVoice"
            title="朗读音色"
            @change="setTtsVoice($event.target.value)"
          >
            <option value="">
              跟随服务端（{{ ttsDefaultVoice ? voiceLabel(ttsDefaultVoice) : '默认' }}）
            </option>
            <option v-for="voice in ttsVoices" :key="voice" :value="voice">
              {{ voiceLabel(voice) }}
            </option>
          </select>
        </div>
      </header>

      <div ref="messagesEl" class="messages">
        <div v-if="!messages.length" class="empty-chat">
          <div class="empty-chat-head">
            <div class="avatar bot" style="width: 44px; height: 44px; border-radius: 16px">
              <AppIcon name="sparkles" :size="20" />
            </div>
            <div>
              <h3>今天想聊点什么？</h3>
              <p>描述一个具体的居家困扰，或者从下面的常见问题开始。</p>
            </div>
          </div>
          <div class="starter-grid">
            <button v-for="item in starters" :key="item.title" class="starter-card" @click="send(item.question)">
              <b>{{ item.title }}</b>
              <span>{{ item.desc }}</span>
            </button>
          </div>
          <p class="hint">也可以直接说「开始训练」，陪孩子练一次情景沟通。</p>
        </div>

        <div
          v-for="(item, index) in messages"
          :key="index"
          class="msg"
          :class="item.role === 'user' ? 'user' : 'assistant'"
        >
          <div class="avatar" :class="item.role === 'user' ? 'me' : 'bot'">
            {{ item.role === 'user' ? '我' : '声' }}
          </div>
          <div class="msg-body">
            <SafetyBanner
              v-if="item.safety && item.safety.level !== 'normal'"
              :level="item.safety.level"
              :categories="item.safety.categories"
            />
            <div class="bubble">{{ item.content }}</div>
            <div v-if="item.role === 'assistant'" class="msg-meta">
              <span class="badge primary">{{ INTENT_LABEL[item.intent] || item.intent }}</span>
              <span v-if="item.training && item.training.status === 'active'" class="badge secondary">
                训练 {{ item.training.step_index }}/{{ item.training.total_steps }}
              </span>
              <span v-if="item.meta?.mocked" class="badge">Mock 模式</span>
              <span v-if="item.intent === 'qa' && item.citations?.length">
                {{ item.citations.length }} 条知识来源
              </span>
              <button
                v-if="speechSupported"
                class="speak-btn"
                :title="speaking ? '停止朗读' : '朗读这条回答'"
                @click.stop="toggleSpeak(item.content)"
              >
                <AppIcon name="volume" :size="12" />
              </button>
            </div>
            <details v-if="item.citations?.length" class="citations">
              <summary>查看知识来源（{{ item.citations.length }}）</summary>
              <div v-for="citation in item.citations" :key="citation.index" class="citation-item">
                <div>
                  [{{ citation.index }}] 《{{ citation.title }}》
                  <template v-if="citation.section"> · {{ citation.section }}</template>
                  <span class="src">{{ citation.source }}</span>
                </div>
                <p>{{ citation.snippet }}</p>
              </div>
            </details>
          </div>
        </div>

        <div v-if="sending" class="msg assistant">
          <div class="avatar bot">声</div>
          <div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>
        </div>
      </div>

      <footer class="composer">
        <div class="chips">
          <button v-for="chip in chips" :key="chip" class="chip" @click="send(chip)">{{ chip }}</button>
        </div>
        <div class="composer-box">
          <textarea
            v-model="input"
            rows="1"
            placeholder="描述孩子当时的情况，或输入「开始训练」「结束训练」…"
            @keydown.enter.exact.prevent="send()"
            @input="resize"
          ></textarea>
          <button class="btn icon" title="语音输入" @click="showVoice = true">
            <AppIcon name="mic" :size="18" />
          </button>
          <button class="btn" :disabled="sending || !input.trim()" @click="send()">
            <AppIcon name="send" :size="15" />
            发送
          </button>
        </div>
        <div class="composer-hint">Enter 发送 · Shift + Enter 换行 · 所有回答仅供居家辅助参考</div>
        <div v-if="error" class="error" style="margin-top: 8px">{{ error }}</div>
      </footer>
    </section>

    <div v-if="showVoice" class="modal-mask" @click.self="showVoice = false">
      <div class="modal-card">
        <div class="modal-head">
          <div>
            <h3>语音输入</h3>
            <p class="hint">录音只在你点击后开始；识别完成会把文字填进输入框。</p>
          </div>
          <button class="modal-close" title="关闭" @click="showVoice = false">×</button>
        </div>
        <VoiceRecorder @transcribed="onVoiceTranscript" />
      </div>
    </div>
  </div>
</template>
