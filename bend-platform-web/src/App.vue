<script setup>
import { onErrorCaptured } from 'vue'
import { ElMessage } from 'element-plus'

/**
 * 根组件
 * 作用：作为Vue应用的根组件，使用router-view显示路由页面
 * 包含全局错误处理，防止子组件错误导致应用崩溃
 */

// 全局错误捕获
onErrorCaptured((err, instance, info) => {
  const errorMsg = typeof err === 'string' ? err : err?.message
  if (errorMsg === 'cancel' || errorMsg === 'ESC') {
    return false
  }
  console.error('=== Vue Error Captured ===')
  console.error('Error:', err)
  console.error('Error Message:', err?.message)
  console.error('Error Name:', err?.name)
  console.error('Component:', instance)
  console.error('Info:', info)
  console.error('Stack:', err?.stack)
  ElMessage.error('页面加载出错: ' + (err?.message || err))
  return false
})
</script>

<template>
  <!-- 使用 router-view 显示路由匹配的页面组件 -->
  <router-view />
</template>

<style>
/**
 * 全局样式重置和基础配置
 */

/* 重置外边距 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* 设置HTML和body样式 */
html,
body {
  height: 100%;
  font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 设置应用容器 */
#app {
  height: 100%;
}

/* 全局滚动条样式 */
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

/* 弹框表单统一样式 */
.dialog-form {
  padding-top: 8px;
}

.dialog-form .el-form-item:first-child {
  margin-top: 4px;
}
</style>