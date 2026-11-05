<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../api'
import { apiError } from '../api/client'
import { loadChildren, setToken, store } from '../store'

const router = useRouter()
const mode = ref('login')
const form = reactive({ username: '', password: '', display_name: '家长' })
const busy = ref(false)
const error = ref('')

async function submit() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    const payload =
      mode.value === 'login'
        ? { username: form.username.trim(), password: form.password }
        : {
            username: form.username.trim(),
            password: form.password,
            display_name: form.display_name.trim() || '家长'
          }
    const { data } = mode.value === 'login' ? await authApi.login(payload) : await authApi.register(payload)
    setToken(data.access_token)
    store.user = data.user
    await loadChildren()
    router.push({ name: 'chat' })
  } catch (e) {
    error.value = apiError(e)
  } finally {
    busy.value = false
  }
}

function fillDemo() {
  mode.value = 'login'
  form.username = 'demo'
  form.password = 'demo123456'
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <section class="login-art">
        <div class="brand-mark">破</div>
        <h1>破茧之声</h1>
        <p>为自闭症谱系儿童家庭准备的居家康复助手。<br />把专业知识拆成今天就能做的一小步。</p>
        <ul>
          <li>知识库检索，回答标注来源</li>
          <li>六类情景沟通训练，分层提示不逼迫</li>
          <li>每日记录与阶段随访小结</li>
          <li>医疗安全规则拦截，不越界诊断</li>
        </ul>
        <div class="foot">仅供居家辅助参考，不构成医疗诊断与治疗方案。</div>
      </section>

      <section class="login-form">
        <div class="login-tabs">
          <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
          <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
        </div>

        <div class="field">
          <label>用户名</label>
          <input v-model="form.username" class="input" autocomplete="username" placeholder="字母、数字或下划线" @keyup.enter="submit" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="form.password" class="input" type="password" autocomplete="current-password" placeholder="至少 6 位" @keyup.enter="submit" />
        </div>
        <div v-if="mode === 'register'" class="field">
          <label>称呼</label>
          <input v-model="form.display_name" class="input" placeholder="例如：小星妈妈" @keyup.enter="submit" />
        </div>

        <div v-if="error" class="error">{{ error }}</div>

        <button class="btn" :disabled="busy || !form.username || !form.password" @click="submit">
          {{ busy ? '请稍候…' : mode === 'login' ? '进入破茧之声' : '创建账号并进入' }}
        </button>

        <div class="demo-tip">
          演示账号：<b>demo / demo123456</b>（需先运行 <code>python -m scripts.seed_demo</code>）
          <a href="#" style="color: var(--accent-dark)" @click.prevent="fillDemo">一键填入</a>
        </div>
      </section>
    </div>
  </div>
</template>
