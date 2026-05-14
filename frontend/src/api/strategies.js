import api from './client'

export const strategiesApi = {
  list: () => api.get('/strategies/'),
  get: (id) => api.get(`/strategies/${id}`),
  create: (payload) => api.post('/strategies/', payload),
  update: (id, payload) => api.put(`/strategies/${id}`, payload),
  delete: (id) => api.delete(`/strategies/${id}`),
}
