<script setup>
defineProps({
  level: { type: String, default: 'normal' },
  categories: { type: Array, default: () => [] }
})

const text = {
  emergency: '已触发紧急安全拦截：请优先处理现场安全并立即就医',
  redirect: '已阻断医疗判断类内容：诊断与用药请遵医嘱',
  caution: '已附加安全提醒：涉及自伤或攻击行为，请优先保证安全'
}
const cls = {
  emergency: 'danger',
  redirect: 'amber',
  caution: 'amber'
}
</script>

<template>
  <div v-if="level !== 'normal'" class="badge" :class="cls[level] || 'amber'" style="margin-bottom: 7px; white-space: normal; text-align: left;">
    {{ text[level] || '已触发安全提示' }}
  </div>
</template>
