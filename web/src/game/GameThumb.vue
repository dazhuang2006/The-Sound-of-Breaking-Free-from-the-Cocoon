<script setup>
/** 关卡缩略图：用同一套房间资产渲染，保证「选场景」与「进游戏」看到的是同一个世界。 */
import { computed } from 'vue'
import RoomShell from './art/RoomShell.vue'
import PropSprite from './art/PropSprite.vue'
import CharacterSprite from './art/CharacterSprite.vue'
import { VIEW_BOX, isoX, isoY } from './iso'

const props = defineProps({
  art: { type: String, default: 'home' },
  env: { type: String, default: 'indoor' }
})

const LAYOUT = {
  home: {
    props: [
      ['sofa', 7.6, 1.5],
      ['plant', 13.8, 3.4],
      ['coffee_table', 7.4, 4.6]
    ],
    npc: { role: 'parent', x: 9.8, y: 4.4 }
  },
  classroom: {
    props: [
      ['teacher_desk', 12, 2.4],
      ['bookshelf', 2, 1.7],
      ['desk', 5.2, 5.2]
    ],
    npc: { role: 'teacher', x: 10.4, y: 4.4 }
  },
  playground: {
    props: [
      ['slide', 12.4, 3.6],
      ['tree', 1.8, 6.2],
      ['sandbox', 6.6, 7.8]
    ],
    npc: { role: 'peer', x: 6.4, y: 6.2 }
  },
  store: {
    props: [
      ['counter', 9.6, 5.6],
      ['fridge', 6, 2],
      ['shelf', 2.6, 3.2]
    ],
    npc: { role: 'shopkeeper', x: 9.6, y: 4.2 }
  }
}

const layout = computed(() => LAYOUT[props.art] || LAYOUT.home)

function at(x, y) {
  return `translate(${isoX(x, y)} ${isoY(x, y)})`
}
</script>

<template>
  <svg class="game-thumb" :viewBox="VIEW_BOX" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <RoomShell :art="art" :env="env" />
    <g v-for="([key, x, y], index) in layout.props" :key="key + index" :transform="at(x, y)">
      <PropSprite :art="key" />
    </g>
    <g :transform="at(layout.npc.x, layout.npc.y)">
      <CharacterSprite :role="layout.npc.role" facing="down" />
    </g>
  </svg>
</template>
