<script setup>
/**
 * 2D 情景游戏页。
 *
 * 六个关卡共用同一个引擎；本组件只负责「把后端返回的训练回合演出来」：
 * 任务卡来自后端 step.task，情境台词来自 training.prompt，提示/表扬也来自后端，
 * 前端不复制任何训练语料。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { gameApi, trainingApi } from '../api'
import { apiError } from '../api/client'
import { store } from '../store'
import { speak, stopSpeaking, speaking, toggleSpeak } from '../utils/speech'
import GameStage from '../game/GameStage.vue'
import GameThumb from '../game/GameThumb.vue'
import GameComposer from '../game/GameComposer.vue'
import { useGameEngine } from '../game/useGameEngine'
import AppIcon from '../components/AppIcon.vue'
import BrandMark from '../components/BrandMark.vue'
import '../game/game.css'

const route = useRoute()
const router = useRouter()

const phase = ref('loading') // loading | pick | play | done
const catalog = ref([])
const resumeSession = ref(null)
const training = ref(null)
const world = ref(null)
const stepIndex = ref(0)
const coach = ref({ title: '教练', text: '', tone: 'task' })
const bubbles = ref([])
const busy = ref(false)
const fading = ref(false)
const error = ref('')
const toast = ref('')
const showLog = ref(false)
const lastSaid = ref('')
const autoRead = ref(localStorage.getItem('pojian_game_speech') !== '0')
// 手动推进：角色回应读完后，由玩家点「继续」才进入下一步，不做任何自动跳转
const pendingAdvance = ref(null)

const engine = useGameEngine()

let bubbleSeq = 0
let bubbleTimers = new Map()
let stepTimer = null
let toastTimer = null
let saveTimer = null
let reactionTimer = null
let disposed = false

const steps = computed(() => world.value?.steps || [])
const step = computed(() => steps.value[Math.min(stepIndex.value, steps.value.length - 1)] || null)
const scene = computed(() => engine.scene.value)
const totalSteps = computed(() => training.value?.total_steps || steps.value.length || 3)
const progress = computed(() => {
  if (!training.value) return 0
  if (training.value.status === 'completed') return 100
  return Math.round((stepIndex.value / Math.max(totalSteps.value, 1)) * 100)
})
const focusName = computed(() => engine.focusEntity.value?.name || '要说话的人')
const stars = computed(() => {
  const correct = training.value?.correct_count ?? 0
  const total = totalSteps.value || 1
  if (correct >= total) return 3
  if (correct >= Math.ceil(total / 2)) return 2
  return 1
})
const explored = computed(() => engine.visited.value.filter((id) => id).length)
const transcript = computed(() =>
  (training.value?.transcript || []).filter((item) => item.role !== 'summary')
)
const roleLabel = { coach: '教练', child: '孩子', hint: '提示', system: '系统' }

onMounted(init)
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(stepTimer)
  clearTimeout(toastTimer)
  clearTimeout(saveTimer)
  clearTimeout(reactionTimer)
  bubbleTimers.forEach((id) => clearTimeout(id))
  bubbleTimers.clear()
  stopSpeaking()
  saveNow()
  engine.dispose()
})

watch(
  () => engine.player.walking,
  (walking, before) => {
    if (!walking && before) scheduleSave()
  }
)

async function init() {
  try {
    const [{ data: list }, { data: sessions }] = await Promise.all([
      gameApi.scenarios(),
      trainingApi.sessions()
    ])
    catalog.value = list
    // 只把「真的练过」的会话列为可继续
    const active = sessions.find((item) => item.status === 'active' && item.step_index > 0)
    resumeSession.value = active ? withScenarioName(active) : null
    phase.value = 'pick'
    // 工作台的「今日计划」会带 ?scenario=xxx 直接进关
    const wanted = route.query.scenario
    if (typeof wanted === 'string' && list.some((item) => item.scenario === wanted)) {
      await startScenario(wanted)
    }
  } catch (err) {
    error.value = apiError(err)
    phase.value = 'pick'
  }
}

function exitToDashboard() {
  stopSpeaking()
  pendingAdvance.value = null
  clearBubbles()
  saveNow()
  engine.dispose()
  router.push('/dashboard')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function startScenario(key) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const { data: turn } = await trainingApi.start({ scenario: key, child_id: store.childId })
    await loadGame(turn.id)
  } catch (err) {
    error.value = apiError(err)
  } finally {
    busy.value = false
  }
}

async function resumeGame() {
  if (!resumeSession.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await loadGame(resumeSession.value.id)
  } catch (err) {
    error.value = apiError(err)
  } finally {
    busy.value = false
  }
}

async function loadGame(id) {
  const { data } = await gameApi.session(id)
  engine.dispose()
  training.value = data.training
  world.value = data.world
  engine.init(data.world, data.state)
  phase.value = 'play'
  clearBubbles()
  stepIndex.value = Math.min(data.training.step_index, data.world.steps.length - 1)
  if (data.training.status === 'completed') {
    phase.value = 'done'
    return
  }
  await enterStep(stepIndex.value)
}

function npcOf(id, sceneData = null) {
  const list = sceneData?.npcs || scene.value?.npcs || []
  return list.find((item) => item.id === id) || null
}

/** 按字数估算「读得完」的停留时间（中文约 110ms/字，夹在 2.2–7 秒之间）。 */
function readingMs(text, min = 2200, max = 7000) {
  const length = String(text || '').length
  return Math.max(min, Math.min(max, length * 110))
}

/**
 * 手动推进：回应气泡不自动消失，也不再定时跳下一步，
 * 由玩家读完/听完后点「继续」。彻底避免「话没说完就被切走」。
 */
function queueAdvance(label, run) {
  pendingAdvance.value = { label, run }
}

async function advance() {
  const pending = pendingAdvance.value
  if (!pending) return
  pendingAdvance.value = null
  try {
    await pending.run()
  } catch (err) {
    error.value = apiError(err)
  }
}

function addBubble({ tone, name, text, anchor, anchorId, lift = 176, ms = 5200 }) {
  if (!text) return
  const key = `bubble-${++bubbleSeq}`
  const entry = { key, tone, name, text, anchor, anchorId, lift }
  bubbles.value = [...bubbles.value.slice(-2), entry]
  // ms <= 0 表示「不自动消失」，等玩家点「继续」时再由 clearBubbles 清掉
  if (ms > 0) {
    const timer = setTimeout(() => {
      bubbles.value = bubbles.value.filter((item) => item.key !== key)
      bubbleTimers.delete(key)
    }, ms)
    bubbleTimers.set(key, timer)
  }
}

function npcSay(npc, text, tone = 'npc', ms = 5200) {
  if (!npc) return
  addBubble({
    tone,
    name: npc.name,
    text,
    anchor: { x: npc.x, y: npc.y },
    anchorId: npc.id,
    ms
  })
}

function playerSay(text) {
  // 孩子的话固定显示在底部的「我说」条里：站在 NPC 旁边时两个气泡会互相压住，
  // 而这句话必须始终看得见（方便家长核对孩子说了什么）。
  lastSaid.value = text
}

function propSay(prop, text) {
  addBubble({
    tone: 'note',
    name: prop.name,
    text,
    anchor: { x: prop.x, y: prop.y },
    anchorId: prop.id,
    lift: 150,
    ms: 4200
  })
}

function clearBubbles() {
  bubbleTimers.forEach((id) => clearTimeout(id))
  bubbleTimers.clear()
  if (reactionTimer) {
    clearTimeout(reactionTimer)
    reactionTimer = null
  }
  bubbles.value = []
}

/** 先让孩子自己的话停留一下，再让角色回应，避免两个气泡叠在一起。 */
function scheduleReaction(fn, delay = 900) {
  if (reactionTimer) clearTimeout(reactionTimer)
  reactionTimer = setTimeout(() => {
    reactionTimer = null
    if (!disposed) fn()
  }, delay)
}

function flash(message) {
  toast.value = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
  }, 2200)
}

async function enterStep(index) {
  if (disposed || !world.value || !training.value) return
  const target = world.value.steps[Math.max(0, Math.min(index, world.value.steps.length - 1))]
  stepIndex.value = target.index
  pendingAdvance.value = null
  clearBubbles()

  if (scene.value?.id !== target.scene) {
    fading.value = true
    await sleep(240)
    if (disposed) return
    const nextScene = world.value.scenes[target.scene]
    engine.loadScene(target.scene)
    if (nextScene?.name) flash(`来到${nextScene.name}`)
    fading.value = false
    await sleep(160)
  }

  engine.focusId.value = target.focus
  const speaker = npcOf(target.speaker)
  lastSaid.value = ''
  coach.value = {
    title: target.voice === 'coach' ? '教练旁白' : speaker?.name || '教练',
    text: training.value.prompt || '',
    tone: 'task'
  }
  if (autoRead.value) speak(training.value.prompt || '')
  if (target.line && speaker) npcSay(speaker, target.line, 'npc', readingMs(target.line, 2600, 8000))
  scheduleSave()
}

async function onSubmit(text, source) {
  if (!training.value || busy.value || phase.value !== 'play') return
  busy.value = true
  error.value = ''
  playerSay(text)
  const before = training.value.step_index
  try {
    const { data } = await gameApi.turn(training.value.id, text, source)
    training.value = data.training

    if (data.blocked) {
      coach.value = {
        title: '安全提醒',
        text: data.notice || data.reply,
        tone: 'safety'
      }
      stopSpeaking()
      return
    }

    if (training.value.status === 'completed') {
      const speaker = npcOf(world.value.steps[before].speaker)
      const feedback = training.value.feedback || '说得真好！'
      scheduleReaction(() => npcSay(speaker, feedback, 'praise', 0), 850)
      if (autoRead.value) speak(feedback)
      flash('这个场景完成啦 🎉')
      scheduleSave()
      // 不自动跳结算：等玩家读完再点「查看小结」
      queueAdvance('查看小结 →', async () => {
        if (disposed) return
        clearBubbles()
        phase.value = 'done'
      })
      return
    }

    if (training.value.step_index > before) {
      const feedback = training.value.feedback || ''
      if (data.accepted) {
        const speaker = npcOf(world.value.steps[before].speaker)
        scheduleReaction(() => npcSay(speaker, feedback || '说得真好！', 'praise', 0), 950)
        flash('说得真好 ✨')
      } else {
        coach.value = {
          title: '我们继续',
          text: training.value.feedback,
          tone: 'demo'
        }
      }
      if (autoRead.value && feedback) speak(feedback)
      scheduleSave()
      // 关键：气泡常驻 + 等玩家点「继续」，不再有任何自动切换
      queueAdvance('继续 →', async () => {
        if (!disposed) await enterStep(training.value.step_index)
      })
      return
    }

    const speaker = npcOf(world.value.steps[before].speaker)
    coach.value = {
      title: training.value.hint_level ? `小提示 ${training.value.hint_level}/2` : '再想想',
      text: training.value.feedback,
      tone: 'hint'
    }
    scheduleReaction(() => npcSay(speaker, '没关系，我们慢慢来～', 'soft', 2800), 900)
    if (autoRead.value) speak(training.value.feedback || '')
  } catch (err) {
    error.value = apiError(err)
  } finally {
    busy.value = false
  }
}

function onEntity(entity) {
  if (busy.value || phase.value !== 'play') return
  const isFocus = entity.data.id === engine.focusId.value

  if (entity.type === 'npc') {
    engine.approach(entity, () => {
      engine.logAction('talk', entity.data.id, training.value.step_index)
      if (isFocus) {
        const target = step.value
        if (target?.line) npcSay(entity.data, target.line, 'npc', 5000)
        else npcSay(entity.data, entity.data.line || '我在听。', 'npc', 4600)
        const prompt = training.value?.prompt
        if (prompt) coach.value = { title: entity.data.name, text: prompt, tone: 'task' }
      } else {
        npcSay(entity.data, entity.data.line || `${entity.data.name}在忙。`, 'npc', 4200)
      }
      scheduleSave()
    })
    return
  }

  engine.approach(entity, () => {
    engine.markVisited(entity.data.id)
    engine.logAction('inspect', entity.data.id, training.value.step_index)
    propSay(entity.data, entity.data.note || `${entity.data.name}，可以看一看。`)
    if (isFocus) engine.faceTowards({ x: entity.data.x, y: entity.data.y })
    scheduleSave()
  })
}

function onFloor(point) {
  if (busy.value || phase.value !== 'play') return
  engine.onFloorClick(point)
}

function onApproach() {
  engine.goToFocus()
}

function toggleAutoRead() {
  autoRead.value = !autoRead.value
  localStorage.setItem('pojian_game_speech', autoRead.value ? '1' : '0')
  if (!autoRead.value) stopSpeaking()
}

async function finishEarly() {
  if (!training.value || busy.value) return
  busy.value = true
  try {
    const { data } = await trainingApi.end(training.value.id)
    training.value = data
    phase.value = 'done'
    stopSpeaking()
  } catch (err) {
    error.value = apiError(err)
  } finally {
    busy.value = false
  }
}

function backToPick() {
  stopSpeaking()
  clearBubbles()
  engine.dispose()
  phase.value = 'pick'
  // 刚进场景就退出去、一步都没走：直接放弃，别在下次又提示「训练还没做完」
  const current = training.value
  if (current?.status === 'active' && current.step_index === 0 && current.correct_count === 0) {
    resumeSession.value = null
    trainingApi.abort(current.id).catch(() => {})
  } else if (current?.status === 'active') {
    resumeSession.value = withScenarioName(current)
  }
  refreshResume()
}

function withScenarioName(session) {
  const meta = catalog.value.find((item) => item.scenario === session.scenario)
  return {
    ...session,
    scenario_name: meta?.name || session.scenario,
    total_steps: meta?.steps || session.total_steps || 0
  }
}

async function refreshResume() {
  try {
    const { data } = await trainingApi.sessions()
    // 只把「真的练过」的会话列为可继续；刚点开还没作答的不算，也不去动别人的会话
    const active = data.find((item) => item.status === 'active' && item.step_index > 0)
    resumeSession.value = active ? withScenarioName(active) : null
  } catch {
    resumeSession.value = null
  }
}

async function discardResume() {
  const target = resumeSession.value
  resumeSession.value = null
  if (!target?.id) return
  try {
    await trainingApi.abort(target.id)
  } catch {
    /* 面板已经收起，失败也不影响继续选关 */
  }
}

function playAgain() {
  const key = training.value?.scenario
  if (key) startScenario(key)
}

function scheduleSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(saveNow, 700)
}

async function saveNow() {
  if (!training.value || !world.value || phase.value === 'loading') return
  try {
    await gameApi.saveState(training.value.id, engine.snapshot())
  } catch {
    /* 存档失败不阻断游戏，下一次操作会再试 */
  }
}

function chooseGesturePhrase() {
  return step.value?.gestures || []
}
</script>

<template>
  <div class="game-page">
    <!-- ============ 选关 ============ -->
    <template v-if="phase === 'loading'">
      <div class="page game-loading">正在准备游戏场景…</div>
    </template>

    <template v-else-if="phase === 'pick'">
      <div class="page game-pick">
        <div class="game-brandbar">
          <div class="game-brand">
            <BrandMark :size="40" />
            <div>
              <div class="brand-title">破茧之声 · 情景小游戏</div>
              <div class="brand-sub">星星的孩子 · 六个训练场景，走进去练</div>
            </div>
          </div>
          <div class="game-brand-actions">
            <button class="btn ghost small" @click="router.push('/training')">
              <AppIcon name="book" :size="14" />
              文字版训练
            </button>
            <button class="btn ghost small" @click="exitToDashboard">
              <AppIcon name="arrowLeft" :size="14" />
              返回工作台
            </button>
          </div>
        </div>

        <div class="pick-head">
          <div>
            <h1 class="page-title">今天想让 {{ store.children.find((item) => item.id === store.childId)?.nickname || '小朋友' }} 练什么？</h1>
            <p class="page-desc">
              同样的六个训练主题，换成可以走进去的 2D 房间：点地面走路、点家具看看、点角色说话。
              判定与提示仍然由原来的训练引擎负责。
            </p>
          </div>
          <span class="badge accent">点击探索 · 靠近对话</span>
        </div>

        <div v-if="error" class="error" style="margin-bottom: 14px">{{ error }}</div>

        <div v-if="resumeSession" class="resume-card">
          <div>
            <b>接着上次练：{{ resumeSession.scenario_name }}</b>
            <p>
              已经完成 {{ resumeSession.step_index }}/{{ resumeSession.total_steps }} 个情境，进度已保存。
            </p>
          </div>
          <div class="resume-actions">
            <button class="btn" :disabled="busy" @click="resumeGame">继续</button>
            <button class="btn ghost" :disabled="busy" @click="discardResume">放弃这次</button>
          </div>
        </div>

        <div class="level-grid">
          <button
            v-for="item in catalog"
            :key="item.scenario"
            class="level-card"
            :disabled="busy"
            @click="startScenario(item.scenario)"
          >
            <div class="level-thumb">
              <GameThumb :art="item.art" :env="item.env" />
              <span class="level-badge">{{ item.steps }} 个情境</span>
            </div>
            <div class="level-body">
              <h3>{{ item.name }}</h3>
              <p>{{ item.goal }}</p>
              <div class="level-meta">
                <span>📍 {{ item.scene_name }}</span>
                <span v-if="item.scenes.length > 1">· {{ item.scenes.length }} 个场景</span>
              </div>
              <span class="level-go">进入游戏 →</span>
            </div>
          </button>
        </div>
      </div>
    </template>

    <!-- ============ 游戏中 ============ -->
    <template v-else-if="phase === 'play' && world">
      <header class="game-topbar">
        <div class="topbar-left">
          <button class="icon-btn ghost" title="返回选关" @click="backToPick">
            <AppIcon name="arrowLeft" :size="18" />
          </button>
          <button class="icon-btn ghost" title="返回工作台" @click="exitToDashboard">
            <AppIcon name="dashboard" :size="17" />
          </button>
          <div>
            <div class="topbar-title">
              {{ world.name }}
              <span class="topbar-scene">{{ scene?.name }}</span>
            </div>
            <div class="topbar-sub">{{ world.goal }}</div>
          </div>
        </div>

        <div class="topbar-mid">
          <span class="step-dot" v-for="i in totalSteps" :key="i" :class="{ done: i <= training.step_index }"></span>
          <span class="step-text">{{ Math.min(training.step_index + 1, totalSteps) }} / {{ totalSteps }}</span>
        </div>

        <div class="topbar-right">
          <span class="chip">✓ 回应 {{ training.correct_count }} 次</span>
          <button class="chip ghost" @click="showLog = true">对话记录</button>
          <button v-if="autoRead" class="chip on" @click="toggleAutoRead">朗读 开</button>
          <button v-else class="chip" @click="toggleAutoRead">朗读 关</button>
          <button class="chip ghost" @click="finishEarly">结束</button>
        </div>
      </header>

      <div class="game-main">
        <div class="stage-wrap" :class="{ fading }">
          <GameStage
            :scene="scene"
            :player="engine.player"
            :focus-id="engine.focusId.value"
            :visited="engine.visited.value"
            :bubbles="bubbles"
            :disabled="busy"
            @floor="onFloor"
            @entity="onEntity"
          />
          <div class="progress-bar"><span :style="{ width: progress + '%' }"></span></div>
        </div>

        <aside class="task-card" :class="{ complete: training.step_index >= totalSteps }">
          <div class="task-kicker">第 {{ Math.min(stepIndex + 1, totalSteps) }} 关 · {{ scene?.name }}</div>
          <p class="task-text">{{ step?.task }}</p>
          <div class="task-tools">
            <button class="mini-btn" :disabled="busy" @click="onApproach">带我过去</button>
            <span class="task-explore">已观察 {{ explored }} 处</span>
          </div>
        </aside>

        <!-- 教练条浮在场景底部：不占排版高度，房间才能铺满屏幕 -->
        <div class="game-coach">
          <div v-if="lastSaid" class="said-line">
            <span class="said-label">我说</span>
            <span class="said-text">{{ lastSaid }}</span>
          </div>
          <div class="coach-strip" :class="coach.tone">
            <div class="coach-avatar">声</div>
            <div class="coach-body">
              <div class="coach-title">
                {{ coach.title }}
                <button v-if="coach.text" class="speak-btn" :title="speaking ? '停止朗读' : '朗读这句'" @click="toggleSpeak(coach.text)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                    <path d="M4 9v6h4l5 4V5L8 9H4Z" stroke-linejoin="round" />
                    <path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke-linecap="round" />
                  </svg>
                </button>
              </div>
              <p class="coach-text">{{ coach.text }}</p>
            </div>
          </div>
        </div>

        <div v-if="pendingAdvance" class="game-next">
          <button class="btn" @click="advance">{{ pendingAdvance.label }}</button>
        </div>

        <div v-if="toast" class="game-toast">{{ toast }}</div>
      </div>

      <footer class="game-bottom">
        <GameComposer
          :disabled="busy"
          :busy="busy"
          :near-focus="engine.nearFocus.value"
          :gestures="chooseGesturePhrase()"
          :focus-name="focusName"
          @submit="onSubmit"
          @approach="onApproach"
        />
        <div v-if="error" class="error" style="margin-top: 8px">{{ error }}</div>
      </footer>
    </template>

    <!-- ============ 完成 ============ -->
    <template v-else-if="phase === 'done'">
      <div class="page done-page">
        <div class="done-card">
          <div class="done-stars">
            <span v-for="i in 3" :key="i" :class="{ lit: i <= stars }">★</span>
          </div>
          <h2>{{ world?.name || '这次练习' }} · 完成啦</h2>
          <p class="done-sub">
            完成了 {{ training?.step_index }}/{{ training?.total_steps }} 个情境，
            {{ training?.correct_count }} 次给出了合适的回应。
          </p>
          <pre class="done-summary">{{ training?.summary }}</pre>
          <div class="done-actions">
            <button class="btn" @click="playAgain">再练一次</button>
            <button class="btn ghost" @click="backToPick">换个场景</button>
          </div>
        </div>
      </div>
    </template>

    <!-- 对话记录 -->
    <div v-if="showLog" class="log-mask" @click.self="showLog = false">
      <div class="log-panel">
        <div class="log-head">
          <h3>这次练习说过的话</h3>
          <button class="icon-btn ghost" @click="showLog = false">✕</button>
        </div>
        <div class="log-body">
          <div v-for="(item, index) in transcript" :key="index" class="log-line" :class="item.role">
            <b>{{ roleLabel[item.role] || '教练' }}</b>
            <span>{{ item.content }}</span>
          </div>
          <div v-if="!transcript.length" class="empty-state">还没有对话记录。</div>
        </div>
      </div>
    </div>
  </div>
</template>
