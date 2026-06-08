<script setup>
import { onErrorCaptured } from 'vue'
import { ElMessage } from 'element-plus'

/**
 * ???? * ?????Vue?????????router-view??????
 * ??????????????????????
 */

// ??????
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
  ElMessage.error('??????: ' + (err?.message || err))
  return false
})
</script>

<template>
  <!-- ?? router-view ????????????-->
  <router-view />
</template>

<style>
/**
 * ???????????
 */

/* ??????*/
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* ??HTML?body?? */
html,
body {
  height: 100%;
  font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ?????? */
#app {
  height: 100%;
}

/* ????????*/
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

/* ???????????? element-plus.css .el-dialog .el-form? */
.dialog-form {
  padding-top: 8px;
}

.dialog-form .el-form-item:first-child {
  margin-top: 4px;
}
</style>