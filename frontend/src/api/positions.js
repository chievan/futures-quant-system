import api from './client'

export const positionsApi = {
  getCurrent: () => api.get('/positions/current'),
  getHistory: (taskId, page = 1, size = 20) => api.get(`/positions/history/${taskId}`, { params: { page, size } }),
  getAnalysis: (taskId) => api.get(`/positions/analysis/${taskId}`),
  exportCsv: (taskId) => api.get(`/positions/export/${taskId}`, { responseType: 'blob' }),
}
