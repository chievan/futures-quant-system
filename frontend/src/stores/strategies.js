import { defineStore } from 'pinia'
import { ref } from 'vue'
import { strategiesApi } from '../api/strategies'

export const useStrategiesStore = defineStore('strategies', () => {
  const strategies = ref([])
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try {
      const data = await strategiesApi.list()
      strategies.value = data.strategies
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    await strategiesApi.create(payload)
    await fetchAll()
  }

  async function remove(id) {
    await strategiesApi.delete(id)
    await fetchAll()
  }

  return { strategies, loading, fetchAll, create, remove }
})
