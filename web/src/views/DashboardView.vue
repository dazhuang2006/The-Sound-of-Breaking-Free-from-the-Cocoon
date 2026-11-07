<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { followupApi, trainingApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import AppIcon from '../components/AppIcon.vue'
import StateBlock from '../components/StateBlock.vue'
import TrendChart from '../components/TrendChart.vue'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const sessions = ref([])
const catalog = ref([])
const records = ref([])
const summaries = ref([])

const STATUS_LABEL = { active: '进行中', completed: '已完成', aborted: '已放弃' }

onMounted(load)
watch(
  () => store.childId,
  () => {
    loadFollowup()
  }
)

function todayISO() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

function dateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function localDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [sessionsRes, catalogRes] = await Promise.all([trainingApi.sessions(), trainingApi.scenarios()])
    sessions.value = sessionsRes.data
    catalog.value = catalogRes.data
    await loadFollowup()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    loading.value = false
  }
}

async function loadFollowup() {
  if (!store.childId) {
    records.value = []
    summaries.value = []
    return
  }
  try {
    const [recordRes, summaryRes] = await Promise.all([
      followupApi.records(store.childId, 14),
      followupApi.summaries(store.childId)
    ])
    records.value = recordRes.data
    summaries.value = summaryRes.data
  } catch {
    records.value = []
    summaries.value = []
  }
}

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 19) return '下午好'
  return '晚上好'
})

const displayName = computed(() => store.user?.display_name || '家长')
const child = computed(() => store.children.find((item) => item.id === store.childId) || store.children[0] || null)

function ageText(birthDate) {
  if (!birthDate) return '年龄未填写'
  const birth = new Date(birthDate)
  const now = new Date()
  let months = (now.getFullYear() - birth.getFullYear()) * 12 + (now.getMonth() - birth.getMonth())
  if (now.getDate() < birth.getDate()) months -= 1
  months = Math.max(months, 0)
  const years = Math.floor(months / 12)
  const rest = months % 12
  if (years === 0) return `${rest} 个月`
  return rest ? `${years} 岁 ${rest} 个月` : `${years} 岁`
}

function scenarioName(key) {
  return catalog.value.find((item) => item.key === key)?.name || key
}

const today = todayISO()

const todaySessions = computed(() => sessions.value.filter((item) => localDate(item.created_at) === today))
const weekSessions = computed(() => {
  const limit = Date.now() - 7 * 24 * 3600 * 1000
  return sessions.value.filter((item) => new Date(item.created_at).getTime() >= limit)
})
const recentSessions = computed(() => sessions.value.slice(0, 5))

const todayRecord = computed(() => records.value.find((item) => item.record_date === today) || null)
const latestRecord = computed(() => records.value[0] || null)
const latestSummary = computed(() => summaries.value[0] || null)

const streak = computed(() => {
  if (!records.value.length) return 0
  const dates = new Set(records.value.map((item) => item.record_date))
  let count = 0
  const cursor = new Date(`${today}T00:00:00`)
  for (let i = 0; i < 60; i += 1) {
    const key = dateKey(cursor)
    if (!dates.has(key)) {
      if (i === 0) {
        cursor.setDate(cursor.getDate() - 1)
        continue
      }
      break
    }
    count += 1
    cursor.setDate(cursor.getDate() - 1)
  }
  return count
})

const plan = computed(() => {
  if (!catalog.value.length) return []
  const start = new Date().getDay() % catalog.value.length
  const items = []
  for (let i = 0; i < 3; i += 1) {
    const meta = catalog.value[(start + i) % catalog.value.length]
    if (!meta) continue
    const finished = todaySessions.value.some(
      (session) => session.scenario === meta.key && session.status === 'completed'
    )
    items.push({ ...meta, finished })
  }
  return items
})

const planDone = computed(() => plan.value.filter((item) => item.finished).length)
const planPercent = computed(() => (plan.value.length ? Math.round((planDone.value / plan.value.length) * 100) : 0))

const chartPoints = computed(() => {
  const list = []
  const map = new Map(records.value.map((item) => [item.record_date, item]))
  for (let i = 6; i >= 0; i -= 1) {
    const date = new Date(`${today}T00:00:00`)
    date.setDate(date.getDate() - i)
    const key = dateKey(date)
    list.push({
      label: `${date.getMonth() + 1}/${date.getDate()}`,
      value: map.has(key) ? map.get(key).completion : 0
    })
  }
  return list
})

const quickQuestions = [
  '孩子晚上不肯睡觉怎么办',
  '孩子在超市躺地上，我该怎么处理',
  '怎么在家练习主动打招呼'
]

function startScenario(key) {
  router.push({ name: 'game', query: { scenario: key } })
}

function goChat(question) {
  router.push({ name: 'chat', query: question ? { q: question } : {} })
}

function statusClass(status) {
  if (status === 'completed') return 'secondary'
  if (status === 'active') return 'accent'
  return ''
}

function relativeTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const day = Math.floor(diff / 86400000)
  if (day <= 0) return '今天'
  if (day === 1) return '昨天'
  if (day < 7) return `${day} 天前`
  return localDate(iso).slice(5)
}
</script>

<template>
  <div class="page">
    <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>

    <section class="dash-hero">
      <div>
        <h1 class="hero-greeting">{{ greeting }}，{{ displayName }}</h1>
        <p class="hero-meta">
          <template v-if="child">
            今天陪 <b>{{ child.nickname }}</b> 练一小段就好。
            {{ child.profile_note ? '' : '补一句孩子的兴趣或敏感点，回答会更贴合。' }}
          </template>
          <template v-else>先添加一个孩子档案，之后的训练与随访都会归到这份档案下。</template>
        </p>
        <div class="row" style="margin-top: 12px; max-width: 380px">
          <div class="progress" style="flex: 1">
            <span :style="{ width: planPercent + '%' }"></span>
          </div>
          <span class="badge primary">今日计划 {{ planDone }}/{{ plan.length }}</span>
        </div>
      </div>
      <div class="hero-actions">
        <button class="btn" :disabled="!catalog.length" @click="startScenario(plan[0]?.key || 'thanks')">
          <AppIcon name="play" :size="16" />
          开始今天的练习
        </button>
        <button class="btn ghost" @click="goChat('')">
          <AppIcon name="chat" :size="16" />
          问问 AI
        </button>
      </div>
    </section>

    <section class="stat-grid">
      <article class="stat-card">
        <div class="stat-icon"><AppIcon name="child" :size="19" /></div>
        <div>
          <div class="stat-value">{{ store.children.length }}<small>位</small></div>
          <div class="stat-label">孩子档案</div>
        </div>
      </article>
      <article class="stat-card">
        <div class="stat-icon green"><AppIcon name="game" :size="19" /></div>
        <div>
          <div class="stat-value">{{ weekSessions.length }}<small>次</small></div>
          <div class="stat-label">近 7 天训练</div>
        </div>
      </article>
      <article class="stat-card">
        <div class="stat-icon yellow"><AppIcon name="calendar" :size="19" /></div>
        <div>
          <div class="stat-value">{{ streak }}<small>天</small></div>
          <div class="stat-label">连续随访记录</div>
        </div>
      </article>
      <article class="stat-card">
        <div class="stat-icon pink"><AppIcon name="heart" :size="19" /></div>
        <div>
          <div class="stat-value">{{ todayRecord ? todayRecord.completion : latestRecord?.completion ?? 0 }}<small>%</small></div>
          <div class="stat-label">{{ todayRecord ? '今日训练完成度' : '最近一次完成度' }}</div>
        </div>
      </article>
    </section>

    <div class="dash-grid">
      <div class="dash-col">
        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="child" :size="17" /> 孩子档案概览</div>
            <router-link class="btn ghost small" to="/children">管理档案</router-link>
          </div>

          <StateBlock
            v-if="!store.children.length"
            title="还没有孩子档案"
            desc="添加昵称、出生日期和家长自述，答疑与训练会更有针对性。"
            action="去添加"
            @action="router.push('/children')"
          />
          <div v-else class="child-grid">
            <router-link
              v-for="(item, index) in store.children.slice(0, 3)"
              :key="item.id"
              to="/children"
              class="child-card"
              :class="{ current: item.id === store.childId }"
            >
              <div class="child-head">
                <div class="child-avatar" :class="['', 'green', 'blue'][index % 3]">{{ item.nickname.slice(0, 1) }}</div>
                <div>
                  <div class="child-name">
                    {{ item.nickname }}
                    <span v-if="item.id === store.childId" class="badge primary">当前</span>
                  </div>
                  <div class="child-meta">{{ ageText(item.birth_date) }}</div>
                </div>
              </div>
              <div class="child-note locked">
                <AppIcon name="lock" :size="12" />
                {{ item.profile_note ? '已填写家长自述，在档案页查看' : '暂无补充说明' }}
              </div>
            </router-link>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="sun" :size="17" /> 今日训练计划</div>
            <span class="badge">{{ planDone }}/{{ plan.length }} 已完成</span>
          </div>
          <div v-if="loading" class="state-block"><div class="skeleton skeleton-line" style="width: 80%"></div></div>
          <div v-else class="plan-list">
            <div v-for="(item, index) in plan" :key="item.key" class="plan-item" :class="{ 'plan-done': item.finished }">
              <div class="plan-index">{{ item.finished ? '✓' : index + 1 }}</div>
              <div class="plan-body">
                <div class="plan-name">{{ item.name }}</div>
                <div class="plan-desc">{{ item.goal }}</div>
              </div>
              <button v-if="!item.finished" class="btn small" @click="startScenario(item.key)">开始</button>
              <span v-else class="badge secondary">已完成</span>
            </div>
          </div>
        </section>
      </div>

      <div class="dash-col">
        <section v-if="!todayRecord" class="reminder">
          <div class="reminder-icon"><AppIcon name="calendar" :size="18" /></div>
          <div style="flex: 1">
            <b>今天还没有随访记录</b>
            <p>花两分钟记一句，情绪和完成度的变化才看得见。</p>
            <button class="btn small" style="margin-top: 9px" @click="router.push('/followup')">去记录</button>
          </div>
        </section>
        <section v-else class="reminder" style="border-color: #d9e6d0; background: linear-gradient(120deg, #f3f8ef, #fdfef9)">
          <div class="reminder-icon" style="background: var(--color-secondary-soft); color: var(--color-success)">
            <AppIcon name="check" :size="18" />
          </div>
          <div style="flex: 1">
            <b>今天已经记录过了</b>
            <p>情绪 {{ todayRecord.mood }}/5 · 睡眠 {{ todayRecord.sleep_hours }} 小时 · 完成度 {{ todayRecord.completion }}%</p>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="chart" :size="17" /> 近 7 天完成度</div>
            <router-link class="btn ghost small" to="/followup">查看随访</router-link>
          </div>
          <TrendChart :points="chartPoints" type="bar" :max="100" color="#b9c9b1" />
        </section>

        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="clock" :size="17" /> 最近训练记录</div>
            <router-link class="btn ghost small" to="/game">全部关卡</router-link>
          </div>
          <StateBlock
            v-if="!recentSessions.length && !loading"
            title="还没有训练记录"
            desc="从工作台的今日计划里挑一个场景开始吧。"
            action="去练习"
            @action="router.push('/game')"
          />
          <div v-else class="timeline">
            <div v-for="session in recentSessions" :key="session.id" class="timeline-item">
              <span class="timeline-dot" :class="{ green: session.status === 'completed' }"></span>
              <div class="timeline-body">
                <div class="timeline-title">
                  {{ scenarioName(session.scenario) }}
                  <span class="badge" :class="statusClass(session.status)" style="margin-left: 4px">
                    {{ STATUS_LABEL[session.status] || session.status }}
                  </span>
                </div>
                <div class="timeline-sub">
                  {{ relativeTime(session.created_at) }} · 第 {{ Math.min(session.step_index + 1, session.total_steps) }}/{{ session.total_steps }} 步
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="sparkles" :size="17" /> AI 助手快捷入口</div>
          </div>
          <div class="quick-grid">
            <button v-for="question in quickQuestions" :key="question" class="quick-card" @click="goChat(question)">
              <AppIcon name="chat" :size="16" />
              <span>{{ question }}</span>
            </button>
          </div>
        </section>

        <section v-if="latestSummary" class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="book" :size="17" /> 最近一次阶段小结</div>
            <span class="badge">{{ latestSummary.period_start }} ~ {{ latestSummary.period_end }}</span>
          </div>
          <p class="summary-text" style="max-height: 132px; overflow: hidden">
            {{ latestSummary.content }}
          </p>
          <router-link class="btn ghost small" style="margin-top: 10px" to="/followup">查看完整小结</router-link>
        </section>
      </div>
    </div>
  </div>
</template>
