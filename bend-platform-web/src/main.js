import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import router from '@/router'
import App from './App.vue'
import './style.css'
import { setupErrorHandler } from '@/utils/errorHandler'

/**
 * Bend Platform 前端应用入口
 * 功能：初始化Vue应用、配置插件和全局样式
 */

// 创建Vue应用实例
const app = createApp(App)

// 创建Pinia状态管理实例
const pinia = createPinia()

// 注册Pinia插件
app.use(pinia)

// 注册Vue Router插件
app.use(router)

// 注册Element Plus插件，并设置中文语言包
app.use(ElementPlus, { locale: zhCn })

// 设置全局错误处理器
setupErrorHandler(app)

// 挂载应用到#app元素
app.mount('#app')