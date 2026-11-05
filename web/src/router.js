import { createRouter, createWebHashHistory } from 'vue-router'
import { store, bootstrap } from './store'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'chat', component: () => import('./views/ChatView.vue') },
  { path: '/training', name: 'training', component: () => import('./views/TrainingView.vue') },
  { path: '/followup', name: 'followup', component: () => import('./views/FollowupView.vue') },
  { path: '/children', name: 'children', component: () => import('./views/ChildrenView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
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
