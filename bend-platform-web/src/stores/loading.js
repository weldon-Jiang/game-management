import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLoadingStore = defineStore('loading', () => {
  const loadingStates = ref({})

  const setLoading = (key, loading) => {
    loadingStates.value[key] = loading
  }

  const isLoading = (key) => {
    return loadingStates.value[key] || false
  }

  const startLoading = (key) => {
    setLoading(key, true)
  }

  const stopLoading = (key) => {
    setLoading(key, false)
  }

  return {
    loadingStates,
    setLoading,
    isLoading,
    startLoading,
    stopLoading
  }
})
