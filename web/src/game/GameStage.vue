<script setup>
/**
 * 舞台：地板 → 后墙 → 按深度排序的实体（家具 / 角色 / 小朋友）→ 焦点光环 → 对话气泡。
 *
 * 点击地面 = 走过去；点击家具 = 走到旁边观察；点击角色 = 走到面前说话。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import RoomShell from './art/RoomShell.vue'
import PropSprite from './art/PropSprite.vue'
import CharacterSprite from './art/CharacterSprite.vue'
import { VIEW, VIEW_BOX, depthKey, isoX, isoY, fromIso } from './iso'

const props = defineProps({
  scene: { type: Object, default: null },
  player: { type: Object, default: null },
  focusId: { type: String, default: '' },
  visited: { type: Array, default: () => [] },
  bubbles: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['floor', 'entity', 'hover'])

const svgEl = ref(null)
const stageEl = ref(null)
const box = ref({ w: 0, h: 0 })

let observer = null

onMounted(() => {
  if (!stageEl.value || typeof ResizeObserver === 'undefined') return
  observer = new ResizeObserver((entries) => {
    const rect = entries[0]?.contentRect
    if (rect) box.value = { w: rect.width, h: rect.height }
  })
  observer.observe(stageEl.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})

const PROP_HEIGHT = {
  rug: 52,
  bookshelf: 160,
  sofa: 116,
  lamp: 150,
  plant: 128,
  coffee_table: 80,
  dining_table: 96,
  toy_box: 84,
  puzzle: 46,
  biscuit: 42,
  crayons: 30,
  plate: 34,
  blocks: 58,
  desk: 104,
  teacher_desk: 104,
  puzzle_box: 48,
  water_bottle: 62,
  slide: 190,
  swing: 188,
  sandbox: 62,
  bench: 92,
  tree: 182,
  ball: 46,
  shelf: 146,
  fridge: 182,
  counter: 140,
  milk: 58,
  basket: 48
}

function propWidth(prop) {
  return Math.max(58, (prop.w + prop.h) * 28)
}

function hitOf(entity) {
  if (entity.type === 'npc' || entity.type === 'player') {
    return { x: -38, y: -156, w: 76, h: 168 }
  }
  const prop = entity.data
  const width = propWidth(prop)
  const height = PROP_HEIGHT[prop.art] || 104
  return { x: -width / 2, y: -height - 6, w: width, h: height + 12 }
}

function transformOf(entity) {
  if (entity.type === 'player') {
    return `translate(${isoX(props.player.x, props.player.y)} ${isoY(props.player.x, props.player.y)})`
  }
  if (entity.type === 'npc') {
    return `translate(${isoX(entity.data.x, entity.data.y)} ${isoY(
      entity.data.x,
      entity.data.y
    )})`
  }
  const prop = entity.data
  return `translate(${isoX(prop.x, prop.y)} ${isoY(prop.x, prop.y) - (prop.lift || 0)})`
}

const entities = computed(() => {
  if (!props.scene || !props.player) return []
  const list = []
  for (const prop of props.scene.props) {
    const feet = depthKey(prop.x, prop.y + prop.h / 2)
    const depth = prop.art === 'rug' ? -500 : feet + (prop.z || 0)
    list.push({ key: `prop:${prop.id}`, type: 'prop', data: prop, depth })
  }
  for (const npc of props.scene.npcs) {
    list.push({ key: `npc:${npc.id}`, type: 'npc', data: npc, depth: depthKey(npc.x, npc.y) })
  }
  list.push({
    key: 'player',
    type: 'player',
    data: props.player,
    depth: depthKey(props.player.x, props.player.y) + 0.01
  })
  return list.sort((a, b) => a.depth - b.depth)
})

function isFocus(entity) {
  return Boolean(props.focusId) && entity.data?.id === props.focusId
}

function isVisited(entity) {
  return entity.type === 'prop' && props.visited.includes(entity.data.id)
}

/** 角色头顶已经有气泡时，暂时收起名字牌，避免两块文字叠在一起。 */
const talkingIds = computed(
  () => new Set(props.bubbles.map((bubble) => bubble.anchorId).filter(Boolean))
)

function hideTag(entity) {
  return entity.type === 'npc' && talkingIds.value.has(entity.data.id)
}

function onFloorClick(event) {
  if (props.disabled || !svgEl.value) return
  const svg = svgEl.value
  const matrix = svg.getScreenCTM()
  if (!matrix) return
  const point = svg.createSVGPoint()
  point.x = event.clientX
  point.y = event.clientY
  const local = point.matrixTransform(matrix.inverse())
  emit('floor', fromIso(local.x, local.y))
}

function pick(entity) {
  if (props.disabled) return
  emit('entity', entity)
}

function hover(entity) {
  emit('hover', entity ? entity.data.id : '')
}

/** SVG 等比缩放后会留黑边，气泡要按「实际内容区」换算，而不是容器百分比。 */
const scale = computed(() => {
  if (!box.value.w || !box.value.h) return 0
  return Math.min(box.value.w / VIEW.w, box.value.h / VIEW.h)
})

function bubbleStyle(bubble) {
  const s = scale.value || 1
  const offsetX = (box.value.w - VIEW.w * s) / 2
  const offsetY = (box.value.h - VIEW.h * s) / 2
  const lift = bubble.lift ?? 168
  const x = bubble.anchor?.x ?? 8
  const y = bubble.anchor?.y ?? 8
  const left = offsetX + (isoX(x, y) - VIEW.x) * s
  const top = offsetY + (isoY(x, y) - lift - VIEW.y) * s
  return { left: `${left}px`, top: `${top}px` }
}

function labelWidth(text) {
  return Math.max(44, String(text || '').length * 15 + 20)
}
</script>

<template>
  <div ref="stageEl" class="game-stage">
    <svg
      ref="svgEl"
      class="stage-svg"
      :viewBox="VIEW_BOX"
      preserveAspectRatio="xMidYMid meet"
      @click="onFloorClick"
    >
      <RoomShell v-if="scene" :art="scene.art" :env="scene.env" />

      <g
        v-for="entity in entities"
        :key="entity.key"
        class="entity"
        :class="[entity.type, { focused: isFocus(entity), dimmed: disabled }]"
        :transform="transformOf(entity)"
        @click.stop="entity.type !== 'player' && pick(entity)"
        @mouseenter="hover(entity)"
        @mouseleave="hover(null)"
      >
        <!-- 焦点光环 -->
        <g v-if="isFocus(entity)" class="focus-ring">
          <ellipse cx="0" cy="0" rx="40" ry="15" fill="none" stroke="#F3B94E" stroke-width="5" stroke-dasharray="11 9" />
          <ellipse cx="0" cy="0" rx="40" ry="15" fill="#FBE7AE" opacity="0.25" />
        </g>

        <!-- 点击热区 -->
        <rect
          class="hit"
          :x="hitOf(entity).x"
          :y="hitOf(entity).y"
          :width="hitOf(entity).w"
          :height="hitOf(entity).h"
          fill="transparent"
        />

        <PropSprite v-if="entity.type === 'prop'" :art="entity.data.art" />
        <CharacterSprite
          v-else
          :role="entity.data.role"
          :facing="entity.data.facing || 'down'"
          :walking="entity.type === 'player' ? player.walking : false"
          :phase="entity.type === 'player' ? player.phase : 0"
          :mood="entity.data.mood || 'idle'"
        />

        <!-- 名字牌 -->
        <g v-if="entity.type === 'npc' && !hideTag(entity)" class="name-tag" :transform="`translate(0 ${-156})`">
          <rect
            :x="-labelWidth(entity.data.name) / 2"
            y="-16"
            :width="labelWidth(entity.data.name)"
            height="28"
            rx="14"
            fill="#FFFFFF"
            stroke="#4A3F4A"
            stroke-width="2.6"
            opacity="0.94"
          />
          <text x="0" y="4" text-anchor="middle" font-size="15" fill="#4A3F4A">
            {{ entity.data.name }}
          </text>
        </g>

        <!-- 已观察标记 -->
        <g v-if="isVisited(entity)" :transform="`translate(${propWidth(entity.data) / 2 - 8} ${-(
          PROP_HEIGHT[entity.data.art] || 100
        ) - 8})`">
          <circle cx="0" cy="0" r="13" fill="#9DD8C4" stroke="#4A3F4A" stroke-width="2.6" />
          <path d="M-5 0l4 5 7-9" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        </g>

        <!-- 焦点箭头 -->
        <g v-if="isFocus(entity)" class="focus-arrow">
          <g :transform="`translate(0 ${-(hitOf(entity).h + 24)})`">
            <path d="M0 0l-13-18h26z" fill="#F3B94E" stroke="#4A3F4A" stroke-width="3" stroke-linejoin="round" />
          </g>
        </g>
      </g>
    </svg>

    <!-- 对话气泡层（HTML，中文排版更好看） -->
    <div class="stage-bubbles">
      <div
        v-for="bubble in bubbles"
        :key="bubble.key"
        class="game-bubble"
        :class="bubble.tone"
        :style="bubbleStyle(bubble)"
      >
        <div v-if="bubble.name" class="bubble-name">{{ bubble.name }}</div>
        <div class="bubble-text">{{ bubble.text }}</div>
      </div>
    </div>
  </div>
</template>
