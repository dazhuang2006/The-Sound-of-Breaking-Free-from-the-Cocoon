<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store, logout, setChild } from './store'
import AppIcon from './components/AppIcon.vue'
import BrandMark from './components/BrandMark.vue'

const route = useRoute()
const router = useRouter()

const navs = [
  { name: 'dashboard', label: '工作台', path: '/dashboard', icon: 'dashboard' },
  { name: 'children', label: '儿童档案', path: '/children', icon: 'child' },
  { name: 'chat', label: 'AI 康复答疑', path: '/chat', icon: 'chat' },
  { name: 'game', label: '儿童情景模拟', path: '/game', icon: 'game' },
  { name: 'followup', label: '康复随访', path: '/followup', icon: 'chart' },
  { name: 'settings', label: '系统设置', path: '/settings', icon: 'settings' }
]

const immersive = computed(() => Boolean(route.meta.immersive))
const current = computed(() => navs.find((item) => item.name === route.name) || null)
const pageTitle = computed(() => route.meta.title || current.value?.label || '工作台')
const pageSub = computed(() => route.meta.subtitle || '')
const today = new Date()
const dateLabel = `${today.getMonth() + 1} 月 ${today.getDate()} 日`

function onChildChange(event) {
  setChild(Number(event.target.value) || null)
}

function signOut() {
  logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <router-view v-if="!store.user || route.meta.public" />

  <router-view v-else-if="immersive" />

  <div v-else class="app-shell">
    <aside class="sidebar">
      <router-link to="/dashboard" class="brand">
        <BrandMark :size="42" />
        <div>
          <div class="brand-title">破茧之声</div>
          <div class="brand-sub">星星的孩子 · 居家康复</div>
        </div>
      </router-link>

      <nav class="nav">
        <router-link
          v-for="item in navs"
          :key="item.name"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.name === item.name }"
        >
          <AppIcon :name="item.icon" :size="19" />
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

    <div class="shell-main">
      <header class="topbar">
        <div>
          <div class="topbar-title">{{ pageTitle }}</div>
          <div v-if="pageSub" class="topbar-sub">{{ pageSub }}</div>
        </div>
        <div class="topbar-actions">
          <span class="badge">
            <AppIcon name="sun" :size="13" />
            {{ dateLabel }}
          </span>
          <router-link v-if="!store.children.length" class="badge primary" to="/children">
            添加孩子档案
          </router-link>
          <span v-else class="badge primary">
            <AppIcon name="heart" :size="13" />
            {{ store.children.find((item) => item.id === store.childId)?.nickname || '未选择' }}
          </span>
        </div>
      </header>

      <main class="content">
        <router-view :key="route.name" />
      </main>
    </div>
  </div>
</template>
