import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE || '/api/v1'

export const http = axios.create({ baseURL, timeout: 90000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('pojian_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && !location.hash.includes('/login')) {
      localStorage.removeItem('pojian_token')
      location.hash = '#/login'
    }
    return Promise.reject(error)
  }
)

export function apiError(error) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('；')
  }
  return detail || error?.message || '网络异常，请稍后再试'
}
