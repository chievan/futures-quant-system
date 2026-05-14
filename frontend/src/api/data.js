import api from './client'

export const dataApi = {
  getContracts: () => api.get('/data/contracts'),
  getInfo: (contract) => api.get(`/data/info/${contract}`),
  deleteData: (payload) => api.delete('/data/delete', { data: payload }),
  download: (payload) => api.post('/data/download', payload),
  getTasks: () => api.get('/data/tasks'),
  getQuality: (contract) => api.get(`/data/quality/${contract}`),
}
