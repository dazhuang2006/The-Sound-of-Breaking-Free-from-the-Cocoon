<script setup>
/**
 * 角色造型：小朋友 / 老师 / 家长 / 阿姨 / 小伙伴 / 店员。
 *
 * 原点 (0, 0) 在脚底，角色向上生长，身高约 124px；
 * 走动时四肢摆动、身体轻微上下起伏，点击后会自动朝向目标。
 */
import { computed } from 'vue'

const props = defineProps({
  role: { type: String, default: 'child' },
  facing: { type: String, default: 'down' },
  walking: { type: Boolean, default: false },
  phase: { type: Number, default: 0 },
  mood: { type: String, default: 'idle' }
})

const INK = '#4A3F4A'

const PALETTES = {
  child: {
    skin: '#FFE4D5',
    hair: '#6B4A3A',
    top: '#F7A8B8',
    bottom: '#F2A9BC',
    shoe: '#C98FA0',
    accent: '#FFF2F5'
  },
  parent: {
    skin: '#FFE4D5',
    hair: '#4E3A32',
    top: '#A9D6EE',
    bottom: '#8FC6E4',
    shoe: '#6B5A54',
    accent: '#FFFFFF'
  },
  teacher: {
    skin: '#FFE0CD',
    hair: '#4A3B33',
    top: '#9DD8C4',
    bottom: '#6FB8A6',
    shoe: '#5C5148',
    accent: '#FFFFFF'
  },
  auntie: {
    skin: '#FFE4D5',
    hair: '#5A4038',
    top: '#FBD98F',
    bottom: '#E7BC69',
    shoe: '#6B5A54',
    accent: '#FFF8E8'
  },
  peer: {
    skin: '#FFE0CD',
    hair: '#4A3B33',
    top: '#BFE3F5',
    bottom: '#7FA8C9',
    shoe: '#5C6B7A',
    accent: '#FFFFFF'
  },
  shopkeeper: {
    skin: '#FFE0CD',
    hair: '#3F322B',
    top: '#F7C6D0',
    bottom: '#D9A0B0',
    shoe: '#5C5148',
    accent: '#FFFFFF'
  }
}

const palette = computed(() => PALETTES[props.role] || PALETTES.child)
const flip = computed(() => (props.facing === 'left' ? -1 : 1))
const back = computed(() => props.facing === 'up')
const phase = computed(() => props.phase || 0)
const swing = computed(() => (props.walking ? Math.sin(phase.value) : 0))
const bob = computed(() => (props.walking ? -Math.abs(Math.cos(phase.value)) * 2.2 : 0))
const legAngle = computed(() => swing.value * 16)
const armAngle = computed(() => swing.value * -13)
const lean = computed(() => (props.walking ? 1.4 : 0))

const isChild = computed(() => props.role === 'child')
const isTeacher = computed(() => props.role === 'teacher')
const isMom = computed(() => props.role === 'parent')
const isAuntie = computed(() => props.role === 'auntie')
const isPeer = computed(() => props.role === 'peer')
const isShop = computed(() => props.role === 'shopkeeper')
</script>

<template>
  <g class="character-sprite" :class="[role, mood]">
    <ellipse cx="0" cy="2" rx="24" ry="8" fill="rgba(74,63,74,0.16)" />

    <g :transform="`scale(${flip} 1)`">
      <g :transform="`translate(0 ${bob}) rotate(${lean})`">
        <!-- 腿 -->
        <g :transform="`rotate(${legAngle} -9 -34)`">
          <rect x="-15" y="-36" width="12" height="34" rx="6" :fill="palette.bottom" :stroke="INK" stroke-width="3.6" />
          <ellipse cx="-9" cy="-4" rx="9" ry="6" :fill="palette.shoe" :stroke="INK" stroke-width="3" />
        </g>
        <g :transform="`rotate(${-legAngle} 9 -34)`">
          <rect x="3" y="-36" width="12" height="34" rx="6" :fill="palette.bottom" :stroke="INK" stroke-width="3.6" />
          <ellipse cx="9" cy="-4" rx="9" ry="6" :fill="palette.shoe" :stroke="INK" stroke-width="3" />
        </g>

        <!-- 裙子 / 上衣 -->
        <path
          v-if="isChild || isMom || isAuntie || isShop"
          d="M-17-80q17-6 34 0l12 46q-29 9-58 0z"
          :fill="palette.top"
          :stroke="INK"
          stroke-width="4"
          stroke-linejoin="round"
        />
        <path
          v-else
          d="M-16-80q16-6 32 0l4 44q-20 7-40 0z"
          :fill="palette.top"
          :stroke="INK"
          stroke-width="4"
          stroke-linejoin="round"
        />
        <path d="M-6-80l6 8 6-8" :fill="palette.accent" :stroke="INK" stroke-width="2.6" stroke-linejoin="round" />

        <!-- 手臂 -->
        <g :transform="`rotate(${armAngle} -17 -74)`">
          <rect x="-24" y="-76" width="10" height="34" rx="5" :fill="palette.top" :stroke="INK" stroke-width="3.4" />
          <circle cx="-19" cy="-42" r="5.5" :fill="palette.skin" :stroke="INK" stroke-width="3" />
        </g>
        <g :transform="`rotate(${-armAngle} 17 -74)`">
          <rect x="14" y="-76" width="10" height="34" rx="5" :fill="palette.top" :stroke="INK" stroke-width="3.4" />
          <circle cx="19" cy="-42" r="5.5" :fill="palette.skin" :stroke="INK" stroke-width="3" />
        </g>

        <!-- 头 -->
        <g>
          <circle cx="-24" cy="-98" r="7" :fill="palette.skin" :stroke="INK" stroke-width="3" />
          <circle cx="24" cy="-98" r="7" :fill="palette.skin" :stroke="INK" stroke-width="3" />
          <circle cx="0" cy="-102" r="25" :fill="palette.skin" :stroke="INK" stroke-width="4" />

          <!-- 头发（背面） -->
          <path
            v-if="back"
            d="M-25-104q0-26 25-26t25 26q0 12-8 16h-34q-8-4-8-16z"
            :fill="palette.hair"
            :stroke="INK"
            stroke-width="4"
            stroke-linejoin="round"
          />

          <template v-else>
            <!-- 刘海 -->
            <path
              d="M-25-106q2-24 25-24t25 24q-9-9-25-9t-25 9z"
              :fill="palette.hair"
              :stroke="INK"
              stroke-width="4"
              stroke-linejoin="round"
            />
            <!-- 眼睛 -->
            <circle cx="-8.5" cy="-101" r="3" fill="#3A3038" />
            <circle cx="8.5" cy="-101" r="3" fill="#3A3038" />
            <circle cx="-7.4" cy="-102.3" r="1" fill="#FFFFFF" />
            <circle cx="9.6" cy="-102.3" r="1" fill="#FFFFFF" />
            <!-- 腮红 -->
            <ellipse cx="-15" cy="-93" rx="5.4" ry="3.2" fill="#F7B7C2" opacity="0.65" />
            <ellipse cx="15" cy="-93" rx="5.4" ry="3.2" fill="#F7B7C2" opacity="0.65" />
            <!-- 嘴 -->
            <path d="M-6-88q6 6 12 0" fill="none" :stroke="INK" stroke-width="2.8" stroke-linecap="round" />
          </template>

          <!-- 发型 / 配饰 -->
          <g v-if="isChild && !back">
            <circle cx="-27" cy="-114" r="11" :fill="palette.hair" :stroke="INK" stroke-width="3.4" />
            <circle cx="27" cy="-114" r="11" :fill="palette.hair" :stroke="INK" stroke-width="3.4" />
            <circle cx="-30" cy="-117" r="3" fill="#F7C6D0" />
            <circle cx="30" cy="-117" r="3" fill="#F7C6D0" />
          </g>
          <g v-else-if="isMom || isTeacher">
            <circle cx="0" cy="-130" r="12" :fill="palette.hair" :stroke="INK" stroke-width="3.4" />
            <path d="M-22-110q-6-14 4-20" fill="none" :stroke="INK" stroke-width="3" stroke-linecap="round" />
            <path d="M22-110q6-14-4-20" fill="none" :stroke="INK" stroke-width="3" stroke-linecap="round" />
          </g>
          <g v-else-if="isAuntie">
            <path d="M-24-108q-4-20 24-20t24 20q0 8-6 10-18-8-36 0-6-2-6-10z" :fill="palette.hair" :stroke="INK" stroke-width="3.4" />
          </g>
          <g v-else-if="isPeer">
            <path d="M-25-108q0-24 25-24t25 24z" fill="#8FD3C3" :stroke="INK" stroke-width="3.6" stroke-linejoin="round" />
            <path d="M-25-108q-14 2-16 8 10 4 20 0z" fill="#8FD3C3" :stroke="INK" stroke-width="3.2" stroke-linejoin="round" />
            <circle cx="0" cy="-133" r="4" fill="#FBE7AE" :stroke="INK" stroke-width="2.4" />
          </g>
          <g v-else-if="isShop">
            <path d="M-25-108q0-24 25-24t25 24z" fill="#F7C6D0" :stroke="INK" stroke-width="3.6" stroke-linejoin="round" />
            <rect x="-26" y="-112" width="52" height="10" rx="5" fill="#FFF3F6" :stroke="INK" stroke-width="3" />
          </g>

          <!-- 眼镜 -->
          <g v-if="isTeacher || isAuntie" fill="none" :stroke="INK" stroke-width="2.6">
            <circle cx="-8.5" cy="-101" r="9" />
            <circle cx="8.5" cy="-101" r="9" />
            <path d="M-18.5-101h-6M18.5-101h6" stroke-linecap="round" />
          </g>
        </g>

        <!-- 围裙 -->
        <g v-if="isShop">
          <path d="M-14-62h28l4 30h-36z" fill="#FFF9F0" :stroke="INK" stroke-width="3.4" stroke-linejoin="round" />
          <rect x="-6" y="-44" width="12" height="9" rx="2" fill="#9DD8C4" />
        </g>
        <g v-else-if="isMom">
          <path d="M-13-60h26l3 28h-32z" fill="#FFFFFF" :stroke="INK" stroke-width="3" stroke-linejoin="round" opacity="0.9" />
        </g>
      </g>
    </g>
  </g>
</template>
