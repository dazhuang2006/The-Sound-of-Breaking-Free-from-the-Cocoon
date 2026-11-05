<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { chatApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import SafetyBanner from '../components/SafetyBanner.vue'

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

const chips = [
  '孩子晚上不肯睡觉怎么办',
  '孩子在超市突然躺地上怎么处理',
  '开始训练：道谢',
  '结束训练',
  '生成阶段总结'
]

const modeLabel = computed(() => {
  const last = [...messages.value].reverse().find((item) => item.role === 'assistant')
  if (last?.training?.status === 'active') return '情景训练中'
  if (last?.intent === 'safety' || last?.safety?.level === 'emergency') return '安全模式'
  return '居家答疑'
})

onMounted(loadSessions)

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
  sessionId.value = null
  messages.value = []
  error.value = ''
}

async function send(text) {
  const content = (typeof text === 'string' ? text : input.value).trim()
  if (!content || sending.value) return
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
        <button class="btn ghost small" @click="newChat">＋ 新对话</button>
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
          <h2>{{ sessionId ? '对话中' : '新的对话' }}</h2>
          <div class="sub">
            {{ store.childId ? '已关联孩子档案，回答会参考近期随访记录' : '未选择孩子档案，回答为通用建议' }}
          </div>
        </div>
        <span class="mode-pill">{{ modeLabel }}</span>
      </header>

      <div ref="messagesEl" class="messages">
        <div v-if="!messages.length" class="empty-state">
          <b>今天想聊点什么？</b>
          可以问一个具体的居家困扰，例如「孩子睡前特别兴奋怎么办」；<br />
          也可以说「开始训练」，陪孩子练一次情景沟通。
        </div>

        <div v-for="(item, index) in messages" :key="index" class="msg" :class="item.role === 'user' ? 'user' : 'assistant'">
          <div class="avatar" :class="item.role === 'user' ? 'me' : 'bot'">{{ item.role === 'user' ? '我' : '声' }}</div>
          <div class="msg-body">
            <SafetyBanner v-if="item.safety && item.safety.level !== 'normal'" :level="item.safety.level" :categories="item.safety.categories" />
            <div class="bubble">{{ item.content }}</div>
            <div v-if="item.role === 'assistant'" class="msg-meta">
              <span class="badge accent">{{ INTENT_LABEL[item.intent] || item.intent }}</span>
              <span v-if="item.training && item.training.status === 'active'" class="badge teal">
                训练 {{ item.training.step_index }}/{{ item.training.total_steps }}
              </span>
              <span v-if="item.meta?.mocked" class="badge">Mock 模式</span>
              <span v-if="item.intent === 'qa' && item.citations?.length">{{ item.citations.length }} 条知识来源</span>
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
          <button class="btn" :disabled="sending || !input.trim()" @click="send()">发送</button>
        </div>
        <div class="composer-hint">Enter 发送 · Shift + Enter 换行 · 所有回答仅供居家辅助参考</div>
        <div v-if="error" class="error" style="margin-top: 8px">{{ error }}</div>
      </footer>
    </section>
  </div>
</template>
