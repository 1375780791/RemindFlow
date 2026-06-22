import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../utils/axios'

interface User {
  id: number
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  // Fetch current user details
  async function fetchUser() {
    if (!token.value) return
    loading.value = true
    error.value = null
    try {
      const response = await api.get<User>('/auth/me')
      user.value = response.data
    } catch (err: any) {
      // If error occurs, logout
      logout()
      error.value = err.response?.data?.detail || '获取用户信息失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Login action
  async function login(payload: any) {
    loading.value = true
    error.value = null
    try {
      const response = await api.post<{ access_token: string }>('/auth/login', payload)
      const accessToken = response.data.access_token
      token.value = accessToken
      localStorage.setItem('token', accessToken)
      await fetchUser()
    } catch (err: any) {
      error.value = err.response?.data?.detail || '登录失败，请检查账号和密码'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Register action
  async function register(payload: any) {
    loading.value = true
    error.value = null
    try {
      await api.post<User>('/auth/register', payload)
      // Auto login after registration
      await login({ email: payload.email, password: payload.password })
    } catch (err: any) {
      error.value = err.response?.data?.detail || '注册失败，该邮箱可能已被占用'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Logout action
  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    fetchUser,
    login,
    register,
    logout,
  }
})
