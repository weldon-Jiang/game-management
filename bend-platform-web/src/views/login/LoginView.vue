<template>
  <div class="login-container">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
    </div>

    <!-- 登录表单卡片 -->
    <div class="login-card">
      <div class="card-header">
        <div class="logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h1>Bend Platform</h1>
        <p>商户管理平台</p>
      </div>

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="loginKey">
          <el-input
            v-model="loginForm.loginKey"
            placeholder="请输入账号或手机号"
            :prefix-icon="User"
            size="large"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="card-footer">
        <!-- <span>还没有账号？</span>
        <router-link to="/register">立即注册</router-link> -->
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

/**
 * 登录视图组件
 * 提供用户登录功能
 */
const router = useRouter()
const authStore = useAuthStore()

/**
 * 登录表单引用
 */
const loginFormRef = ref(null)

/**
 * 登录表单数据
 */
const loginForm = reactive({
  loginKey: '',
  password: ''
})

const loginRules = {
  loginKey: [
    { required: true, message: '请输入账号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 20, message: '密码长度为4-20个字符', trigger: 'blur' }
  ]
}

/**
 * 登录按钮加载状态
 */
const loading = ref(false)

/**
 * 处理登录请求
 * 1. 验证表单
 * 2. 调用登录接口
 * 3. 登录成功后跳转到首页
 */
const handleLogin = async () => {
  // 表单验证
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(loginForm.loginKey, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 登录页面容器 - 全屏占据 */
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0f;
  position: relative;
  overflow: hidden;
}

/* 背景装饰 - 渐变圆球 */
.bg-decoration {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}

.orb-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, #6366f1 0%, transparent 70%);
  top: -100px;
  right: -100px;
  animation: float 8s ease-in-out infinite;
}

.orb-2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, #8b5cf6 0%, transparent 70%);
  bottom: -50px;
  left: -50px;
  animation: float 10s ease-in-out infinite reverse;
}

.orb-3 {
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, #a78bfa 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: pulse 6s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-30px) rotate(5deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.5; transform: translate(-50%, -50%) scale(1.2); }
}

/* 登录卡片 */
.login-card {
  width: 400px;
  padding: 48px 40px;
  background: rgba(18, 18, 26, 0.9);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  position: relative;
  z-index: 10;
}

/* 卡片头部 */
.card-header {
  text-align: center;
  margin-bottom: 40px;
}

.logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 20px;
  color: #6366f1;
}

.logo svg {
  width: 100%;
  height: 100%;
}

.card-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 8px;
}

.card-header p {
  font-size: 14px;
  color: #8a8a8a;
  margin: 0;
}

/* 登录表单 */
.login-form {
  margin-bottom: 24px;
}

:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: none;
  padding: 4px 16px;
  transition: all 0.3s ease;
}

:deep(.el-input__wrapper:hover) {
  border-color: rgba(99, 102, 241, 0.5);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.05);
}

:deep(.el-input__inner) {
  color: #ffffff;
  height: 44px;
}

:deep(.el-input__inner::placeholder) {
  color: #5a5a5a;
}

:deep(.el-input__prefix) {
  color: #8a8a8a;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  height: 48px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.3s ease;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px -10px rgba(99, 102, 241, 0.5);
}

.login-btn:active {
  transform: translateY(0);
}

/* 卡片底部 */
.card-footer {
  text-align: center;
  font-size: 14px;
  color: #8a8a8a;
}

.card-footer a {
  color: #6366f1;
  text-decoration: none;
  margin-left: 4px;
  transition: color 0.2s;
}

.card-footer a:hover {
  color: #818cf8;
}
</style>