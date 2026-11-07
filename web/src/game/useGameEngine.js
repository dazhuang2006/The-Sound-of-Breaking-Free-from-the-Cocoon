/**
 * 游戏引擎（角色 / 移动 / 互动 / 场景切换 / 存档快照）。
 *
 * 六个关卡共用这一套引擎：它只认后端下发的 world 配置，
 * 不知道「这是道谢还是购物」，因此扩展新关卡不需要改引擎。
 */
import { computed, reactive, ref } from 'vue'
import { createNav } from './pathfinding'
import { clampToBounds } from './iso'

const SPEED = 3.7
const NEAR = 2.05

export function useGameEngine() {
  const world = ref(null)
  const scene = ref(null)
  const sceneKey = ref(0)
  const player = reactive({ x: 8, y: 9, facing: 'down', walking: false, phase: 0 })
  const visited = ref([])
  const focusId = ref('')
  const walking = ref(false)
  const hovered = ref('')
  const actions = ref([])

  let nav = null
  let route = []
  let pending = null
  let frame = 0
  let lastTs = 0

  const sceneProps = computed(() => scene.value?.props || [])
  const sceneNpcs = computed(() => scene.value?.npcs || [])

  function startLoop() {
    if (frame) return
    lastTs = 0
    frame = requestAnimationFrame(tick)
  }

  function stopLoop() {
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    route = []
    pending = null
    walking.value = false
    player.walking = false
  }

  function tick(ts) {
    const dt = lastTs ? Math.min(0.06, (ts - lastTs) / 1000) : 0
    lastTs = ts
    if (route.length && dt > 0) {
      const next = route[0]
      const dx = next.x - player.x
      const dy = next.y - player.y
      const dist = Math.hypot(dx, dy)
      const step = SPEED * dt
      if (dist <= step || dist < 0.001) {
        player.x = next.x
        player.y = next.y
        route.shift()
      } else {
        player.x += (dx / dist) * step
        player.y += (dy / dist) * step
      }
      if (Math.abs(dx) > Math.abs(dy)) {
        player.facing = dx > 0 ? 'right' : 'left'
      } else if (Math.abs(dy) > 0.01) {
        player.facing = dy > 0 ? 'down' : 'up'
      }
      player.walking = route.length > 0
      player.phase += dt * 10
      if (!route.length) {
        player.walking = false
        walking.value = false
        const callback = pending
        pending = null
        callback?.()
      }
    } else if (player.walking) {
      player.walking = false
      walking.value = false
    }
    frame = requestAnimationFrame(tick)
  }

  function loadScene(sceneId, spawn) {
    if (!world.value) return
    const target = world.value.scenes[sceneId] || world.value.scenes[world.value.start_scene]
    if (!target) return
    scene.value = target
    nav = createNav(target)
    sceneKey.value += 1
    route = []
    pending = null
    walking.value = false
    player.walking = false
    hovered.value = ''
    const point = spawn || target.spawn
    player.x = point.x
    player.y = point.y
    player.facing = 'down'
  }

  function init(worldData, state) {
    world.value = worldData
    visited.value = Array.isArray(state?.visited) ? [...state.visited] : []
    actions.value = Array.isArray(state?.actions) ? [...state.actions].slice(-60) : []
    const startScene = state?.scene && worldData.scenes[state.scene] ? state.scene : worldData.start_scene
    loadScene(startScene, state?.player || null)
    startLoop()
  }

  function dispose() {
    stopLoop()
    world.value = null
    scene.value = null
  }

  function entityById(id) {
    if (!id || !scene.value) return null
    const npc = scene.value.npcs.find((item) => item.id === id)
    if (npc) return { type: 'npc', ...npc }
    const prop = scene.value.props.find((item) => item.id === id)
    if (prop) return { type: 'prop', ...prop }
    return null
  }

  function standOf(entity) {
    if (!entity) return null
    if (entity.type === 'npc') return entity.stand || { x: entity.x, y: entity.y + 1.25 }
    if (entity.stand) return { x: entity.stand.x, y: entity.stand.y }
    return { x: entity.x, y: entity.y + entity.h / 2 + 0.7 }
  }

  function faceTowards(target) {
    const dx = target.x - player.x
    const dy = target.y - player.y
    if (Math.abs(dx) > Math.abs(dy)) player.facing = dx > 0 ? 'right' : 'left'
    else player.facing = dy >= 0 ? 'down' : 'up'
  }

  function walkTo(point, done) {
    if (!nav || !point) {
      done?.()
      return false
    }
    const goal = clampToBounds(point.x, point.y, scene.value?.bounds)
    const free = nav.nearestFree(goal.x, goal.y)
    if (!free) {
      done?.()
      return false
    }
    const path = nav.findPath({ x: player.x, y: player.y }, free)
    if (!path.length) {
      done?.()
      return false
    }
    route = path.slice(1)
    if (!route.length) {
      faceTowards(free)
      done?.()
      return true
    }
    pending = done
    walking.value = true
    player.walking = true
    return true
  }

  function approach(entity, done) {
    const stand = standOf(entity)
    if (!stand) {
      done?.()
      return
    }
    faceTowards(stand)
    walkTo(stand, () => {
      // 站定后转向互动对象本人，而不是站在锚点上背对对方
      faceTowards({ x: entity.x, y: entity.y })
      done?.()
    })
  }

  function onFloorClick(worldPoint) {
    if (!scene.value) return
    const { minX, maxX, minY, maxY } = scene.value.bounds
    if (
      worldPoint.x < minX - 0.4 ||
      worldPoint.x > maxX + 0.4 ||
      worldPoint.y < minY - 0.4 ||
      worldPoint.y > maxY + 0.4
    ) {
      return
    }
    walkTo(worldPoint)
  }

  function distanceTo(point) {
    if (!point) return Infinity
    return Math.hypot(point.x - player.x, point.y - player.y)
  }

  const focusEntity = computed(() => entityById(focusId.value))

  const nearFocus = computed(() => {
    const entity = focusEntity.value
    if (!entity) return false
    const stand = standOf(entity)
    return stand ? distanceTo(stand) <= NEAR : false
  })

  const focusPoint = computed(() => standOf(focusEntity.value))

  function markVisited(id) {
    if (!id) return
    if (!visited.value.includes(id)) visited.value = [...visited.value, id]
  }

  function logAction(kind, target, step) {
    actions.value = [
      ...actions.value.slice(-59),
      { kind, target, step, at: String(Date.now()) }
    ]
  }

  function snapshot() {
    return {
      scene: scene.value?.id,
      player: { x: Number(player.x.toFixed(2)), y: Number(player.y.toFixed(2)) },
      visited: [...visited.value],
      actions: [...actions.value].slice(-80)
    }
  }

  function goToFocus(done) {
    const entity = focusEntity.value
    if (!entity) return
    approach(entity, done)
  }

  return {
    world,
    scene,
    sceneKey,
    player,
    visited,
    focusId,
    walking,
    hovered,
    sceneProps,
    sceneNpcs,
    focusEntity,
    focusPoint,
    nearFocus,
    init,
    dispose,
    loadScene,
    entityById,
    standOf,
    walkTo,
    approach,
    goToFocus,
    onFloorClick,
    markVisited,
    logAction,
    snapshot,
    distanceTo,
    faceTowards,
    startLoop,
    stopLoop
  }
}
