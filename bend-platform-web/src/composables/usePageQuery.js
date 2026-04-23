import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'

/**
 * 分页查询 Hook
 *
 * 功能说明：
 * - 封装分页查询的通用逻辑
 * - 支持排序、筛选、分页
 * - 自动处理加载状态和错误
 *
 * @param {Function} apiFunc - API 调用函数，接收 pageRequest 参数
 * @returns 分页查询相关的数据和方法
 */
export function usePageQuery(apiFunc) {
  const loading = ref(false)
  const tableData = ref([])
  const total = ref(0)

  const queryParams = reactive({
    page: 1,
    pageSize: 10,
    sortField: 'createTime',
    sortOrder: 'desc'
  })

  const pagination = computed(() => ({
    currentPage: queryParams.page,
    pageSize: queryParams.pageSize,
    total: total.value
  }))

  async function fetchData() {
    if (loading.value) return

    loading.value = true
    try {
      const response = await apiFunc(queryParams)

      if (response.code === 200 || response.code === 0) {
        tableData.value = response.data.records || response.data.list || []
        total.value = response.data.total || 0
      } else {
        ElMessage.error(response.message || '查询失败')
      }
    } catch (error) {
      console.error('查询错误:', error)
      ElMessage.error(error.message || '网络错误')
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page) {
    queryParams.page = page
    fetchData()
  }

  function handleSizeChange(size) {
    queryParams.pageSize = size
    queryParams.page = 1
    fetchData()
  }

  function handleSortChange({ prop, order }) {
    if (prop && order) {
      queryParams.sortField = prop
      queryParams.sortOrder = order === 'ascending' ? 'asc' : 'desc'
    } else {
      queryParams.sortField = 'createTime'
      queryParams.sortOrder = 'desc'
    }
    fetchData()
  }

  function resetQuery() {
    queryParams.page = 1
    queryParams.pageSize = 10
    fetchData()
  }

  function setQueryParams(params) {
    Object.assign(queryParams, params)
  }

  return {
    loading,
    tableData,
    total,
    queryParams,
    pagination,
    fetchData,
    handlePageChange,
    handleSizeChange,
    handleSortChange,
    resetQuery,
    setQueryParams
  }
}

/**
 * 表单弹框 Hook
 *
 * 功能说明：
 * - 封装新增/编辑的通用逻辑
 * - 支持表单校验
 * - 自动处理 loading 状态
 *
 * @param {Function} createApi - 创建 API
 * @param {Function} updateApi - 更新 API
 * @param {Function} fetchDetailApi - 获取详情 API
 * @returns 表单弹框相关的数据和方法
 */
export function useFormDialog(createApi, updateApi, fetchDetailApi) {
  const dialogVisible = ref(false)
  const dialogLoading = ref(false)
  const isEdit = ref(false)
  const formData = ref({})
  const formRef = ref(null)

  const formRules = {}

  async function openDialog(id = null) {
    dialogVisible.value = true
    isEdit.value = !!id
    formData.value = {}

    if (id) {
      await loadDetail(id)
    }
  }

  async function loadDetail(id) {
    dialogLoading.value = true
    try {
      const response = await fetchDetailApi(id)
      if (response.code === 200 || response.code === 0) {
        formData.value = { ...response.data }
      } else {
        ElMessage.error(response.message || '加载失败')
      }
    } catch (error) {
      ElMessage.error(error.message || '加载失败')
    } finally {
      dialogLoading.value = false
    }
  }

  async function handleSubmit() {
    if (!formRef.value) return

    await formRef.value.validate(async (valid) => {
      if (!valid) return

      dialogLoading.value = true
      try {
        const api = isEdit.value ? updateApi : createApi
        const data = { ...formData.value }

        if (isEdit.value) {
          delete data.createTime
          delete data.updateTime
        }

        const response = await api(data)

        if (response.code === 200 || response.code === 0) {
          ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
          dialogVisible.value = false
          return true
        } else {
          ElMessage.error(response.message || '操作失败')
          return false
        }
      } catch (error) {
        ElMessage.error(error.message || '操作失败')
        return false
      } finally {
        dialogLoading.value = false
      }
    })
  }

  function handleCancel() {
    dialogVisible.value = false
    formRef.value?.resetFields()
  }

  function closeDialog() {
    dialogVisible.value = false
    formRef.value?.resetFields()
    formData.value = {}
  }

  return {
    dialogVisible,
    dialogLoading,
    isEdit,
    formData,
    formRef,
    formRules,
    openDialog,
    loadDetail,
    handleSubmit,
    handleCancel,
    closeDialog
  }
}

/**
 * 删除确认 Hook
 *
 * @param {Function} deleteApi - 删除 API
 * @param {Function} onSuccess - 删除成功回调
 */
export function useDeleteConfirm(deleteApi, onSuccess) {
  async function handleDelete(id, name = '数据') {
    try {
      await ElMessageBox.confirm(
        `确定删除 ${name} 吗？删除后无法恢复。`,
        '删除确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )

      const response = await deleteApi(id)

      if (response.code === 200 || response.code === 0) {
        ElMessage.success('删除成功')
        onSuccess?.()
      } else {
        ElMessage.error(response.message || '删除失败')
      }
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error(error.message || '删除失败')
      }
    }
  }

  return {
    handleDelete
  }
}
