<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { trainingApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import { speak, speechSupported, speaking, stopSpeaking, toggleSpeak } from '../utils/speech'
import AppIcon from '../components/AppIcon.vue'
import StateBlock from '../components/StateBlock.vue'

const router = useRouter()

const scenarios = ref([])
const active = ref(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const answerText = ref('')
const bodyEl = ref(null)
const autoRead = ref(localStorage.getItem('pojian_training_speech') !== '0')

function toggleAutoRead() {
  autoRead.value = !autoRead.value
  localStorage.setItem('pojian_training_speech', autoRead.value ? '1' : '0')
  if (!autoRead.value) stopSpeaking()
}

function readPrompt(view) {
  if (!autoRead.value || !view) return
  const text = view.prompt || view.feedback
  if (text) speak(text)
}

const ROLE_LABEL = { coach: '教练', child: '孩子', hint: '提示', system: '系统' }
const ROLE_AVATAR = { coach: '声', child: '我', hint: '灯', system: '·' }

const turns = computed(() => (active.value?.transcript || []).filter((item) => item.role !== 'summary'))

const progress = computed(() => {
  if (!active.value) return 0
  if (active.value.status === 'completed') return 100
  return Math.round((active.value.step_index / Math.max(active.value.total_steps, 1)) * 100)
})

onMounted(init)
onBeforeUnmount(stopSpeaking)

async function init() {
  loading.value = true
  error.value = ''
  try {
    const [{ data: catalog }, { data: sessions }] = await Promise.all([
      trainingApi.scenarios(),
      trainingApi.sessions()
    ])
    scenarios.value = catalog
    const current = sessions.find((item) => item.status === 'active')
    if (current) active.value = (await trainingApi.get(current.id)).data
  } catch (e) {
    error.value = apiError(e)
  } finally {
    loading.value = false
  }
}

async function start(key) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const { data } = await trainingApi.start({ scenario: key, child_id: store.childId })
    active.value = data
    readPrompt(data)
    await scrollBottom()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    busy.value = false
  }
}

async function respond() {
  const text = answerText.value.trim()
  if (!text || busy.value || !active.value) return
  busy.value = true
  error.value = ''
  try {
    const { data } = await trainingApi.answer(active.value.id, text)
    active.value = data
    answerText.value = ''
    if (data.status === 'active') readPrompt(data)
    await scrollBottom()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    busy.value = false
  }
}

async function finish() {
  if (busy.value || !active.value) return
  stopSpeaking()
  busy.value = true
  error.value = ''
  try {
    const { data } = await trainingApi.end(active.value.id)
    active.value = data
    await scrollBottom()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    busy.value = false
  }
}

function reset() {
  stopSpeaking()
  active.value = null
  answerText.value = ''
  error.value = ''
}

async function scrollBottom() {
  await nextTick()
  if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
}
</script>

<template>
  <div class="training-page">
    <template v-if="!active">
      <div class="page">
        <div class="page-head">
          <div>
            <p class="page-desc">
              一次只练一个场景、一次只问一个问题。孩子用手势、图片或点头回应，同样算完成；
              更适合家长代填或网络较慢时使用。
            </p>
          </div>
          <div class="row">
            <span v-if="!store.childId" class="badge amber">建议先在「儿童档案」里选择孩子</span>
            <button class="btn ghost small" @click="router.push('/game')">
              <AppIcon name="game" :size="14" />
              进入 2D 情景模拟
            </button>
          </div>
        </div>

        <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>

        <StateBlock v-if="loading" type="loading" desc="正在准备训练场景…" />
        <div v-else class="scenario-grid">
          <button
            v-for="item in scenarios"
            :key="item.key"
            class="scenario-card"
            :disabled="busy"
            @click="start(item.key)"
          >
            <span class="badge primary" style="align-self: flex-start">{{ item.steps }} 个回合</span>
            <h3>{{ item.name }}</h3>
            <p>{{ item.goal }}</p>
            <span class="go">开始这个场景 →</span>
          </button>
        </div>

        <div class="card" style="margin-top: 18px">
          <div class="card-title"><AppIcon name="heart" :size="17" /> 训练进行时，家长可以这样配合</div>
          <p class="hint" style="line-height: 1.95">
            先描述情境，等待 5～10 秒；孩子答偏时不要急着纠正，先给线索，再给开头，最后才示范。
            孩子不想继续时，说「结束训练」即可，不施压。
          </p>
        </div>
      </div>
    </template>

    <template v-else>
      <header class="training-head">
        <div class="row">
          <div>
            <div class="row center" style="gap: 8px">
              <h2 style="font-size: 18px; font-weight: 700">{{ active.scenario_name }}</h2>
              <span class="badge" :class="active.status === 'completed' ? 'secondary' : 'primary'">
                {{ active.status === 'completed' ? '已完成' : '进行中' }}
              </span>
              <span class="badge">{{ active.step_index }}/{{ active.total_steps }} 回合</span>
              <span class="badge secondary">正确回应 {{ active.correct_count }} 次</span>
            </div>
            <p class="hint" style="margin-top: 4px">{{ active.goal }}</p>
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
              {{ autoRead ? '朗读 开' : '朗读 关' }}
            </button>
            <button v-if="active.status === 'active'" class="btn ghost small" :disabled="busy" @click="finish">
              结束训练
            </button>
            <button class="btn ghost small" :disabled="busy" @click="reset">选择其他场景</button>
          </div>
        </div>
        <div class="progress"><span :style="{ width: progress + '%' }"></span></div>
      </header>

      <div ref="bodyEl" class="training-body">
        <div v-for="(item, index) in turns" :key="index" class="turn" :class="item.role">
          <div class="avatar" :class="item.role === 'child' ? 'me' : 'bot'">
            {{ ROLE_AVATAR[item.role] || '声' }}
          </div>
          <div>
            <div class="turn-label">
              {{ ROLE_LABEL[item.role] || '教练' }}
              <template v-if="item.step !== undefined"> · 第 {{ item.step + 1 }} 回合</template>
              <button
                v-if="item.role === 'coach' && speechSupported"
                class="speak-btn"
                :title="speaking ? '停止朗读' : '朗读这句话'"
                @click.stop="toggleSpeak(item.content)"
              >
                <AppIcon name="volume" :size="12" />
              </button>
            </div>
            <div class="bubble">{{ item.content }}</div>
          </div>
        </div>

        <div v-if="active.status === 'completed'" class="summary-card">{{ active.summary }}</div>
      </div>

      <footer v-if="active.status === 'active'" class="training-composer">
        <div class="composer-box">
          <textarea
            v-model="answerText"
            rows="1"
            placeholder="孩子说了什么？也可以记录「点头」「递图片」这类回应…"
            @keydown.enter.exact.prevent="respond"
          ></textarea>
          <button class="btn" :disabled="busy || !answerText.trim()" @click="respond">
            <AppIcon name="send" :size="15" />
            {{ busy ? '处理中…' : '记录回应' }}
          </button>
        </div>
        <div class="composer-hint">用孩子真实说出的原话记录，不需要替孩子组织句子。</div>
        <div v-if="error" class="error" style="margin-top: 8px">{{ error }}</div>
      </footer>
      <footer v-else class="training-composer">
        <button class="btn" @click="reset">再练一个场景</button>
      </footer>
    </template>
  </div>
</template>
