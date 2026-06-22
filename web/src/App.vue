<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { Clock, LogOut, Key } from 'lucide-vue-next'
import api from './utils/axios'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isLoginPage = computed(() => route.name === 'login')

// Restore user authentication session on page load
onMounted(async () => {
  if (authStore.token) {
    try {
      await authStore.fetchUser()
    } catch (e) {
      console.error('自动登录失败，凭证可能已过期:', e)
      router.push({ name: 'login' })
    }
  }
})

// Handle user logout
function handleLogout() {
  authStore.logout()
  router.push({ name: 'login' })
}

// Change Password Modal States
const isChangePasswordModalOpen = ref(false)
const oldPassword = ref('')
const newPassword = ref('')
const confirmNewPassword = ref('')
const changePasswordLoading = ref(false)
const changePasswordError = ref<string | null>(null)
const changePasswordSuccess = ref<string | null>(null)

const isChangePasswordFormValid = computed(() => {
  return (
    oldPassword.value.length > 0 &&
    newPassword.value.length >= 8 &&
    newPassword.value === confirmNewPassword.value
  )
})

function openChangePasswordModal() {
  console.log('openChangePasswordModal called, setting isChangePasswordModalOpen = true')
  isChangePasswordModalOpen.value = true
  oldPassword.value = ''
  newPassword.value = ''
  confirmNewPassword.value = ''
  changePasswordError.value = null
  changePasswordSuccess.value = null
}

function closeChangePasswordModal() {
  console.log('closeChangePasswordModal called, setting isChangePasswordModalOpen = false')
  isChangePasswordModalOpen.value = false
  oldPassword.value = ''
  newPassword.value = ''
  confirmNewPassword.value = ''
  changePasswordError.value = null
  changePasswordSuccess.value = null
}

// Send change password request via API
async function submitChangePassword() {
  console.log('submitChangePassword called')
  if (!isChangePasswordFormValid.value || changePasswordLoading.value) {
    console.warn('Form validation failed or already loading')
    return
  }

  changePasswordLoading.value = true
  changePasswordError.value = null
  changePasswordSuccess.value = null

  try {
    const response = await api.post('/auth/change-password', {
      old_password: oldPassword.value,
      new_password: newPassword.value
    })
    
    console.log('Change password API success:', response.data)
    changePasswordSuccess.value = response.data?.message || '密码修改成功！'
    
    // Auto close modal after 1.5 seconds
    setTimeout(() => {
      closeChangePasswordModal()
    }, 1500)
  } catch (err: any) {
    console.error('Failed to change password:', err)
    changePasswordError.value = err.response?.data?.detail || '密码修改失败，请重试'
  } finally {
    changePasswordLoading.value = false
  }
}
</script>

<template>
  <div class="app-wrapper">
    <!-- Header: Hidden on Login page, visible elsewhere when authenticated -->
    <header v-if="!isLoginPage && authStore.isAuthenticated" class="main-header">
      <div class="header-container">
        <div class="brand">
          <Clock class="brand-icon" :size="22" />
          <span class="logo-text">RemindFlow</span>
        </div>

        <nav class="nav-links">
          <RouterLink to="/" class="nav-item">控制台</RouterLink>
          <RouterLink to="/todos/new" class="nav-item">+ 新建提醒</RouterLink>
          <RouterLink to="/llm-settings" class="nav-item">模型配置</RouterLink>
          <RouterLink to="/about" class="nav-item">关于</RouterLink>
        </nav>

        <div class="user-profile">
          <span class="user-email" v-if="authStore.user">{{ authStore.user.email }}</span>
          <button class="change-password-btn" @click="openChangePasswordModal">
            <Key :size="14" />
            <span>修改密码</span>
          </button>
          <button class="logout-btn" @click="handleLogout">
            <LogOut :size="14" />
            <span>退出</span>
          </button>
        </div>
      </div>
    </header>

    <main class="main-content" :class="{ 'no-padding': isLoginPage }">
      <RouterView />
    </main>

    <!-- Change Password Modal -->
    <Teleport to="body">
      <transition name="fade" appear>
        <div v-if="isChangePasswordModalOpen" class="modal-backdrop" @click.self="closeChangePasswordModal">
          <div class="modal-container glass">
            <div class="modal-header">
              <Key class="modal-header-icon" :size="20" />
              <h3>修改密码</h3>
            </div>
            
            <div class="modal-body">
              <transition name="fade">
                <div v-if="changePasswordError" class="modal-alert error">
                  <span>{{ changePasswordError }}</span>
                </div>
              </transition>
              <transition name="fade">
                <div v-if="changePasswordSuccess" class="modal-alert success">
                  <span>{{ changePasswordSuccess }}</span>
                </div>
              </transition>

              <form @submit.prevent="submitChangePassword" class="modal-form">
                <div class="modal-input-field">
                  <label for="old-password">当前密码</label>
                  <input
                    id="old-password"
                    type="password"
                    v-model="oldPassword"
                    required
                    placeholder="请输入当前密码"
                    :disabled="changePasswordLoading"
                  />
                </div>

                <div class="modal-input-field">
                  <label for="new-password">新密码 (最少 8 位)</label>
                  <input
                    id="new-password"
                    type="password"
                    v-model="newPassword"
                    required
                    placeholder="请输入新密码 (最少 8 位)"
                    :disabled="changePasswordLoading"
                  />
                </div>

                <div class="modal-input-field">
                  <label for="confirm-new-password">确认新密码</label>
                  <input
                    id="confirm-new-password"
                    type="password"
                    v-model="confirmNewPassword"
                    required
                    placeholder="请再次输入新密码"
                    :disabled="changePasswordLoading"
                  />
                </div>

                <div class="modal-actions">
                  <button
                    type="button"
                    class="modal-btn cancel-btn"
                    @click="closeChangePasswordModal"
                    :disabled="changePasswordLoading"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    class="modal-btn submit-btn"
                    :disabled="changePasswordLoading || !isChangePasswordFormValid"
                  >
                    <span v-if="changePasswordLoading" class="spinner"></span>
                    <span v-else>确认修改</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style>
/* Global resets for body to ensure it spans full screen and has nice dark background */
body {
  margin: 0;
  padding: 0;
  background-color: #0b0c15;
  color: #f1f2f6;
  min-height: 100vh;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Global styles for Teleported Change Password Modal */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100000;
}

.modal-container.glass {
  background: rgba(17, 19, 40, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  width: 90%;
  max-width: 440px;
  padding: 30px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  box-sizing: border-box;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}

.modal-header-icon {
  color: #6366f1;
}

.modal-header h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0;
  color: #ffffff;
}

.modal-alert {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 0.85rem;
  margin-bottom: 18px;
}

.modal-alert.error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #fca5a5;
  text-align: left;
}

.modal-alert.success {
  background: rgba(52, 211, 153, 0.1);
  border: 1px solid rgba(52, 211, 153, 0.2);
  color: #a7f3d0;
  text-align: left;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.modal-input-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
}

.modal-input-field label {
  font-size: 0.82rem;
  color: #94a3b8;
  font-weight: 500;
}

.modal-input-field input {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px 14px;
  color: #ffffff;
  font-size: 0.9rem;
  outline: none;
  transition: all 0.3s;
}

.modal-input-field input:focus {
  border-color: rgba(99, 102, 241, 0.5);
  background: rgba(99, 102, 241, 0.05);
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.15);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 10px;
}

.modal-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.submit-btn {
  background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
  color: #ffffff;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Spinner Loader */
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<style scoped>
.app-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* Premium Dark Mode Nav Bar */
.main-header {
  background: rgba(15, 17, 32, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  color: #6366f1;
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 800;
  background: var(--gradient-devtools);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-links {
  display: flex;
  gap: 8px;
}

.nav-item {
  color: #94a3b8;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.3s;
}

.nav-item:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.04);
}

/* Active Link State */
.nav-item.router-link-active {
  color: #ffffff;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-email {
  color: #94a3b8;
  font-size: 0.9rem;
}

.logout-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f1f2f6;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 500;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}

/* Main Content Area */
.main-content {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 30px 24px;
  box-sizing: border-box;
}

.main-content.no-padding {
  max-width: none;
  padding: 0;
  margin: 0;
}

.change-password-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f1f2f6;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 500;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.change-password-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
}


</style>
