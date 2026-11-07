<script setup>
import { computed, onMounted, ref } from 'vue'
import { audioApi, authApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import AppIcon from '../components/AppIcon.vue'
import {
  loadTtsVoices,
  setTtsVoice,
  speechSupported,
  ttsDefaultVoice,
  ttsVoice,
  ttsVoices
} from '../utils/speech'

const loading = ref(true)
const error = ref('')
const notice = ref('')
const profile = ref(null)
const ttsHealth = ref(null)
const asrHealth = ref(null)
const health = ref(null)

const reduceMotion = ref(document.documentElement.dataset.reduceMotion === 'true')
const autoReadChat = ref(localStorage.getItem('pojian_autoread') !== '0')
const autoReadTraining = ref(localStorage.getItem('pojian_training_speech') !== '0')
const autoReadGame = ref(localStorage.getItem('pojian_game_speech') !== '0')

const voiceDraft = ref(ttsVoice.value)

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [meRes, ttsRes, asrRes] = await Promise.allSettled([
      authApi.me(),
      audioApi.ttsHealth(),
      audioApi.health()
    ])
    if (meRes.status === 'fulfilled') profile.value = meRes.value.data
    if (ttsRes.status === 'fulfilled') ttsHealth.value = ttsRes.value.data
    if (asrRes.status === 'fulfilled') asrHealth.value = asrRes.value.data
    try {
      const response = await fetch('/health')
      if (response.ok) health.value = await response.json()
    } catch {
      health.value = null
    }
    await loadTtsVoices()
  } catch (e) {
    error.value = apiError(e)
  } finally {
    loading.value = false
  }
}

function voiceLabel(voice) {
  const name = String(voice || '').split(':').pop() || '默认'
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function saveVoice() {
  setTtsVoice(voiceDraft.value)
  notice.value = '朗读音色已更新'
}

function toggleReduceMotion() {
  reduceMotion.value = !reduceMotion.value
  document.documentElement.dataset.reduceMotion = reduceMotion.value ? 'true' : 'false'
  localStorage.setItem('pojian_reduce_motion', reduceMotion.value ? '1' : '0')
}

function toggleChatRead() {
  autoReadChat.value = !autoReadChat.value
  localStorage.setItem('pojian_autoread', autoReadChat.value ? '1' : '0')
}

function toggleTrainingRead() {
  autoReadTraining.value = !autoReadTraining.value
  localStorage.setItem('pojian_training_speech', autoReadTraining.value ? '1' : '0')
}

function toggleGameRead() {
  autoReadGame.value = !autoReadGame.value
  localStorage.setItem('pojian_game_speech', autoReadGame.value ? '1' : '0')
}

const roleLabel = computed(() => (store.user?.role === 'professional' ? '康复从业者' : '家长'))
const providerLabel = computed(() => {
  const llm = health.value?.components?.llm
  if (!llm) return '未获取'
  return llm === 'mock' ? 'Mock（离线模板）' : llm
})
const chunks = computed(() => health.value?.components?.knowledge_chunks ?? '—')
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="page-desc">账号、朗读与隐私偏好都保存在本地；服务状态来自后端实时检查。</p>
      </div>
      <button class="btn ghost small" :disabled="loading" @click="load">
        <AppIcon name="refresh" :size="14" />
        刷新状态
      </button>
    </div>

    <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>
    <div v-if="notice" class="notice" style="margin-bottom: 14px">{{ notice }}</div>

    <div class="settings-grid">
      <section class="card">
        <div class="card-title"><AppIcon name="user" :size="17" /> 账号信息</div>
        <div class="kv"><span>称呼</span><b>{{ profile?.display_name || store.user?.display_name }}</b></div>
        <div class="kv"><span>登录名</span><b>{{ profile?.username || '—' }}</b></div>
        <div class="kv"><span>身份</span><b>{{ roleLabel }}</b></div>
        <div class="kv"><span>注册时间</span><b>{{ String(profile?.created_at || '').slice(0, 10) || '—' }}</b></div>
        <p class="hint" style="margin-top: 12px">
          账号只用于本机演示；生产环境请通过环境变量配置随机 <code>SECRET_KEY</code>。
        </p>
      </section>

      <section class="card">
        <div class="card-title"><AppIcon name="volume" :size="17" /> 朗读与音色</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">AI 答疑自动朗读</div>
            <div class="setting-desc">回答生成后自动播放，适合不方便一直看屏幕时</div>
          </div>
          <button class="switch" :class="{ on: autoReadChat }" @click="toggleChatRead" aria-label="切换答疑自动朗读"></button>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">文字训练自动朗读</div>
            <div class="setting-desc">教练提问时自动读出，孩子可以只听不看</div>
          </div>
          <button class="switch" :class="{ on: autoReadTraining }" @click="toggleTrainingRead" aria-label="切换训练朗读"></button>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">情景游戏自动朗读</div>
            <div class="setting-desc">角色开口时自动朗读台词</div>
          </div>
          <button class="switch" :class="{ on: autoReadGame }" @click="toggleGameRead" aria-label="切换游戏朗读"></button>
        </div>
        <div v-if="speechSupported" class="field" style="margin-top: 14px">
          <label>朗读音色</label>
          <div class="row">
            <select v-model="voiceDraft" class="select grow">
              <option value="">
                跟随服务端（{{ ttsDefaultVoice ? voiceLabel(ttsDefaultVoice) : '默认' }}）
              </option>
              <option v-for="voice in ttsVoices" :key="voice" :value="voice">
                {{ voiceLabel(voice) }}
              </option>
            </select>
            <button class="btn small" @click="saveVoice">保存音色</button>
          </div>
          <p class="hint">
            TTS：{{ ttsHealth?.available ? '服务可用' : '当前不可用，将回退浏览器语音' }} ·
            {{ ttsHealth?.provider || '未知' }}
          </p>
        </div>
        <p v-else class="hint" style="margin-top: 12px">当前浏览器不支持语音合成，朗读将不可用。</p>
      </section>

      <section class="card">
        <div class="card-title"><AppIcon name="leaf" :size="17" /> 外观与动效</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">减少动态效果</div>
            <div class="setting-desc">关闭页面淡入、卡片浮起与气泡动画；系统级「减少动态效果」也会自动生效</div>
          </div>
          <button class="switch" :class="{ on: reduceMotion }" @click="toggleReduceMotion" aria-label="切换减少动态效果"></button>
        </div>
        <p class="hint" style="margin-top: 12px">
          主题色：暖陶 {{ '#' }}DDAA8C · 鼠尾草 {{ '#' }}B9C9B1 · 暖阳 {{ '#' }}F1D98F。
          所有页面共用同一套变量，修改只需改 <code>:root</code>。
        </p>
      </section>

      <section class="card">
        <div class="card-title"><AppIcon name="shield" :size="17" /> 服务状态</div>
        <div class="kv"><span>后端</span><b>{{ health?.status === 'ok' ? '正常' : health?.status || '未获取' }}</b></div>
        <div class="kv"><span>模型</span><b>{{ providerLabel }}</b></div>
        <div class="kv"><span>知识库条目</span><b>{{ chunks }}</b></div>
        <div class="kv"><span>语音识别</span><b>{{ asrHealth?.available ? '可用' : '未启用' }}</b></div>
        <div class="kv"><span>语音合成</span><b>{{ ttsHealth?.available ? '可用' : '未启用' }}</b></div>
        <p class="hint" style="margin-top: 12px">
          ASR / TTS 不可用时功能会自动降级（浏览器语音或纯文字），不会阻断训练与随访。
        </p>
      </section>

      <section class="card">
        <div class="card-title"><AppIcon name="game" :size="17" /> 情景训练入口</div>
        <p class="hint" style="line-height: 1.9; margin-bottom: 12px">
          2D 情景模拟是独立的沉浸式页面；文字版训练保留原有点按流程，适合家长代填或网络较慢时使用。
        </p>
        <div class="row">
          <router-link class="btn" to="/game">进入 2D 情景模拟</router-link>
          <router-link class="btn ghost" to="/training">文字版训练</router-link>
        </div>
      </section>

      <section class="card">
        <div class="card-title"><AppIcon name="info" :size="17" /> 关于与免责声明</div>
        <p class="hint" style="line-height: 1.9">
          破茧之声为居家康复辅助工具，所有回答基于知识库与家长记录生成，仅供居家辅助参考，
          不构成医疗诊断与治疗方案。出现急症、自伤或明显能力退行时，请优先就医。
        </p>
      </section>
    </div>
  </div>
</template>
