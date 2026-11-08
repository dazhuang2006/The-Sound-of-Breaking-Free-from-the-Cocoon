<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { chatApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import SafetyBanner from '../components/SafetyBanner.vue'
import AppIcon from '../components/AppIcon.vue'
import StateBlock from '../components/StateBlock.vue'
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
  loadTtsVoices,
  prefetchSpeech
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

// Agent 子图的节点名 → 展示用中文
const TRACE_LABEL = {
  plan_queries: '规划检索式',
  retrieve_evidence: '并行检索',
  grade_evidence: '证据评级',
  rewrite_query: '改写检索式（回环）',
  draft_answer: '生成草稿',
  self_critique: '自我审查',
  revise_answer: '修订答案（回环）',
  finalize_answer: '定稿'
}

function traceDetail(step) {
  const parts = []
  if (step.planner) parts.push(step.planner === 'llm' ? '模型规划' : '规则规划')
  if (step.queries) parts.push(`${step.queries.length} 条检索式`)
  if (step.hits !== undefined) parts.push(`命中 ${step.hits} 条`)
  if (step.coverage !== undefined) parts.push(`覆盖率 ${step.coverage}`)
  if (step.top !== undefined) parts.push(`最高分 ${step.top}`)
  if (step.enough !== undefined) parts.push(step.enough ? '证据充足' : '证据不足')
  if (step.chars) parts.push(`${step.chars} 字`)
  if (step.provider) parts.push(step.provider)
  if (step.issues !== undefined) parts.push(`${step.issues} 个待改问题`)
  if (step.strategy) parts.push(step.strategy === 'llm' ? '模型修订' : '规则修订')
  if (step.citations !== undefined) parts.push(`${step.citations} 条引用`)
  return parts.join(' · ')
}

const sessions = ref([])
const sessionId = ref(null)
const sessionTitle = ref('')
const sessionMode = ref('qa')
const messages = ref([])
const input = ref('')
const sending = ref(false)
const loadingSession = ref(false)
const error = ref('')
const loadError = ref('')
const pendingSessionId = ref(null)
const messagesEl = ref(null)
const showVoice = ref(false)
const autoRead = ref(localStorage.getItem('pojian_autoread') !== '0')

// 连续点击两个会话时，只接受最后一次请求的结果，避免旧响应覆盖新会话
let openSeq = 0

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

const MODE_LABEL = { qa: '居家答疑', training: '情景训练' }

const modeLabel = computed(() => {
  if (sessionTitle.value && MODE_LABEL[sessionMode.value]) return MODE_LABEL[sessionMode.value]
  const last = [...messages.value].reverse().find((item) => item.role === 'assistant')
  if (last?.training?.status === 'active') return '情景训练中'
  if (last?.intent === 'safety' || last?.safety?.level === 'emergency') return '安全模式'
  return '居家答疑'
})

const headerTitle = computed(() => sessionTitle.value || '新的对话')

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
  if (sending.value || !id) return
  const seq = ++openSeq
  pendingSessionId.value = id
  const chosen = sessions.value.find((item) => item.id === id)
  if (chosen) {
    sessionTitle.value = chosen.title || ''
    sessionMode.value = chosen.mode || 'qa'
  }
  stopSpeaking()
  error.value = ''
  loadError.value = ''
  loadingSession.value = true
  try {
    const { data } = await chatApi.session(id)
    if (seq !== openSeq) return
    sessionId.value = data.id
    sessionTitle.value = data.title || ''
    sessionMode.value = data.mode || 'qa'
    messages.value = (data.messages || [])
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
    if (seq !== openSeq) return
    loadError.value = apiError(e)
  } finally {
    if (seq === openSeq) loadingSession.value = false
  }
}

function newChat() {
  if (sending.value) return
  openSeq += 1
  stopSpeaking()
  sessionId.value = null
  sessionTitle.value = ''
  sessionMode.value = 'qa'
  messages.value = []
  error.value = ''
  loadError.value = ''
  pendingSessionId.value = null
  loadingSession.value = false
}

async function removeSession(item) {
  const name = item.title || '未命名对话'
  if (!window.confirm(`删除「${name}」？删除后不可恢复。`)) return
  try {
    await chatApi.remove(item.id)
    sessions.value = sessions.value.filter((session) => session.id !== item.id)
    if (sessionId.value === item.id) newChat()
  } catch (e) {
    error.value = apiError(e)
  }
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
    } else if (speechSupported) {
      // 没开自动朗读时，后台先把前两句合成好；用户点喇叭时直接命中缓存
      void prefetchSpeech(data.reply)
    }
    await loadSessions()
    // 首条消息发出后后端会给会话起标题，这里同步到右侧标题，避免一直显示「新的对话」
    const current = sessions.value.find((item) => item.id === sessionId.value)
    if (current) {
      sessionTitle.value = current.title || sessionTitle.value
      sessionMode.value = current.mode || sessionMode.value
    }
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
        <div
          v-for="item in sessions"
          :key="item.id"
          class="session-item"
          :class="{ active: item.id === sessionId }"
        >
          <button class="session-main" :title="item.title" @click="openSession(item.id)">
            {{ timeLabel(item.updated_at) }} · {{ item.title }}
          </button>
          <button class="session-del" title="删除这条对话" @click.stop="removeSession(item)">
            <AppIcon name="trash" :size="13" />
          </button>
        </div>
        <div v-if="!sessions.length" class="session-empty">还没有对话，先问一个问题吧。</div>
      </div>
    </aside>

    <section class="chat-main">
      <header class="chat-head">
        <div>
          <h2 :title="headerTitle">
            <span class="chat-title">{{ headerTitle }}</span>
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
        <StateBlock v-if="loadingSession" type="loading" desc="正在打开这个话题…" />

        <StateBlock
          v-else-if="loadError"
          type="error"
          title="这个话题没有打开"
          :desc="loadError"
          action="重试"
          @action="openSession(pendingSessionId)"
        />

        <template v-else>
          <StateBlock
            v-if="!messages.length && sessionId"
            title="这个话题还没有消息"
            desc="在下面的输入框继续提问，内容会接在这个话题里。"
          />

          <div v-else-if="!messages.length" class="empty-chat">
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

            <details v-if="item.meta?.agent_trace?.length" class="agent-trace">
              <summary>
                Agent 执行轨迹 · {{ item.meta.agent_steps }} 步
                · 检索 {{ item.meta.retrieval_rounds }} 轮<template v-if="item.meta.revisions">
                  · 自我修订 {{ item.meta.revisions }} 次</template>
              </summary>
              <ol>
                <li v-for="(step, index) in item.meta.agent_trace" :key="index">
                  <span class="trace-node">{{ TRACE_LABEL[step.node] || step.node }}</span>
                  <span class="trace-detail">{{ traceDetail(step) }}</span>
                </li>
              </ol>
            </details>
          </div>
        </div>

        <div v-if="sending" class="msg assistant">
          <div class="avatar bot">声</div>
          <div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>
        </div>
        </template>
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
          <button class="btn" :disabled="sending || !input.trim()" @click="send()">
            <AppIcon name="send" :size="15" />
            发送
          </button>
        </div>
        <div class="composer-hint">Enter 发送 · Shift + Enter 换行 · 所有回答仅供居家辅助参考</div>
        <div v-if="error" class="error" style="margin-top: 8px">{{ error }}</div>
      </footer>
    </section>
  </div>
</template>
