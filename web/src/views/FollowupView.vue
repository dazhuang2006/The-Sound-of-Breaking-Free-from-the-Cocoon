<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { followupApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'

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
    error.value = '请先在「孩子档案」里添加并选择孩子'
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
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">康复随访</h1>
        <p class="page-desc">每天一两分钟记录情绪、睡眠与训练完成度，连续记录后再看变化。</p>
      </div>
      <span v-if="!store.childId" class="badge amber">请先选择孩子档案</span>
    </div>

    <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>
    <div v-if="notice" class="badge teal" style="margin-bottom: 14px">{{ notice }}</div>

    <div class="followup-layout">
      <section class="card">
        <div class="card-title">今日记录</div>
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

        <button class="btn" style="margin-top: 16px" :disabled="saving || !store.childId" @click="submit">
          {{ saving ? '保存中…' : '保存今天的记录' }}
        </button>
      </section>

      <section>
        <div class="card">
          <div class="card-title">阶段小结</div>
          <div class="row" style="align-items: center; margin-bottom: 12px">
            <select v-model.number="days" class="select" style="width: 140px">
              <option :value="7">近 7 天</option>
              <option :value="14">近 14 天</option>
              <option :value="30">近 30 天</option>
            </select>
            <button class="btn small" :disabled="summarizing || !store.childId" @click="generateSummary">
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
          <div v-else class="empty-state" style="padding: 26px 10px">
            <b>还没有阶段小结</b>连续记录几天后，可以生成一份客观的阶段小结。
          </div>
        </div>

        <div class="card">
          <div class="card-title">最近记录</div>
          <div v-if="loading" class="hint">加载中…</div>
          <div v-else-if="!orderedRecords.length" class="empty-state" style="padding: 26px 10px">
            <b>还没有记录</b>从今天开始，一两句话也可以。
          </div>
          <div v-for="record in orderedRecords" :key="record.id" class="record">
            <div class="record-head">
              <span class="record-date">{{ record.record_date }}</span>
              <span class="badge">情绪 {{ record.mood }}/5 · {{ moodText(record.mood) }}</span>
              <span class="badge">睡眠 {{ record.sleep_hours }}h</span>
              <span class="badge teal">完成 {{ record.completion }}%</span>
            </div>
            <p v-if="record.behavior">{{ record.behavior }}</p>
            <div v-if="record.training_items?.length" style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap">
              <span v-for="item in record.training_items" :key="item" class="badge accent">{{ item }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
