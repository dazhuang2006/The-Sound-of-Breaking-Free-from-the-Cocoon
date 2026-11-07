<script setup>
/**
 * 房间外壳：立体岛式地板 + 室内后墙（窗/黑板/招牌/门）或户外天空与栅栏。
 *
 * 后墙用「墙面局部坐标」画：局部 x 沿墙向右、局部 y 向上为负，
 * 再乘一个斜切矩阵贴到等距平面上，窗框、黑板、门口就会自然「贴在墙上」。
 */
import { computed } from 'vue'
import {
  GRID_H,
  GRID_W,
  VIEW,
  WALL_LEFT_MATRIX,
  WALL_RIGHT_MATRIX,
  isoX,
  isoY
} from '../iso'

const props = defineProps({
  art: { type: String, default: 'home' },
  env: { type: String, default: 'indoor' }
})

const WALL_HEIGHT = 212
const WALL_UNIT = 32.4
const RIGHT_WALL_LEN = GRID_W * WALL_UNIT
const LEFT_WALL_LEN = GRID_H * WALL_UNIT

const PALETTES = {
  home: {
    bg: '#FFF3EC',
    floor: ['#F7DEC3', '#F1D3B4'],
    wallL: '#F7D6CE',
    wallR: '#FDE8E2',
    trim: '#FFF9F4',
    edge: '#D9AE86',
    ink: '#4A3F4A'
  },
  classroom: {
    bg: '#F2FBF7',
    floor: ['#FAEBDA', '#F4E0CB'],
    wallL: '#D6EEE6',
    wallR: '#E9F8F3',
    trim: '#FFFFFF',
    edge: '#D6BC9C',
    ink: '#4A3F4A'
  },
  store: {
    bg: '#FFFAEE',
    floor: ['#F0F4F7', '#E4EAEF'],
    wallL: '#FBEAC6',
    wallR: '#FDF6E4',
    trim: '#FFFFFF',
    edge: '#C3CBD2',
    ink: '#4A3F4A'
  },
  playground: {
    bg: '#E8F7FF',
    floor: ['#D6EEC4', '#C7E6B1'],
    wallL: '#D9F0C9',
    wallR: '#E4F5D6',
    trim: '#FFFFFF',
    edge: '#A9CE90',
    ink: '#4A3F4A'
  }
}

const palette = computed(() => PALETTES[props.art] || PALETTES.home)

const floorPoints = computed(() =>
  [
    [0, 0],
    [GRID_W, 0],
    [GRID_W, GRID_H],
    [0, GRID_H]
  ]
    .map(([x, y]) => `${isoX(x, y)},${isoY(x, y)}`)
    .join(' ')
)

const tiles = computed(() => {
  const out = []
  for (let i = 0; i < GRID_W; i += 1) {
    for (let j = 0; j < GRID_H; j += 1) {
      out.push({
        key: `${i}-${j}`,
        points: [
          [i, j],
          [i + 1, j],
          [i + 1, j + 1],
          [i, j + 1]
        ]
          .map(([x, y]) => `${isoX(x, y)},${isoY(x, y)}`)
          .join(' '),
        fill: palette.value.floor[(i + j) % 2]
      })
    }
  }
  return out
})

/** 两面后墙的屏幕坐标四边形。 */
const leftWallScreen = computed(() => {
  const x1 = isoX(0, GRID_H)
  const y1 = isoY(0, GRID_H)
  return `0,0 ${x1},${y1} ${x1},${y1 - WALL_HEIGHT} 0,${-WALL_HEIGHT}`
})

const rightWallScreen = computed(() => {
  const x1 = isoX(GRID_W, 0)
  const y1 = isoY(GRID_W, 0)
  return `0,0 ${x1},${y1} ${x1},${y1 - WALL_HEIGHT} 0,${-WALL_HEIGHT}`
})

const fences = computed(() => ({
  right: Array.from({ length: 17 }, (_, i) => i * 30),
  left: Array.from({ length: 12 }, (_, i) => i * 30)
}))

const bunting = Array.from({ length: 9 }, (_, i) => i)
const BUNTING_COLORS = ['#F7C6D0', '#BFE3F5', '#FBE7AE', '#CDEBD4']
</script>

<template>
  <g class="room-shell">
    <defs>
      <linearGradient id="sky-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#CFEBFF" />
        <stop offset="60%" stop-color="#EAF8FF" />
        <stop offset="100%" stop-color="#FFF8EC" />
      </linearGradient>
      <linearGradient id="wall-shade" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="rgba(74,63,74,0)" />
        <stop offset="100%" stop-color="rgba(74,63,74,0.10)" />
      </linearGradient>
    </defs>

    <rect
      :x="VIEW.x"
      :y="VIEW.y"
      :width="VIEW.w"
      :height="VIEW.h"
      :fill="env === 'outdoor' ? 'url(#sky-grad)' : palette.bg"
    />

    <!-- 户外：太阳 / 云 / 远山 -->
    <template v-if="env === 'outdoor'">
      <g>
        <circle cx="-250" cy="-166" r="44" fill="#FBE39A" />
        <circle cx="-250" cy="-166" r="30" fill="#FFF0C4" />
        <g stroke="#F6D06E" stroke-width="7" stroke-linecap="round">
          <path d="M-250-228v-14M-250-104v-14M-312-166h-14M-188-166h-14" />
          <path d="M-294-210l-11-11M-206-122l-11-11M-294-122l-11 11M-206-210l-11 11" />
        </g>
      </g>
      <g fill="#FFFFFF" opacity="0.92">
        <g>
          <circle cx="120" cy="-206" r="26" />
          <circle cx="152" cy="-194" r="20" />
          <circle cx="90" cy="-192" r="18" />
          <rect x="90" y="-198" width="62" height="20" rx="10" />
        </g>
        <g opacity="0.8">
          <circle cx="304" cy="-126" r="20" />
          <circle cx="330" cy="-116" r="15" />
          <circle cx="284" cy="-114" r="13" />
          <rect x="284" y="-122" width="46" height="16" rx="8" />
        </g>
      </g>
      <path d="M-382 150q120-72 240-46t220-26q110-14 242 40v104H-382Z" fill="#B9E3A2" opacity="0.55" />
      <path d="M-382 194q150-46 260-24t200-16q110-10 222 32v112H-382Z" fill="#A5D98E" opacity="0.45" />
    </template>

    <!-- 地板厚度：立体岛 -->
    <polygon :points="floorPoints" :fill="palette.edge" transform="translate(0,18)" />
    <polygon :points="floorPoints" :fill="palette.edge" transform="translate(0,9)" opacity="0.6" />

    <!-- 地板格 -->
    <g>
      <polygon
        v-for="tile in tiles"
        :key="tile.key"
        :points="tile.points"
        :fill="tile.fill"
        stroke="rgba(74,63,74,0.05)"
        stroke-width="1"
      />
    </g>

    <!-- 室内后墙 -->
    <template v-if="env === 'indoor'">
      <polygon
        :points="leftWallScreen"
        :fill="palette.wallL"
        :stroke="palette.ink"
        stroke-width="5"
        stroke-linejoin="round"
      />
      <polygon
        :points="rightWallScreen"
        :fill="palette.wallR"
        :stroke="palette.ink"
        stroke-width="5"
        stroke-linejoin="round"
      />
      <polygon :points="leftWallScreen" fill="url(#wall-shade)" />
      <polygon :points="rightWallScreen" fill="url(#wall-shade)" opacity="0.55" />

      <!-- 踢脚线 -->
      <g :transform="WALL_LEFT_MATRIX">
        <rect
          x="0"
          y="-18"
          :width="LEFT_WALL_LEN"
          height="18"
          :fill="palette.trim"
          :stroke="palette.ink"
          stroke-width="4"
        />
      </g>
      <g :transform="WALL_RIGHT_MATRIX">
        <rect
          x="0"
          y="-18"
          :width="RIGHT_WALL_LEN"
          height="18"
          :fill="palette.trim"
          :stroke="palette.ink"
          stroke-width="4"
        />
      </g>

      <!-- ============ 家庭客厅 ============ -->
      <g v-if="art === 'home'">
        <g :transform="WALL_LEFT_MATRIX">
          <rect x="42" y="-166" width="112" height="166" rx="10" fill="#F5E4D3" :stroke="palette.ink" stroke-width="5" />
          <rect x="56" y="-150" width="84" height="130" rx="7" fill="#EAD3BC" :stroke="palette.ink" stroke-width="3" />
          <circle cx="128" cy="-86" r="7" fill="#F6D27C" :stroke="palette.ink" stroke-width="3" />
          <rect x="206" y="-158" width="102" height="84" rx="8" fill="#FFF6EC" :stroke="palette.ink" stroke-width="5" />
          <rect x="218" y="-146" width="78" height="60" rx="4" fill="#FBE3EC" />
          <circle cx="244" cy="-128" r="12" fill="#F7C26B" />
          <path d="M222-96l20-24 16 18 14-14 20 20" fill="none" stroke="#9BCFAE" stroke-width="5" stroke-linecap="round" />
        </g>
        <g :transform="WALL_RIGHT_MATRIX">
          <rect x="78" y="-172" width="150" height="118" rx="10" fill="#DFF2FB" :stroke="palette.ink" stroke-width="5" />
          <path d="M153-172v118M78-113h150" stroke="#FFFFFF" stroke-width="6" />
          <circle cx="112" cy="-146" r="14" fill="#FFF3C4" />
          <path d="M88-72q26-20 52 0t52-8" fill="none" stroke="#C9E7C4" stroke-width="9" stroke-linecap="round" />
          <path d="M70-176q26 12 22 60t-16 52h-22z" fill="#F7BCC9" :stroke="palette.ink" stroke-width="4" stroke-linejoin="round" />
          <path d="M236-176q-26 12-22 60t16 52h22z" fill="#F7BCC9" :stroke="palette.ink" stroke-width="4" stroke-linejoin="round" />
          <circle cx="360" cy="-146" r="28" fill="#FFF9F1" :stroke="palette.ink" stroke-width="5" />
          <path d="M360-166v22l14 10" fill="none" stroke="#4A3F4A" stroke-width="4" stroke-linecap="round" />
        </g>
      </g>

      <!-- ============ 教室 ============ -->
      <g v-else-if="art === 'classroom'">
        <g :transform="WALL_RIGHT_MATRIX">
          <rect x="78" y="-176" width="252" height="112" rx="8" fill="#5F8B7A" :stroke="palette.ink" stroke-width="5" />
          <rect x="90" y="-164" width="228" height="88" rx="4" fill="#4E7A69" />
          <text x="104" y="-132" font-size="24" fill="#EAF7EF" opacity="0.92" letter-spacing="2">今天练：好好说话</text>
          <path d="M104-110h84M200-110h60M104-92h140" stroke="#EAF7EF" stroke-width="3" opacity="0.45" stroke-linecap="round" />
          <rect x="96" y="-58" width="220" height="10" rx="5" fill="#D9B78F" :stroke="palette.ink" stroke-width="3" />
          <rect x="118" y="-54" width="26" height="7" rx="3" fill="#FFF7EA" />
          <circle cx="420" cy="-150" r="26" fill="#FFFDF6" :stroke="palette.ink" stroke-width="5" />
          <path d="M420-168v18l12 9" fill="none" stroke="#4A3F4A" stroke-width="4" stroke-linecap="round" />
          <path d="M20-198q120 26 240 12t240 6" fill="none" stroke="#B9D8CC" stroke-width="3" />
          <path d="M60-192l14 4-10 16z" fill="#F7C6D0" />
          <path d="M120-184l14 3-10 16z" fill="#BFE3F5" />
          <path d="M184-178l14 2-10 16z" fill="#FBE7AE" />
          <path d="M250-174l14 1-10 16z" fill="#CDEBD4" />
        </g>
        <g :transform="WALL_LEFT_MATRIX">
          <rect x="34" y="-170" width="108" height="170" rx="10" fill="#F6E7D7" :stroke="palette.ink" stroke-width="5" />
          <rect x="48" y="-156" width="80" height="128" rx="7" fill="#EAD9C5" :stroke="palette.ink" stroke-width="3" />
          <circle cx="118" cy="-90" r="7" fill="#F6D27C" :stroke="palette.ink" stroke-width="3" />
          <rect x="156" y="-132" width="128" height="46" rx="10" fill="#FFF4CB" :stroke="palette.ink" stroke-width="4" />
          <text x="170" y="-101" font-size="20" fill="#6B5A35">洗手间 →</text>
          <rect x="170" y="-64" width="132" height="58" rx="6" fill="#FFFDF8" :stroke="palette.ink" stroke-width="4" />
          <rect x="182" y="-54" width="34" height="38" rx="3" fill="#F9D7A8" />
          <rect x="224" y="-54" width="30" height="38" rx="3" fill="#CDE9D8" />
          <rect x="262" y="-54" width="30" height="38" rx="3" fill="#D8E9F8" />
        </g>
      </g>

      <!-- ============ 便利店 ============ -->
      <g v-else-if="art === 'store'">
        <g :transform="WALL_RIGHT_MATRIX">
          <rect x="96" y="-186" width="322" height="76" rx="12" fill="#FFF7E3" :stroke="palette.ink" stroke-width="5" />
          <text x="122" y="-133" font-size="43" fill="#E2879F" font-weight="700" letter-spacing="4">便利店</text>
          <circle cx="386" cy="-148" r="12" fill="#9DD8C4" :stroke="palette.ink" stroke-width="3" />
          <path d="M40-202h420l-24 26H64z" fill="#F7C6D0" :stroke="palette.ink" stroke-width="4" stroke-linejoin="round" />
          <path d="M84-202h46l-6 26H78z" fill="#FFF9F2" />
          <path d="M176-202h46l-6 26h-46z" fill="#FFF9F2" />
          <path d="M268-202h46l-6 26h-46z" fill="#FFF9F2" />
          <path d="M360-202h46l-6 26h-46z" fill="#FFF9F2" />
          <rect x="64" y="-96" width="120" height="86" rx="8" fill="#E5F4FB" :stroke="palette.ink" stroke-width="5" />
          <path d="M124-96v86M64-53h120" stroke="#FFFFFF" stroke-width="5" />
        </g>
        <g :transform="WALL_LEFT_MATRIX">
          <rect x="52" y="-172" width="112" height="172" rx="10" fill="#F7EBD8" :stroke="palette.ink" stroke-width="5" />
          <rect x="66" y="-158" width="84" height="132" rx="7" fill="#DFF0F6" :stroke="palette.ink" stroke-width="3" />
          <circle cx="138" cy="-92" r="7" fill="#F6D27C" :stroke="palette.ink" stroke-width="3" />
          <rect x="180" y="-150" width="128" height="44" rx="9" fill="#DFF4E7" :stroke="palette.ink" stroke-width="4" />
          <text x="196" y="-120" font-size="20" fill="#4E8A6B">营业中</text>
        </g>
      </g>
    </template>

    <!-- 户外：栅栏 + 彩旗 -->
    <template v-else>
      <g :transform="WALL_LEFT_MATRIX">
        <rect x="0" y="-44" width="356" height="9" fill="#FFE7D2" stroke="#4A3F4A" stroke-width="3" />
        <rect x="0" y="-20" width="356" height="8" fill="#FFE7D2" stroke="#4A3F4A" stroke-width="3" />
        <g v-for="x in fences.left" :key="'lf' + x">
          <rect :x="x" y="-52" width="16" height="52" rx="4" fill="#FFF6EC" stroke="#4A3F4A" stroke-width="3.4" />
          <path :d="`M${x}-52l8-12 8 12`" fill="#FFF6EC" stroke="#4A3F4A" stroke-width="3.4" stroke-linejoin="round" />
        </g>
      </g>
      <g :transform="WALL_RIGHT_MATRIX">
        <rect x="0" y="-44" width="518" height="9" fill="#FFE7D2" stroke="#4A3F4A" stroke-width="3" />
        <rect x="0" y="-20" width="518" height="8" fill="#FFE7D2" stroke="#4A3F4A" stroke-width="3" />
        <g v-for="x in fences.right" :key="'rf' + x">
          <rect :x="x" y="-52" width="16" height="52" rx="4" fill="#FFF6EC" stroke="#4A3F4A" stroke-width="3.4" />
          <path :d="`M${x}-52l8-12 8 12`" fill="#FFF6EC" stroke="#4A3F4A" stroke-width="3.4" stroke-linejoin="round" />
        </g>
      </g>
      <g :transform="WALL_RIGHT_MATRIX">
        <path d="M30-100q120 26 230 8t230 6" fill="none" stroke="#C9B9AA" stroke-width="2.6" />
        <g v-for="i in bunting" :key="'b' + i">
          <path
            :d="`M${44 + i * 46}-92 l16 3 -12 20 z`"
            :fill="BUNTING_COLORS[i % 4]"
            stroke="#4A3F4A"
            stroke-width="2"
            stroke-linejoin="round"
          />
        </g>
      </g>
    </template>

    <!-- 地板轮廓 -->
    <polygon
      :points="floorPoints"
      fill="none"
      :stroke="palette.ink"
      stroke-width="5"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
  </g>
</template>
