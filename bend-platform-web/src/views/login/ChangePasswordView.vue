<template>
  <div class="change-pwd-container">
    <el-card class="change-pwd-card">
      <h2>首次登录，请修改默认密码</h2>
      <p class="hint">为保障账号安全，首次登录必须修改密码。请妥善保管新密码，平台无法找回。</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSubmit" style="width:100%">
            确认修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { userApi } from '@/api'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  newPassword: '',
  confirmPassword: ''
})

const validateConfirm = (rule, value, callback) => {
  if (value !== form.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await userApi.resetPassword(authStore.userId, form.newPassword)
    ElMessage.success('密码修改成功')
    authStore.user.needChangePassword = false
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.change-pwd-container {
  display: flex; justify-content: center; align-items: center; min-height: 100vh;
  background: #0a0a0f;
}
.change-pwd-card {
  width: 420px; background: #12121a; border: 1px solid rgba(255,255,255,0.06);
}
.change-pwd-card h2 { text-align: center; color: #fff; margin-bottom: 8px; }
.hint { text-align: center; color: #e6a23c; font-size: 13px; margin-bottom: 24px; }
</style>
