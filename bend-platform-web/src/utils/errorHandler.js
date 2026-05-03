import { createApp } from 'vue'

export function setupErrorHandler(app) {
  app.config.errorHandler = (err, instance, info) => {
    console.error('[Global Error Handler]', {
      error: err,
      component: instance,
      info: info,
      timestamp: new Date().toISOString()
    })

    if (window.$message) {
      window.$message.error('系统错误: ' + (err.message || '未知错误'))
    }
  }

  app.config.warnHandler = (msg, instance, trace) => {
    console.warn('[Vue Warning]', {
      message: msg,
      trace: trace,
      timestamp: new Date().toISOString()
    })
  }

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Unhandled Promise Rejection]', {
      reason: event.reason,
      timestamp: new Date().toISOString()
    })
    event.preventDefault()
  })

  window.addEventListener('error', (event) => {
    console.error('[Global Error]', {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: event.error,
      timestamp: new Date().toISOString()
    })
  })
}
