<script setup>
/**
 * 低饱和暖色趋势图：折线（情绪 1–5）或柱状（完成度 0–100）。
 * 只用 SVG，不引图表库，避免为一个折线图增加依赖。
 */
import { computed } from 'vue'

const props = defineProps({
  points: { type: Array, default: () => [] }, // [{ label, value }]
  type: { type: String, default: 'line' }, // line | bar
  max: { type: Number, default: 100 },
  min: { type: Number, default: 0 },
  color: { type: String, default: '#ddaa8c' },
  fill: { type: String, default: 'rgba(221, 170, 140, 0.18)' },
  unit: { type: String, default: '' }
})

const W = 640
const H = 190
const PAD = { l: 34, r: 16, t: 16, b: 28 }

const plotW = W - PAD.l - PAD.r
const plotH = H - PAD.t - PAD.b

const safePoints = computed(() =>
  props.points.map((item) => ({
    label: item.label,
    value: Number(item.value)
  }))
)

const hasData = computed(() => safePoints.value.some((item) => Number.isFinite(item.value)))

function xAt(index) {
  const count = Math.max(safePoints.value.length, 1)
  if (count === 1) return PAD.l + plotW / 2
  return PAD.l + (index / (count - 1)) * plotW
}

function yAt(value) {
  const span = props.max - props.min || 1
  const ratio = Math.min(1, Math.max(0, (value - props.min) / span))
  return PAD.t + plotH - ratio * plotH
}

const linePath = computed(() => {
  const valid = safePoints.value
    .map((item, index) => ({ ...item, index }))
    .filter((item) => Number.isFinite(item.value))
  if (!valid.length) return ''
  return valid.map((item, i) => `${i === 0 ? 'M' : 'L'}${xAt(item.index).toFixed(1)} ${yAt(item.value).toFixed(1)}`).join(' ')
})

const areaPath = computed(() => {
  const valid = safePoints.value
    .map((item, index) => ({ ...item, index }))
    .filter((item) => Number.isFinite(item.value))
  if (valid.length < 2) return ''
  const first = valid[0]
  const last = valid[valid.length - 1]
  return `${linePath.value} L${xAt(last.index).toFixed(1)} ${PAD.t + plotH} L${xAt(first.index).toFixed(1)} ${
    PAD.t + plotH
  } Z`
})

const dots = computed(() =>
  safePoints.value
    .map((item, index) => ({ ...item, index }))
    .filter((item) => Number.isFinite(item.value))
)

const bars = computed(() => {
  const count = Math.max(safePoints.value.length, 1)
  const slot = plotW / count
  const width = Math.min(34, slot * 0.55)
  return safePoints.value.map((item, index) => {
    const value = Number.isFinite(item.value) ? item.value : 0
    const y = yAt(value)
    return {
      x: PAD.l + slot * index + (slot - width) / 2,
      y,
      width,
      height: Math.max(2, PAD.t + plotH - y),
      label: item.label,
      value
    }
  })
})

const gridLines = computed(() => {
  const span = props.max - props.min || 1
  return [0, 0.5, 1].map((ratio) => ({
    y: PAD.t + plotH - ratio * plotH,
    label: Math.round(props.min + span * ratio)
  }))
})

const labelEvery = computed(() => (safePoints.value.length > 8 ? 3 : 1))
</script>

<template>
  <div class="chart-wrap">
    <svg v-if="hasData" class="chart-svg" :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="趋势图">
      <g>
        <line
          v-for="line in gridLines"
          :key="line.y"
          :x1="PAD.l"
          :x2="W - PAD.r"
          :y1="line.y"
          :y2="line.y"
          stroke="#efe1d4"
          stroke-width="1"
          stroke-dasharray="4 6"
        />
        <text
          v-for="line in gridLines"
          :key="`t-${line.y}`"
          :x="PAD.l - 8"
          :y="line.y + 4"
          text-anchor="end"
          font-size="10"
          fill="#a08c7c"
        >
          {{ line.label }}
        </text>
      </g>

      <template v-if="type === 'bar'">
        <rect
          v-for="bar in bars"
          :key="bar.x"
          :x="bar.x"
          :y="bar.y"
          :width="bar.width"
          :height="bar.height"
          rx="6"
          :fill="bar.value > 0 ? color : '#f3e8dd'"
          opacity="0.9"
        />
      </template>

      <template v-else>
        <path v-if="areaPath" :d="areaPath" :fill="fill" stroke="none" />
        <path
          v-if="linePath"
          :d="linePath"
          fill="none"
          :stroke="color"
          stroke-width="2.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle
          v-for="dot in dots"
          :key="dot.index"
          :cx="xAt(dot.index)"
          :cy="yAt(dot.value)"
          r="4"
          :fill="'#fffdfa'"
          :stroke="color"
          stroke-width="2.4"
        />
        <text
          v-for="dot in dots"
          :key="`v-${dot.index}`"
          :x="xAt(dot.index)"
          :y="yAt(dot.value) - 10"
          text-anchor="middle"
          font-size="10"
          fill="#8c786a"
        >
          {{ dot.value }}{{ unit }}
        </text>
      </template>

      <g>
        <text
          v-for="(item, index) in safePoints"
          v-show="index % labelEvery === 0"
          :key="`x-${index}`"
          :x="xAt(index)"
          :y="H - 8"
          text-anchor="middle"
          font-size="10"
          fill="#a08c7c"
        >
          {{ item.label }}
        </text>
      </g>
    </svg>
    <div v-else class="empty-state" style="padding: 26px 10px">还没有足够的数据，记录几天后这里会出现趋势。</div>
  </div>
</template>
