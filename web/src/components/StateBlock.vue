<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  type: { type: String, default: 'empty' }, // empty | loading | error
  title: { type: String, default: '' },
  desc: { type: String, default: '' },
  action: { type: String, default: '' }
})

defineEmits(['action'])
</script>

<template>
  <div class="state-block" :class="{ 'error-state': type === 'error' }">
    <div class="state-icon">
      <AppIcon :name="type === 'error' ? 'alert' : type === 'loading' ? 'refresh' : 'leaf'" :size="22" />
    </div>
    <template v-if="type === 'loading'">
      <div style="width: min(260px, 80%)">
        <div class="skeleton skeleton-line" style="width: 100%"></div>
        <div class="skeleton skeleton-line" style="width: 78%"></div>
        <div class="skeleton skeleton-line" style="width: 56%; margin-bottom: 0"></div>
      </div>
      <span v-if="desc">{{ desc }}</span>
    </template>
    <template v-else>
      <b v-if="title">{{ title }}</b>
      <p v-if="desc" style="max-width: 420px">{{ desc }}</p>
      <button v-if="action" class="btn ghost small" style="margin-top: 6px" @click="$emit('action')">
        {{ action }}
      </button>
    </template>
  </div>
</template>
