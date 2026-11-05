<script setup>
import { onMounted, reactive, ref } from 'vue'
import { childrenApi } from '../api'
import { apiError } from '../api/client'
import { loadChildren, setChild, store } from '../store'

const form = reactive({ nickname: '', birth_date: '', profile_note: '' })
const busy = ref(false)
const error = ref('')
const notice = ref('')

onMounted(async () => {
  try {
    await loadChildren()
  } catch (e) {
    error.value = apiError(e)
  }
})

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
    await loadChildren()
    setChild(data.id)
    form.nickname = ''
    form.birth_date = ''
    form.profile_note = ''
    notice.value = '档案已创建'
  } catch (e) {
    error.value = apiError(e)
  } finally {
    busy.value = false
  }
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
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">孩子档案</h1>
        <p class="page-desc">档案只保存家长自述的信息，不做任何诊断结论；随访与训练都会归到当前孩子名下。</p>
      </div>
    </div>

    <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>
    <div v-if="notice" class="badge teal" style="margin-bottom: 14px">{{ notice }}</div>

    <div class="followup-layout">
      <section>
        <div class="card">
          <div class="card-title">已建立档案</div>
          <div v-if="!store.children.length" class="empty-state" style="padding: 24px 10px">
            <b>还没有孩子档案</b>添加后，答疑与随访会更具针对性。
          </div>
          <div v-else class="child-grid">
            <div
              v-for="child in store.children"
              :key="child.id"
              class="child-card"
              :class="{ current: child.id === store.childId }"
            >
              <div class="child-name">
                {{ child.nickname }}
                <span v-if="child.id === store.childId" class="badge accent">当前</span>
              </div>
              <div class="hint">{{ ageText(child.birth_date) }}</div>
              <div class="child-note">{{ child.profile_note || '暂无补充说明' }}</div>
              <button
                v-if="child.id !== store.childId"
                class="btn ghost small"
                style="align-self: flex-start; margin-top: 4px"
                @click="setChild(child.id)"
              >
                设为当前孩子
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-title">添加孩子</div>
        <div class="field">
          <label>昵称</label>
          <input v-model="form.nickname" class="input" placeholder="例如：小星" @keyup.enter="submit" />
        </div>
        <div class="field" style="margin-top: 12px">
          <label>出生日期（可选）</label>
          <input v-model="form.birth_date" type="date" class="input" />
        </div>
        <div class="field" style="margin-top: 12px">
          <label>家长自述（可选）</label>
          <textarea
            v-model="form.profile_note"
            class="textarea"
            placeholder="例如：4 岁半，能说少量单词，喜欢拼图；对广播声和吸尘器声音敏感。"
          ></textarea>
        </div>
        <button class="btn" style="margin-top: 16px" :disabled="busy || !form.nickname.trim()" @click="submit">
          {{ busy ? '保存中…' : '创建档案' }}
        </button>
        <p class="hint" style="margin-top: 10px">
          请勿在此填写医院诊断结论或用药信息；这些内容应由专业医生记录与解释。
        </p>
      </section>
    </div>
  </div>
</template>
