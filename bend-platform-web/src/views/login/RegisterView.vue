<template>
  <div class="register-container">
    <div class="bg-decoration">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
    </div>

    <div class="register-card">
      <div class="card-header">
        <div class="logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h1>用户注册</h1>
        <p>创建商户账号</p>
      </div>

      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        class="register-form"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="确认密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item prop="phone">
          <el-input
            v-model="registerForm.phone"
            placeholder="手机号（可选）"
            :prefix-icon="Phone"
            size="large"
            clearable
          />
        </el-form-item>

        <el-form-item prop="merchantName">
          <el-input
            v-model="registerForm.merchantName"
            placeholder="商户名称"
            :prefix-icon="OfficeBuilding"
            size="large"
            clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="register-btn"
            @click="handleRegister"
          >
            {{ loading ? '注册中...' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="card-footer">
        <span>已有账号？</span>
        <router-link to="/login">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Phone, OfficeBuilding } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

/**
 * 注册视图组件
 * 提供用户注册功能，自动创建商户
 */
const router = useRouter()
const authStore = useAuthStore()

/**
 * 注册表单引用
 */
const registerFormRef = ref(null)

/**
 * 注册表单数据
 */
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  phone: '',
  merchantName: ''
})

/**
 * 自定义验证规则 - 确认密码
 */
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

/**
 * 注册表单验证规则
 */
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为2-20个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 20, message: '密码长度为4-20个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  merchantName: [
    { required: true, message: '请输入商户名称', trigger: 'blur' },
    { min: 2, max: 50, message: '商户名称长度为2-50个字符', trigger: 'blur' }
  ]
}

/**
 * 注册按钮加载状态
 */
const loading = ref(false)

/**
 * 处理注册请求
 * 1. 验证表单
 * 2. 调用注册接口
 * 3. 注册成功后跳转到首页
 */
const handleRegister = async () => {
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.register({
      username: registerForm.username,
      password: registerForm.password,
      phone: registerForm.phone,
      merchantName: registerForm.merchantName
    })
    ElMessage.success('注册成功')
    router.push('/')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0f;
  position: relative;
  overflow: hidden;
}

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

.register-card {
  width: 420px;
  padding: 48px 40px;
  background: rgba(18, 18, 26, 0.9);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  position: relative;
  z-index: 10;
}

.card-header {
  text-align: center;
  margin-bottom: 36px;
}

.logo {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  color: #6366f1;
}

.logo svg {
  width: 100%;
  height: 100%;
}

.card-header h1 {
  font-size: 22px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 8px;
}

.card-header p {
  font-size: 14px;
  color: #8a8a8a;
  margin: 0;
}

.register-form {
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

.register-btn {
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

.register-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px -10px rgba(99, 102, 241, 0.5);
}

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