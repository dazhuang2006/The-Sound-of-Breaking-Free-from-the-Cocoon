<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { childrenApi, followupApi, trainingApi } from '../api'
import { apiError } from '../api/client'
import { loadChildren, setChild, store } from '../store'
import AppIcon from '../components/AppIcon.vue'
import StateBlock from '../components/StateBlock.vue'

const router = useRouter()

const form = reactive({ nickname: '', birth_date: '', profile_note: '' })
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const sessions = ref([])
const stats = reactive({})
const revealed = ref(new Set())
const showAdd = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  try {
    await loadChildren()
    const { data } = await trainingApi.sessions()
    sessions.value = data
    await Promise.all(store.children.map((child) => loadChildStats(child.id)))
  } catch (e) {
    error.value = apiError(e)
  } finally {
    loading.value = false
  }
}

async function loadChildStats(childId) {
  try {
    const { data } = await followupApi.records(childId, 14)
    const withCompletion = data.filter((item) => typeof item.completion === 'number')
    const avg = withCompletion.length
      ? Math.round(withCompletion.reduce((sum, item) => sum + item.completion, 0) / withCompletion.length)
      : null
    stats[childId] = { lastRecord: data[0] || null, avg, count: data.length }
  } catch {
    stats[childId] = { lastRecord: null, avg: null, count: 0 }
  }
}

function trainingCount(childId) {
  return sessions.value.filter((item) => item.child_id === childId).length
}

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

function isRevealed(id) {
  return revealed.value.has(id)
}

function toggleReveal(id) {
  const next = new Set(revealed.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  revealed.value = next
}

async function submit() {
  if (!form.nickname.trim() || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const { data } = await childrenApi.create({
      nickname: form.nickname.trim(),
      birth_date: form.birth_date || null,
      profile_note: form.profile_note
    })
    await load()
    setChild(data.id)
    form.nickname = ''
    form.birth_date = ''
    form.profile_note = ''
    notice.value = '档案已创建，并设为当前孩子'
    showAdd.value = false
  } catch (e) {
    error.value = apiError(e)
  } finally {
    busy.value = false
  }
}

function chooseChild(id) {
  setChild(id)
  notice.value = '已切换当前孩子'
}

function openFollowup(id) {
  setChild(id)
  router.push('/followup')
}

const currentChild = computed(() => store.children.find((item) => item.id === store.childId) || null)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="page-desc">
          只保存家长自述的信息（兴趣、敏感点、沟通方式），不做任何诊断结论。
          档案仅当前账号可见，敏感备注默认折叠。
        </p>
      </div>
      <button class="btn" @click="showAdd = true">
        <AppIcon name="plus" :size="16" />
        添加孩子
      </button>
    </div>

    <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>
    <div v-if="notice" class="notice" style="margin-bottom: 14px">{{ notice }}</div>

    <div class="child-layout">
      <section class="stack">
        <StateBlock
          v-if="loading && !store.children.length"
          type="loading"
          desc="正在读取档案…"
        />
        <StateBlock
          v-else-if="!store.children.length"
          title="还没有孩子档案"
          desc="添加后，AI 答疑会参考孩子的兴趣与敏感点，训练和随访也会归到这份档案下。"
          action="添加第一个孩子"
          @action="showAdd = true"
        />
        <div v-else class="child-grid">
          <article
            v-for="(child, index) in store.children"
            :key="child.id"
            class="child-card"
            :class="{ current: child.id === store.childId }"
          >
            <div class="child-head">
              <div class="child-avatar" :class="['', 'green', 'blue'][index % 3]">
                {{ child.nickname.slice(0, 1) }}
              </div>
              <div style="min-width: 0; flex: 1">
                <div class="child-name">
                  {{ child.nickname }}
                  <span v-if="child.id === store.childId" class="badge primary">当前</span>
                </div>
                <div class="child-meta">{{ ageText(child.birth_date) }} · 建档于 {{ String(child.created_at).slice(0, 10) }}</div>
              </div>
            </div>

            <div class="child-stats">
              <span><b>{{ trainingCount(child.id) }}</b> 次训练</span>
              <span>
                <b>{{ stats[child.id]?.avg ?? '—' }}</b>
                {{ stats[child.id]?.avg !== null ? '%' : '' }} 近两周完成度
              </span>
              <span>
                最近随访
                <b>{{ stats[child.id]?.lastRecord?.record_date || '暂无' }}</b>
              </span>
            </div>

            <div v-if="child.profile_note" class="child-note" :class="{ locked: !isRevealed(child.id) }">
              <template v-if="isRevealed(child.id)">{{ child.profile_note }}</template>
              <template v-else>
                <AppIcon name="lock" :size="13" />
                家长自述已隐藏（包含兴趣与敏感点）
              </template>
            </div>
            <div v-else class="child-note locked">暂无补充说明</div>

            <div class="row" style="margin-top: 2px">
              <button v-if="!isRevealed(child.id)" class="btn ghost small" @click="toggleReveal(child.id)">
                <AppIcon name="eye" :size="14" />
                显示备注
              </button>
              <button v-else class="btn ghost small" @click="toggleReveal(child.id)">
                <AppIcon name="eyeOff" :size="14" />
                隐藏备注
              </button>
              <button class="btn ghost small" @click="openFollowup(child.id)">查看随访</button>
              <button
                v-if="child.id !== store.childId"
                class="btn soft small"
                @click="chooseChild(child.id)"
              >
                设为当前
              </button>
            </div>
          </article>
        </div>

        <section class="card">
          <div class="card-title"><AppIcon name="shield" :size="17" /> 隐私与权限</div>
          <p class="hint" style="line-height: 1.9">
            档案接口按账号隔离：所有查询都会带上当前登录用户，只能读取自己创建的档案。
            家长自述可能包含孩子的敏感信息，页面默认折叠，点击「显示备注」后才会出现在屏幕上。
            请不要在自述里填写医院诊断结论或用药信息，这些内容应由专业医生记录与解释。
          </p>
        </section>
      </section>

      <section class="stack">
        <div v-if="currentChild" class="card">
          <div class="card-title"><AppIcon name="user" :size="17" /> {{ currentChild.nickname }} 的近期情况</div>
          <div class="kv"><span>累计训练</span><b>{{ trainingCount(currentChild.id) }} 次</b></div>
          <div class="kv"><span>近两周随访记录</span><b>{{ stats[currentChild.id]?.count ?? 0 }} 条</b></div>
          <div class="kv">
            <span>平均训练完成度</span>
            <b>{{ stats[currentChild.id]?.avg ?? '—' }}{{ stats[currentChild.id]?.avg !== null ? '%' : '' }}</b>
          </div>
          <div class="kv">
            <span>最近一次情绪</span>
            <b>{{ stats[currentChild.id]?.lastRecord ? `${stats[currentChild.id].lastRecord.mood}/5` : '暂无' }}</b>
          </div>
          <button class="btn secondary block" style="margin-top: 12px" @click="openFollowup(currentChild.id)">
            记录今天的随访
          </button>
        </div>

        <div class="card">
          <div class="card-title"><AppIcon name="sparkles" :size="17" /> 小提示</div>
          <p class="hint" style="line-height: 1.9">
            自述写得越具体，AI 越容易给出可执行的建议。例如「4 岁半，能说少量单词，喜欢拼图；
            对广播声和吸尘器声音敏感」，比「语言发育慢」更有帮助。
          </p>
        </div>
      </section>
    </div>

    <div v-if="showAdd" class="modal-mask" @click.self="showAdd = false">
      <div class="modal-card">
        <div class="modal-head">
          <div>
            <h3>添加孩子档案</h3>
            <p class="hint">昵称必填，其余信息可以稍后补充。</p>
          </div>
          <button class="modal-close" @click="showAdd = false">×</button>
        </div>
        <div class="field">
          <label>昵称</label>
          <input v-model="form.nickname" class="input" placeholder="例如：小星" @keyup.enter="submit" />
        </div>
        <div class="field" style="margin-top: 12px">
          <label>出生日期（可选）</label>
          <input v-model="form.birth_date" type="date" class="input" />
        </div>
        <div class="field" style="margin-top: 12px">
          <label>家长自述（可选，默认折叠）</label>
          <textarea
            v-model="form.profile_note"
            class="textarea"
            placeholder="例如：4 岁半，能说少量单词，喜欢拼图；对广播声和吸尘器声音敏感。"
          ></textarea>
        </div>
        <div class="row" style="margin-top: 16px">
          <button class="btn" :disabled="busy || !form.nickname.trim()" @click="submit">
            {{ busy ? '保存中…' : '创建档案' }}
          </button>
          <button class="btn ghost" @click="showAdd = false">取消</button>
        </div>
        <p class="hint" style="margin-top: 10px">
          请勿填写医院诊断结论或用药信息；这些内容应由专业医生记录与解释。
        </p>
      </div>
    </div>
  </div>
</template>
