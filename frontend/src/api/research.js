import api from './client'

export const researchApi = {
  submitBacktest: (payload) => api.post('/research/backtest', payload),
  submitSearch: (payload) => api.post('/research/search', payload),
  listTasks: (page = 1, size = 20) => api.get('/research/tasks', { params: { page, size } }),
  getTask: (taskId) => api.get(`/research/tasks/${taskId}`),
}
