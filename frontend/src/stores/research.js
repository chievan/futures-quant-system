import { defineStore } from 'pinia'
import { ref } from 'vue'
import { researchApi } from '../api/research'

export const useResearchStore = defineStore('research', () => {
  const tasks = ref([])
  const loading = ref(false)
  const total = ref(0)

  async function fetchTasks(page = 1, size = 20) {
    loading.value = true
    try {
      const data = await researchApi.listTasks(page, size)
      tasks.value = data.tasks
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function submitBacktest(payload) {
    return await researchApi.submitBacktest(payload)
  }

  async function submitSearch(payload) {
    return await researchApi.submitSearch(payload)
  }

  async function getTask(taskId) {
    return await researchApi.getTask(taskId)
  }

  return { tasks, loading, total, fetchTasks, submitBacktest, submitSearch, getTask }
})
