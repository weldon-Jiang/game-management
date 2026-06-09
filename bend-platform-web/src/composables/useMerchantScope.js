import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { merchantApi } from '@/api'

/**
 * 平台管理员商户筛选：加载商户列表、维护 filterMerchantId、注入查询参数。
 */
export function useMerchantScope() {
  const authStore = useAuthStore()
  const merchantList = ref([])
  const filterMerchantId = ref('')
  const merchantsLoaded = ref(false)

  const isPlatformAdmin = computed(() => authStore.isPlatformAdmin)

  const loadMerchants = async () => {
    if (!authStore.isPlatformAdmin) return
    try {
      const res = await merchantApi.listAll()
      merchantList.value = res.data || []
      merchantsLoaded.value = true
    } catch (error) {
      console.error('Failed to load merchants:', error)
      merchantList.value = []
    }
  }

  /** 将商户筛选写入 API 查询参数（仅平台管理员且已选择时）。 */
  const applyMerchantFilter = (params) => {
    if (authStore.isPlatformAdmin && filterMerchantId.value) {
      params.merchantId = filterMerchantId.value
    }
    return params
  }

  const resetMerchantFilter = () => {
    filterMerchantId.value = ''
  }

  return {
    isPlatformAdmin,
    merchantList,
    filterMerchantId,
    merchantsLoaded,
    loadMerchants,
    applyMerchantFilter,
    resetMerchantFilter
  }
}
