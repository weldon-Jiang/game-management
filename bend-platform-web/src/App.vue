<script setup>
import { onErrorCaptured } from 'vue'
import { ElMessage } from 'element-plus'
import { isRequestCanceled } from '@/utils/request'

/**
 * 根组件：挂载 router-view，并捕获子组件未处理的渲染/生命周期错误。
 * 用户主动取消（弹窗 ESC、请求 abort）不弹 toast，避免任务详情页误报。
 */

const isBenignUserCancel = (err) => {
  if (isRequestCanceled(err)) return true
  const errorMsg = typeof err === 'string' ? err : err?.message
  return errorMsg === 'cancel' || errorMsg === 'ESC' || errorMsg === 'canceled'
}

onErrorCaptured((err, instance, info) => {
  if (isBenignUserCancel(err)) {
    return false
  }
  console.error('=== Vue Error Captured ===')
  console.error('Error:', err)
  console.error('Error Message:', err?.message)
  console.error('Error Name:', err?.name)
  console.error('Component:', instance)
  console.error('Info:', info)
  console.error('Stack:', err?.stack)
  ElMessage.error('页面错误: ' + (err?.message || err))
  return false
})
</script>

<template>
  <router-view />
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body {
  height: 100%;
  font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100%;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

.dialog-form {
  padding-top: 8px;
}

.dialog-form .el-form-item:first-child {
  margin-top: 4px;
}
</style>
