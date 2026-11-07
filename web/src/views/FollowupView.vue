<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { followupApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import AppIcon from '../components/AppIcon.vue'
import StateBlock from '../components/StateBlock.vue'
import TrendChart from '../components/TrendChart.vue'

const MOODS = [
  { value: 1, label: '很差' },
  { value: 2, label: '较差' },
  { value: 3, label: '一般' },
  { value: 4, label: '较好' },
  { value: 5, label: '很好' }
]

const records = ref([])
const summaries = ref([])
const loading = ref(false)
const saving = ref(false)
const summarizing = ref(false)
const error = ref('')
const notice = ref('')
const days = ref(7)
const voiceText = ref('')
const voiceDraft = ref(null)
const drafting = ref(false)
const savingDraft = ref(false)
const voiceError = ref('')

const DRAFT_FIELDS = [
  { key: 'daily_activities', label: '日常活动', placeholder: '例如：上午去公园' },
  { key: 'training_content', label: '训练内容', placeholder: '例如：拼图训练三张' },
  { key: 'behavior_observations', label: '行为表现', placeholder: '家长观察到的具体行为' },
  { key: 'emotional_state', label: '情绪情况', placeholder: '家长描述的情绪' },
  { key: 'communication_performance', label: '沟通表现', placeholder: '例如：主动说了谢谢' },
  { key: 'parent_notes', label: '家长补充', placeholder: '其他想记录的内容' }
]

const form = reactive({
  record_date: todayStr(),
  mood: 3,
  sleep_hours: 9,
  completion: 60,
  behavior: '',
  items: '图片时间表, 道谢练习',
  interaction: ''
})

const latest = computed(() => summaries.value[0] || null)
const metrics = computed(() => latest.value?.metrics || null)
const orderedRecords = computed(() => [...records.value].reverse())
const hasChild = computed(() => Boolean(store.childId))

onMounted(load)
watch(() => store.childId, load)

function todayStr() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

async function load() {
  if (!store.childId) {
    records.value = []
    summaries.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [recordRes, summaryRes] = await Promise.all([
      followupApi.records(store.childId, 14),
      followupApi.summaries(store.childId)
    ])
    records.value = recordRes.data
    summaries.value = summaryRes.data
  } catch (e) {
    error.value = apiError(e)
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!store.childId) {
    error.value = '请先在「儿童档案」里添加并选择孩子'
    return
  }
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const items = form.items
      .split(/[,，、\s]+/)
      .map((item) => item.trim())
      .filter(Boolean)
    await followupApi.createRecord({
      child_id: store.childId,
      record_date: form.record_date,
      mood: Number(form.mood),
      sleep_hours: Number(form.sleep_hours),
      completion: Number(form.completion),
      behavior: form.behavior,
      training_items: items,
      interaction: form.interaction
    })
    notice.value = '今天的记录已保存'
    form.behavior = ''
    form.interaction = ''
    await load()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    saving.value = false
  }
}

async function generateSummary() {
  if (!store.childId) return
  summarizing.value = true
  error.value = ''
  notice.value = ''
  try {
    const { data } = await followupApi.createSummary({ child_id: store.childId, days: days.value })
    summaries.value = [data, ...summaries.value]
    notice.value = '阶段小结已生成'
  } catch (e) {
    error.value = apiError(e)
  } finally {
    summarizing.value = false
  }
}

function moodText(value) {
  return MOODS.find((item) => item.value === value)?.label || '—'
}

function onTranscribed(text) {
  voiceText.value = text
  voiceDraft.value = null
  voiceError.value = ''
}

function discardVoice() {
  voiceText.value = ''
  voiceDraft.value = null
  voiceError.value = ''
}

async function generateDraft() {
  if (!store.childId) {
    voiceError.value = '请先在「儿童档案」里选择孩子'
    return
  }
  const text = voiceText.value.trim()
  if (!text) {
    voiceError.value = '请先确认转写文字'
    return
  }
  drafting.value = true
  voiceError.value = ''
  try {
    const { data } = await followupApi.voiceDraft({ transcription: text, child_id: store.childId })
    voiceDraft.value = data.draft
  } catch (e) {
    voiceError.value = apiError(e)
  } finally {
    drafting.value = false
  }
}

async function saveDraft() {
  if (!voiceDraft.value || !store.childId) return
  savingDraft.value = true
  voiceError.value = ''
  try {
    const draft = voiceDraft.value
    const behavior = [
      draft.behavior_observations,
      draft.emotional_state,
      draft.communication_performance,
      draft.parent_notes
    ]
      .filter(Boolean)
      .join('\n')
    const trainingItems = (draft.training_content || '')
      .split(/[,，、;；\s]+/)
      .map((item) => item.trim())
      .filter(Boolean)
    await followupApi.createRecord({
      child_id: store.childId,
      record_date: draft.date || form.record_date || todayStr(),
      mood: Number(form.mood),
      sleep_hours: Number(form.sleep_hours),
      completion: Number(form.completion),
      behavior: behavior || '（来自语音记录的草稿）',
      training_items: trainingItems,
      interaction: draft.daily_activities || ''
    })
    notice.value = '语音随访记录已保存'
    voiceText.value = ''
    voiceDraft.value = null
    await load()
  } catch (e) {
    voiceError.value = apiError(e)
  } finally {
    savingDraft.value = false
  }
}

const chartDays = computed(() => {
  const list = []
  const map = new Map(records.value.map((item) => [item.record_date, item]))
  const today = new Date(`${todayStr()}T00:00:00`)
  for (let i = 6; i >= 0; i -= 1) {
    const date = new Date(today)
    date.setDate(date.getDate() - i)
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
      date.getDate()
    ).padStart(2, '0')}`
    const record = map.get(key)
    list.push({
      label: `${date.getMonth() + 1}/${date.getDate()}`,
      mood: record ? record.mood : null,
      completion: record ? record.completion : 0
    })
  }
  return list
})

const moodPoints = computed(() =>
  chartDays.value.filter((item) => item.mood !== null).map((item) => ({ label: item.label, value: item.mood }))
)
const completionPoints = computed(() =>
  chartDays.value.map((item) => ({ label: item.label, value: item.completion }))
)
const avgCompletion = computed(() => {
  const values = chartDays.value.filter((item) => item.completion > 0)
  if (!values.length) return null
  return Math.round(values.reduce((sum, item) => sum + item.completion, 0) / values.length)
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="page-desc">每天一两分钟记录孩子的情绪、睡眠与训练完成度；写下的内容随时可以修改，确认后才会写入记录。</p>
      </div>
      <span v-if="!hasChild" class="badge amber">请先在「儿童档案」里选择孩子</span>
      <span v-else class="badge primary">当前：{{ store.children.find((item) => item.id === store.childId)?.nickname }}</span>
    </div>

    <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>
    <div v-if="notice" class="notice" style="margin-bottom: 14px">{{ notice }}</div>

    <div class="followup-layout">
      <div class="followup-col">
        
        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="calendar" :size="17" /> 今日记录</div>
            <span class="badge">{{ form.record_date }}</span>
          </div>

          <div class="row">
            <div class="field grow">
              <label>日期</label>
              <input v-model="form.record_date" type="date" class="input" />
            </div>
            <div class="field grow">
              <label>睡眠时长（小时）</label>
              <input v-model.number="form.sleep_hours" type="number" min="0" max="24" step="0.5" class="input" />
            </div>
          </div>

          <div class="field" style="margin-top: 14px">
            <label>今天孩子的情绪状态</label>
            <div class="mood-picker">
              <button
                v-for="mood in MOODS"
                :key="mood.value"
                class="mood-btn"
                :class="{ active: form.mood === mood.value }"
                @click="form.mood = mood.value"
              >
                <b>{{ mood.value }}</b>
                {{ mood.label }}
              </button>
            </div>
          </div>

          <div class="field" style="margin-top: 14px">
            <label>训练完成度：{{ form.completion }}%</label>
            <input v-model.number="form.completion" type="range" min="0" max="100" step="5" />
          </div>

          <div class="field" style="margin-top: 14px">
            <label>居家训练项目（用逗号分隔）</label>
            <input v-model="form.items" class="input" placeholder="例如：图片时间表, 道谢练习" />
          </div>

          <div class="field" style="margin-top: 14px">
            <label>行为表现</label>
            <textarea
              v-model="form.behavior"
              class="textarea"
              placeholder="发生了什么？当时的情境、持续多久、你怎么处理…"
            ></textarea>
          </div>

          <div class="field" style="margin-top: 14px">
            <label>亲子互动</label>
            <textarea
              v-model="form.interaction"
              class="textarea"
              style="min-height: 64px"
              placeholder="今天一起做了什么？孩子有什么回应？"
            ></textarea>
          </div>

          <button class="btn" style="margin-top: 16px" :disabled="saving || !hasChild" @click="submit">
            <AppIcon name="check" :size="15" />
            {{ saving ? '保存中…' : '保存今天的记录' }}
          </button>
        </section>
      </div>

      <div class="followup-col">
        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="chart" :size="17" /> 近 7 天趋势</div>
            <span v-if="avgCompletion !== null" class="badge secondary">平均完成度 {{ avgCompletion }}%</span>
          </div>
          <div class="field-label" style="margin-bottom: 2px">训练完成度</div>
          <TrendChart :points="completionPoints" type="bar" :max="100" color="#b9c9b1" />
          <div class="field-label" style="margin: 10px 0 2px">情绪评分（1–5）</div>
          <TrendChart
            :points="moodPoints"
            type="line"
            :min="0"
            :max="5"
            color="#ddaa8c"
            fill="rgba(221, 170, 140, 0.18)"
          />
          <div class="chart-legend">
            <span><i style="background: #b9c9b1"></i>完成度</span>
            <span><i style="background: #ddaa8c"></i>情绪</span>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="book" :size="17" /> 阶段小结</div>
            <span v-if="latest" class="badge">{{ latest.period_start }} ~ {{ latest.period_end }}</span>
          </div>
          <div class="row" style="align-items: center; margin-bottom: 12px">
            <select v-model.number="days" class="select" style="width: 132px">
              <option :value="7">近 7 天</option>
              <option :value="14">近 14 天</option>
              <option :value="30">近 30 天</option>
            </select>
            <button class="btn small" :disabled="summarizing || !hasChild" @click="generateSummary">
              {{ summarizing ? '生成中…' : '生成阶段小结' }}
            </button>
          </div>

          <div v-if="metrics" class="metric-chips">
            <span class="metric">情绪均值 <b>{{ metrics.avg_mood }}</b></span>
            <span class="metric">睡眠 <b>{{ metrics.avg_sleep_hours }}</b> h</span>
            <span class="metric">完成度 <b>{{ metrics.avg_completion }}</b>%</span>
            <span class="metric">记录 <b>{{ metrics.record_count }}</b> 条</span>
          </div>

          <div v-if="latest" class="summary-text">{{ latest.content }}</div>
          <StateBlock
            v-else
            title="还没有阶段小结"
            desc="连续记录几天后，可以生成一份客观的阶段小结。"
          />
        </section>

        <section class="card">
          <div class="card-head">
            <div class="card-title"><AppIcon name="clock" :size="17" /> 最近记录</div>
            <span class="badge">{{ records.length }} 条</span>
          </div>
          <StateBlock v-if="loading" type="loading" desc="正在读取记录…" />
          <StateBlock
            v-else-if="!orderedRecords.length"
            title="还没有记录"
            desc="从今天开始，一两句话也可以。"
          />
          <div v-for="record in orderedRecords" :key="record.id" class="record">
            <div class="record-head">
              <span class="record-date">{{ record.record_date }}</span>
              <span class="badge">情绪 {{ record.mood }}/5 · {{ moodText(record.mood) }}</span>
              <span class="badge">睡眠 {{ record.sleep_hours }}h</span>
              <span class="badge secondary">完成 {{ record.completion }}%</span>
            </div>
            <p v-if="record.behavior">{{ record.behavior }}</p>
            <div v-if="record.training_items?.length" style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap">
              <span v-for="item in record.training_items" :key="item" class="badge accent">{{ item }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
