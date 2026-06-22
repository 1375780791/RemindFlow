<script setup lang="ts">
import { ref, reactive, computed, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { Mail, Lock, Shield, AlertTriangle, Sparkles, Loader2, Key } from 'lucide-vue-next'
import api from '../utils/axios'

const router = useRouter()
const authStore = useAuthStore()

// View state
const isLoginMode = ref(true)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)

// Form data
const form = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  verificationCode: '',
})

// Validation
const isEmailValid = computed(() => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(form.email)
})

const isFormValid = computed(() => {
  if (isLoginMode.value) {
    return isEmailValid.value && form.password.length >= 8
  } else {
    return (
      isEmailValid.value &&
      form.password.length >= 8 &&
      form.password === form.confirmPassword &&
      form.verificationCode.length === 8
    )
  }
})

// Verification code sending state
const sendCodeLoading = ref(false)
const sendCodeCooldown = ref(0)
const sendCodeTimer = ref<any>(null)

async function handleSendVerificationCode() {
  if (!isEmailValid.value || sendCodeLoading.value || sendCodeCooldown.value > 0) return

  sendCodeLoading.value = true
  errorMessage.value = null
  successMessage.value = null

  try {
    await api.post('/auth/send-verification-code', { email: form.email })
    successMessage.value = '验证码已发送至您的邮箱，请注意查收！'
    
    // Start countdown timer (60s)
    sendCodeCooldown.value = 60
    sendCodeTimer.value = setInterval(() => {
      if (sendCodeCooldown.value > 1) {
        sendCodeCooldown.value--
      } else {
        sendCodeCooldown.value = 0
        if (sendCodeTimer.value) clearInterval(sendCodeTimer.value)
      }
    }, 1000)
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || '发送验证码失败，请重试'
  } finally {
    sendCodeLoading.value = false
  }
}

// Toggle mode
function toggleMode() {
  isLoginMode.value = !isLoginMode.value
  errorMessage.value = null
  successMessage.value = null
  form.password = ''
  form.confirmPassword = ''
  form.verificationCode = ''
  sendCodeCooldown.value = 0
  if (sendCodeTimer.value) {
    clearInterval(sendCodeTimer.value)
  }
}

// Submit handler
async function handleSubmit() {
  if (!isFormValid.value) return
  errorMessage.value = null
  successMessage.value = null

  try {
    if (isLoginMode.value) {
      await authStore.login({
        email: form.email,
        password: form.password,
      })
      successMessage.value = '登录成功！正在跳转...'
      setTimeout(() => {
        router.push('/')
      }, 1000)
    } else {
      await authStore.register({
        email: form.email,
        password: form.password,
        verification_code: form.verificationCode,
      })
      successMessage.value = '注册并登录成功！正在跳转...'
      setTimeout(() => {
        router.push('/')
      }, 1000)
    }
  } catch (err: any) {
    errorMessage.value = authStore.error || '操作失败，请重试'
  }
}

onBeforeUnmount(() => {
  if (sendCodeTimer.value) {
    clearInterval(sendCodeTimer.value)
  }
})
</script>

<template>
  <div class="login-container">
    <!-- Animated background elements -->
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

    <div class="glass-card card-glow-devtools">
      <div class="card-header">
        <h1 class="brand-title">RemindFlow</h1>
        <p class="brand-subtitle">轻量级个人周期提醒系统</p>
      </div>

      <!-- Mode Toggle Switch -->
      <div class="toggle-container">
        <div 
          class="toggle-slider" 
          :class="{ 'slide-right': !isLoginMode }"
        ></div>
        <button 
          class="toggle-btn" 
          :class="{ active: isLoginMode }" 
          @click="isLoginMode = true"
        >
          登录
        </button>
        <button 
          class="toggle-btn" 
          :class="{ active: !isLoginMode }" 
          @click="isLoginMode = false"
        >
          注册
        </button>
      </div>

      <!-- Notification messages -->
      <transition name="fade">
        <div class="alert-box error" v-if="errorMessage">
          <AlertTriangle class="alert-icon-svg" :size="16" />
          <span class="message">{{ errorMessage }}</span>
        </div>
      </transition>
      <transition name="fade">
        <div class="alert-box success" v-if="successMessage">
          <Sparkles class="alert-icon-svg" :size="16" />
          <span class="message">{{ successMessage }}</span>
        </div>
      </transition>

      <!-- Form -->
      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="input-group">
          <label for="email">电子邮箱</label>
          <div class="input-wrapper">
            <Mail class="input-icon-svg" :size="18" />
            <input
              id="email"
              type="email"
              v-model="form.email"
              placeholder="请输入您的邮箱"
              required
              autocomplete="email"
            />
          </div>
        </div>

        <div class="input-group">
          <label for="password">密码</label>
          <div class="input-wrapper">
            <Lock class="input-icon-svg" :size="18" />
            <input
              id="password"
              type="password"
              v-model="form.password"
              placeholder="请输入密码（最少8位）"
              required
              autocomplete="current-password"
            />
          </div>
        </div>

        <transition name="slide-fade">
          <div v-if="!isLoginMode" class="register-only-fields">
            <div class="input-group">
              <label for="confirm-password">确认密码</label>
              <div class="input-wrapper">
                <Shield class="input-icon-svg" :size="18" />
                <input
                  id="confirm-password"
                  type="password"
                  v-model="form.confirmPassword"
                  placeholder="请再次输入密码"
                  required
                  autocomplete="new-password"
                />
              </div>
            </div>

            <div class="input-group">
              <label for="verification-code">邮箱验证码</label>
              <div class="input-wrapper">
                <Key class="input-icon-svg" :size="18" />
                <input
                  id="verification-code"
                  type="text"
                  v-model="form.verificationCode"
                  placeholder="请输入6位验证码"
                  required
                  maxlength="6"
                  class="verification-input"
                />
                <button
                  type="button"
                  class="send-code-btn"
                  :disabled="!isEmailValid || sendCodeLoading || sendCodeCooldown > 0"
                  @click="handleSendVerificationCode"
                >
                  <Loader2 v-if="sendCodeLoading" class="spinner animate-spin" :size="14" />
                  <span v-else-if="sendCodeCooldown > 0">{{ sendCodeCooldown }}s</span>
                  <span v-else>获取验证码</span>
                </button>
              </div>
            </div>
          </div>
        </transition>

        <button 
          type="submit" 
          class="submit-btn" 
          :disabled="!isFormValid || authStore.loading"
        >
          <Loader2 v-if="authStore.loading" class="spinner animate-spin" :size="20" />
          <span v-else>{{ isLoginMode ? '登 录' : '注 册' }}</span>
        </button>
      </form>

      <div class="card-footer">
        <p v-if="isLoginMode" class="footer-tip">
          没有账号？<a href="#" @click.prevent="toggleMode">立即注册</a>
        </p>
        <p v-else class="footer-tip">
          已有账号？<a href="#" @click.prevent="toggleMode">返回登录</a>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Full screen dark theme container */
.login-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: #0b0c15;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #f1f2f6;
  z-index: 9999;
}

/* Glowing background blobs */
.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
  mix-blend-mode: screen;
  pointer-events: none;
  animation: float 20s infinite ease-in-out alternate;
}

.orb-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, #6366f1 0%, transparent 80%);
  top: -10%;
  left: 10%;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #a855f7 0%, transparent 80%);
  bottom: -15%;
  right: 10%;
  animation-delay: -5s;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, #ec4899 0%, transparent 80%);
  top: 40%;
  right: 35%;
  animation-delay: -10s;
}

@keyframes float {
  0% {
    transform: translate(0, 0) scale(1);
  }
  100% {
    transform: translate(50px, 30px) scale(1.1);
  }
}

/* Frosted glass morphic card */
.glass-card {
  width: 100%;
  max-width: 440px;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  padding: 40px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

/* Header styles with metallic logo gradient */
.card-header {
  text-align: center;
  margin-bottom: 30px;
}

.brand-title {
  font-size: 2.5rem;
  font-weight: 800;
  margin: 0;
  background: var(--gradient-devtools);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -1px;
  text-shadow: 0 10px 30px rgba(54, 228, 218, 0.15);
}

.brand-subtitle {
  font-size: 0.9rem;
  color: #94a3b8;
  margin: 8px 0 0 0;
}

/* Custom dual state sliding tab switch */
.toggle-container {
  display: flex;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 12px;
  padding: 4px;
  position: relative;
  margin-bottom: 25px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.toggle-slider {
  position: absolute;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: var(--gradient-devtools);
  border-radius: 9px;
  top: 4px;
  left: 4px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 15px rgba(54, 228, 218, 0.3);
}

.toggle-slider.slide-right {
  transform: translateX(100%);
}

.toggle-btn {
  flex: 1;
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 0.95rem;
  font-weight: 600;
  padding: 10px 0;
  cursor: pointer;
  z-index: 2;
  transition: color 0.3s;
}

.toggle-btn.active {
  color: #ffffff;
}

/* Alert notifications */
.alert-box {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 20px;
  font-size: 0.88rem;
  border: 1px solid;
  animation: slideIn 0.3s ease-out;
}

.alert-box.error {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.25);
  color: #fca5a5;
}

.alert-box.success {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.25);
  color: #86efac;
}

.alert-icon-svg {
  margin-right: 10px;
  flex-shrink: 0;
}

/* Forms and inputs styling */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  font-size: 0.85rem;
  color: #94a3b8;
  font-weight: 500;
  padding-left: 2px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon-svg {
  position: absolute;
  left: 14px;
  color: #64748b;
  pointer-events: none;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

.input-wrapper input {
  width: 100%;
  padding: 12px 16px 12px 42px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  color: #ffffff;
  font-size: 0.95rem;
  transition: all 0.3s;
  box-sizing: border-box;
}

.input-wrapper input::placeholder {
  color: #475569;
}

.input-wrapper input:focus {
  outline: none;
  border-color: #6366f1;
  background: rgba(0, 0, 0, 0.3);
  box-shadow: 0 0 15px rgba(99, 102, 241, 0.15);
}

/* Submit button with smooth dynamic states */
.submit-btn {
  background: rgba(20, 22, 45, 0.9);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 14px 0;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 10px;
  position: relative;
  overflow: visible;
  z-index: 1;
}

.submit-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 115%;
  height: 130%;
  background: var(--gradient-devtools);
  transform: translate(-50%, -50%) scale(0.9);
  border-radius: inherit;
  filter: blur(15px);
  opacity: 0;
  transition: opacity 0.4s ease, transform 0.4s ease;
  z-index: -1;
  pointer-events: none;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(54, 228, 218, 0.4);
  background: rgba(20, 22, 45, 0.95);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}

.submit-btn:hover:not(:disabled)::before {
  opacity: 0.55;
  transform: translate(-50%, -50%) scale(1.05);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.submit-btn:disabled {
  background: rgba(255, 255, 255, 0.08);
  color: #64748b;
  cursor: not-allowed;
  box-shadow: none;
}

/* Loading spinner in button */
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #ffffff;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Footer elements */
.card-footer {
  margin-top: 30px;
  text-align: center;
}

.footer-tip {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 0;
}

.footer-tip a {
  color: #6366f1;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.3s;
}

.footer-tip a:hover {
  color: #818cf8;
  text-decoration: underline;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

@keyframes slideIn {
  from {
    transform: translateY(-10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.register-only-fields {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.verification-input {
  padding-right: 120px !important;
}

.send-code-btn {
  position: absolute;
  right: 6px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 34px;
}

.send-code-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.25);
  border-color: rgba(99, 102, 241, 0.45);
  color: #ffffff;
}

.send-code-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.05);
  color: #64748b;
}
</style>
