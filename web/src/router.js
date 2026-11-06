import { createRouter, createWebHashHistory } from 'vue-router'
import { store, bootstrap } from './store'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('./views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('./views/DashboardView.vue'),
    meta: { title: '工作台', subtitle: '今天也可以慢慢来，一次只做一小步' }
  },
  {
    path: '/children',
    name: 'children',
    component: () => import('./views/ChildrenView.vue'),
    meta: { title: '儿童档案', subtitle: '家长自述，不含诊断结论；敏感备注默认折叠' }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('./views/ChatView.vue'),
    meta: { title: 'AI 康复答疑', subtitle: '回答只基于知识库与孩子档案，并标注来源' }
  },
  {
    path: '/game',
    name: 'game',
    component: () => import('./views/GameView.vue'),
    meta: { title: '儿童情景模拟', immersive: true }
  },
  {
    path: '/followup',
    name: 'followup',
    component: () => import('./views/FollowupView.vue'),
    meta: { title: '康复随访', subtitle: '记录—整理—确认，三步留下可回看的变化' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/SettingsView.vue'),
    meta: { title: '系统设置', subtitle: '语音、外观与隐私偏好' }
  },
  {
    path: '/training',
    name: 'training',
    component: () => import('./views/TrainingView.vue'),
    meta: { title: '文字版情景训练', subtitle: '只用文字作答的轻量版本，适合家长代填' }
  },
  { path: '/', redirect: '/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  if (!store.token) return { name: 'login' }
  if (!store.user) {
    try {
      await bootstrap()
    } catch {
      store.token = ''
      localStorage.removeItem('pojian_token')
      return { name: 'login' }
    }
  }
  return true
})

export default router
