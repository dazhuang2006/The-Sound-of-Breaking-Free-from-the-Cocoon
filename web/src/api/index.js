import { http } from './client'

export const authApi = {
  register: (payload) => http.post('/auth/register', payload),
  login: (payload) => http.post('/auth/login', payload),
  me: () => http.get('/auth/me')
}

export const childrenApi = {
  list: () => http.get('/children'),
  create: (payload) => http.post('/children', payload)
}

export const chatApi = {
  send: (payload) => http.post('/chat', payload),
  sessions: () => http.get('/chat/sessions'),
  session: (id) => http.get(`/chat/sessions/${id}`),
  remove: (id) => http.delete(`/chat/sessions/${id}`)
}

export const trainingApi = {
  scenarios: () => http.get('/training/scenarios'),
  start: (payload) => http.post('/training/start', payload),
  get: (id) => http.get(`/training/${id}`),
  answer: (id, answer) => http.post(`/training/${id}/answer`, { answer }),
  end: (id) => http.post(`/training/${id}/end`),
  sessions: () => http.get('/training/sessions')
}

export const followupApi = {
  records: (childId, days = 14) => http.get('/followup/records', { params: { child_id: childId, days } }),
  createRecord: (payload) => http.post('/followup/records', payload),
  summaries: (childId) => http.get('/followup/summaries', { params: { child_id: childId } }),
  createSummary: (payload) => http.post('/followup/summary', payload)
}

export const knowledgeApi = {
  search: (payload) => http.post('/knowledge/search', payload),
  docs: () => http.get('/knowledge/docs'),
  ingest: () => http.post('/knowledge/ingest')
}
