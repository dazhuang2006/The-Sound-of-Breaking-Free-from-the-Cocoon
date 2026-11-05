import { reactive } from 'vue'
import { authApi, childrenApi } from './api'

export const store = reactive({
  token: localStorage.getItem('pojian_token') || '',
  user: null,
  children: [],
  childId: Number(localStorage.getItem('pojian_child_id')) || null,
  ready: false
})

export function setToken(token) {
  store.token = token
  if (token) localStorage.setItem('pojian_token', token)
  else localStorage.removeItem('pojian_token')
}

export function setChild(id) {
  store.childId = id || null
  if (id) localStorage.setItem('pojian_child_id', String(id))
  else localStorage.removeItem('pojian_child_id')
}

export async function loadChildren() {
  const { data } = await childrenApi.list()
  store.children = data
  if (!data.some((item) => item.id === store.childId)) {
    setChild(data.length ? data[0].id : null)
  }
  return data
}

export async function bootstrap() {
  const { data } = await authApi.me()
  store.user = data
  await loadChildren()
  store.ready = true
}

export function logout() {
  store.user = null
  store.children = []
  setChild(null)
  setToken('')
}
