<script setup lang="ts">
import { ref } from 'vue'
import { ArrowLeft, CheckCircle2, Loader2, Settings2, Sparkles, AlertTriangle } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'
import api from '../utils/axios'

const loading = ref(false)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)

async function handleTestConnection() {
  if (loading.value) return

  loading.value = true
  errorMessage.value = null
  successMessage.value = null

  try {
    const response = await api.post('/llm/test-connection', {
      provider_type: 'openai_compatible',
    })
    successMessage.value = `${response.data.message}：${response.data.model}`
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || '联通测试失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="llm-page">
    <div class="llm-card glass">
      <div class="llm-header">
        <RouterLink to="/" class="back-link">
          <ArrowLeft :size="14" />
          <span>返回控制台</span>
        </RouterLink>
        <div class="title-row">
          <Settings2 :size="22" />
          <h1>模型配置</h1>
        </div>
        <p class="subtitle">当前页面使用服务端 .env 中的 OpenAI 协议兼容配置，仅用于测试大模型联通。</p>
      </div>

      <transition name="fade">
        <div v-if="errorMessage" class="status-box error">
          <AlertTriangle :size="16" />
          <span>{{ errorMessage }}</span>
        </div>
      </transition>

      <transition name="fade">
        <div v-if="successMessage" class="status-box success">
          <CheckCircle2 :size="16" />
          <span>{{ successMessage }}</span>
        </div>
      </transition>

      <div class="config-summary">
        <div class="summary-item">
          <span class="summary-label">配置来源</span>
          <span class="summary-value">服务端 .env</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">协议类型</span>
          <span class="summary-value">OpenAI 协议兼容</span>
        </div>
      </div>

      <button class="test-btn" :disabled="loading" @click="handleTestConnection">
        <Loader2 v-if="loading" :size="15" class="spinner" />
        <Sparkles v-else :size="15" />
        <span>{{ loading ? '测试中...' : '测试联通' }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.llm-page {
  min-height: calc(100vh - 120px);
  padding: 30px 0 60px;
}

.llm-card {
  max-width: 820px;
  margin: 0 auto;
  padding: 32px;
}

.llm-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #a5b4fc;
  text-decoration: none;
  width: fit-content;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-row h1 {
  margin: 0;
  font-size: 1.5rem;
}

.subtitle {
  margin: 0;
  color: #94a3b8;
  font-size: 0.92rem;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  font-size: 0.88rem;
}

.status-box.error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
  color: #fca5a5;
}

.status-box.success {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.18);
  color: #86efac;
}

.config-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

.summary-label {
  color: #64748b;
  font-size: 0.78rem;
}

.summary-value {
  color: #ffffff;
  font-weight: 700;
  font-size: 0.94rem;
}

.test-btn {
  margin-top: 20px;
  min-height: 42px;
  padding: 0 18px;
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.32);
  background: rgba(99, 102, 241, 0.12);
  color: #c4b5fd;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.test-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .config-summary {
    grid-template-columns: 1fr;
  }
}
</style>
