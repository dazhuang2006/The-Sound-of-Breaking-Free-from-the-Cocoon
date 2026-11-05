<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store, logout, setChild } from './store'

const route = useRoute()
const router = useRouter()

const navs = [
  { name: 'chat', label: '居家答疑', path: '/', icon: 'chat' },
  { name: 'training', label: '情景训练', path: '/training', icon: 'play' },
  { name: 'followup', label: '康复随访', path: '/followup', icon: 'chart' },
  { name: 'children', label: '孩子档案', path: '/children', icon: 'child' }
]

const current = computed(() => navs.find((item) => item.name === route.name)?.label || '')

function onChildChange(event) {
  setChild(Number(event.target.value) || null)
}

function signOut() {
  logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div v-if="store.user" class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">破</div>
        <div>
          <div class="brand-title">破茧之声</div>
          <div class="brand-sub">居家康复 · 医疗随访</div>
        </div>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navs"
          :key="item.name"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.name === item.name }"
        >
          <svg v-if="item.icon === 'chat'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" stroke-linejoin="round" />
          </svg>
          <svg v-else-if="item.icon === 'play'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <circle cx="12" cy="12" r="9" /><path d="M10 8.5 16 12l-6 3.5v-7Z" stroke-linejoin="round" />
          </svg>
          <svg v-else-if="item.icon === 'chart'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <path d="M4 19V5M4 19h16" stroke-linecap="round" />
            <path d="M8 15v-4M12 15V8M16 15v-6" stroke-linecap="round" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <circle cx="12" cy="8" r="3.4" /><path d="M5 20c.7-3.3 3.5-5 7-5s6.3 1.7 7 5" stroke-linecap="round" />
          </svg>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="child-box">
          <label>当前孩子</label>
          <select v-if="store.children.length" :value="store.childId || ''" @change="onChildChange">
            <option v-for="child in store.children" :key="child.id" :value="child.id">
              {{ child.nickname }}
            </option>
          </select>
          <div v-else class="empty">还没有档案 · <router-link to="/children">去添加</router-link></div>
        </div>
        <div class="user-row">
          <div>
            <div class="user-name">{{ store.user.display_name }}</div>
            <div class="user-role">{{ store.user.role === 'professional' ? '康复从业者' : '家长' }}</div>
          </div>
          <button class="logout" @click="signOut">退出</button>
        </div>
      </div>
    </aside>

    <main class="main">
      <router-view :key="current" />
    </main>
  </div>

  <router-view v-else />
</template>
