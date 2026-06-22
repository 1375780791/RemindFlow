<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../utils/axios'
import { useAuthStore } from '../stores/auth'
// @ts-expect-error - solarlunar does not export typings correctly in ES modules
import solarLunar from 'solarlunar'
import {
  Plus,
  Calendar as CalendarIcon,
  Mail,
  Clock,
  Trash2,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Inbox,
  Search,
  Activity,
  ArrowRight,
  Loader2,
  CalendarDays,
  Edit,
  Send
} from 'lucide-vue-next'

const authStore = useAuthStore()

// State
const todos = ref<any[]>([])
const loading = ref(true)
const errorMessage = ref<string | null>(null)

// Search & filter
const searchQuery = ref('')
const filterCalendar = ref('all') // 'all' | 'solar' | 'lunar'
const filterRecurrence = ref('all') // 'all' | 'none' | 'daily' | 'monthly' | 'yearly' | 'interval_days'

// Expanded todos (id mapping to boolean)
const expandedTodos = ref<Record<number, boolean>>({})
const todoCycles = ref<Record<number, any[]>>({})
const cyclesLoading = ref<Record<number, boolean>>({})
const emailLogs = ref<Record<number, Record<number, any[]>>>({}) // mapping todoId -> reminderCycleId -> list of log objects
const emailLogsLoading = ref<Record<number, boolean>>({})
const testEmailLoading = ref<Record<number, boolean>>({})
const testEmailCooldowns = ref<Record<number, number>>({})
const cardStatus = ref<Record<number, { type: 'success' | 'error', text: string } | null>>({})

// Delete confirmation modal state
const isDeleteModalOpen = ref(false)
const todoToDelete = ref<any | null>(null)
const deleteLoading = ref(false)

// Fetch all rules
async function fetchTodos() {
  loading.value = true
  errorMessage.value = null
  try {
    const response = await api.get('/todos/')
    todos.value = response.data
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || '无法获取待办事项列表'
  } finally {
    loading.value = false
  }
}

// Fetch cycles for a specific rule
async function fetchCycles(todoId: number) {
  cyclesLoading.value[todoId] = true
  try {
    const response = await api.get(`/todos/${todoId}/cycles`)
    todoCycles.value[todoId] = response.data
  } catch (err) {
    console.error(`Failed to fetch cycles for todo ${todoId}:`, err)
  } finally {
    cyclesLoading.value[todoId] = false
  }
}

// Fetch email sending logs for a specific rule
async function fetchEmailLogs(todoId: number) {
  emailLogsLoading.value[todoId] = true
  try {
    const response = await api.get(`/todos/${todoId}/email-logs`)
    const logs = response.data
    
    // Group logs by reminder_cycle_id
    const grouped: Record<number, any[]> = {}
    for (const log of logs) {
      if (!grouped[log.reminder_cycle_id]) {
        grouped[log.reminder_cycle_id] = []
      }
      grouped[log.reminder_cycle_id]!.push(log)
    }
    
    emailLogs.value[todoId] = grouped
  } catch (err) {
    console.error(`Failed to fetch email logs for todo ${todoId}:`, err)
  } finally {
    emailLogsLoading.value[todoId] = false
  }
}

// Toggle expanded state of a rule to show cycles
async function toggleExpand(todoId: number) {
  const isExpanded = !expandedTodos.value[todoId]
  expandedTodos.value[todoId] = isExpanded

  if (isExpanded) {
    const promises = []
    if (!todoCycles.value[todoId]) {
      promises.push(fetchCycles(todoId))
    }
    if (!emailLogs.value[todoId]) {
      promises.push(fetchEmailLogs(todoId))
    }
    if (promises.length > 0) {
      await Promise.all(promises)
    }
  }
}

// Send test email to verify mailbox connection
async function handleTestEmail(todoId: number) {
  if (testEmailLoading.value[todoId] || ((testEmailCooldowns.value[todoId] || 0) > 0)) return

  testEmailLoading.value[todoId] = true
  cardStatus.value[todoId] = null
  
  try {
    const response = await api.post(`/todos/${todoId}/test-email`)
    if (response.data && response.data.success) {
      cardStatus.value[todoId] = {
        type: 'success',
        text: '测试邮件已投递！请检查您的收件箱。'
      }
    } else {
      cardStatus.value[todoId] = {
        type: 'error',
        text: response.data?.message || '测试邮件发送失败'
      }
    }
  } catch (err: any) {
    console.error('Failed to send test email:', err)
    const detail = err.response?.data?.detail || '测试发送失败，邮箱配置有误或网络超时'
    cardStatus.value[todoId] = {
      type: 'error',
      text: detail
    }
  } finally {
    testEmailLoading.value[todoId] = false
    
    // Auto clear alert message after 4 seconds
    setTimeout(() => {
      cardStatus.value[todoId] = null
    }, 4000)

    // Trigger cooldown countdown (10 seconds)
    testEmailCooldowns.value[todoId] = 10
    const timer = setInterval(() => {
      const cooldownVal = testEmailCooldowns.value[todoId]
      if (cooldownVal !== undefined && cooldownVal > 1) {
        testEmailCooldowns.value[todoId] = cooldownVal - 1
      } else {
        delete testEmailCooldowns.value[todoId]
        clearInterval(timer)
      }
    }, 1000)
  }
}

// Open delete confirm modal
function confirmDelete(todo: any) {
  todoToDelete.value = todo
  isDeleteModalOpen.value = true
}

// Close delete confirm modal
function closeDeleteModal() {
  todoToDelete.value = null
  isDeleteModalOpen.value = false
}

// Delete reminder rule
async function handleDelete() {
  if (!todoToDelete.value) return
  deleteLoading.value = true
  try {
    await api.delete(`/todos/${todoToDelete.value.id}`)
    todos.value = todos.value.filter(t => t.id !== todoToDelete.value.id)
    closeDeleteModal()
  } catch (err: any) {
    alert(err.response?.data?.detail || '删除失败，请重试')
  } finally {
    deleteLoading.value = false
  }
}

// Filters logic
const filteredTodos = computed(() => {
  return todos.value.filter(todo => {
    // 1. Search Query
    const query = searchQuery.value.toLowerCase().trim()
    if (query) {
      const descMatch = todo.description.toLowerCase().includes(query)
      const emailMatch = todo.recipient_email.toLowerCase().includes(query)
      if (!descMatch && !emailMatch) return false
    }

    // 2. Calendar Filter
    if (filterCalendar.value !== 'all' && todo.calendar_type !== filterCalendar.value) {
      return false
    }

    // 3. Recurrence Filter
    if (filterRecurrence.value !== 'all' && todo.recurrence_type !== filterRecurrence.value) {
      return false
    }

    return true
  })
})

// Stats calculations
const stats = computed(() => {
  const activeCount = todos.value.filter(t => t.is_active).length
  
  // Find unique recipients
  const emails = new Set(todos.value.map(t => t.recipient_email))
  
  // Find closest upcoming target date
  let closestDate: string | null = null
  // We can scan through cached cycles or just display total rules count
  return {
    activeRules: activeCount,
    recipientsCount: emails.size,
    totalRules: todos.value.length
  }
})

// Format helpers
function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

function formatDateTime(dateTimeStr: string) {
  if (!dateTimeStr) return ''
  const d = new Date(dateTimeStr)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${yyyy}年${mm}月${dd}日 ${hh}:${min}:${ss}`
}

function getLunarLabelForDate(dateStr: string) {
  if (!dateStr) return ''
  try {
    const parts = dateStr.split('-').map(Number)
    const y = parts[0]
    const m = parts[1]
    const d = parts[2]
    if (y !== undefined && m !== undefined && d !== undefined && !isNaN(y) && !isNaN(m) && !isNaN(d)) {
      const info = solarLunar.solar2lunar(y, m, d)
      const monthStr = info.monthCn
      const dayStr = info.dayCn
      const leapPrefix = (info.isLeap && !monthStr.startsWith('闰')) ? '闰' : ''
      return `${leapPrefix}${monthStr}${dayStr}`
    }
  } catch (e) {
    console.error('Failed to convert date to lunar:', e)
  }
  return ''
}

function getRecurrenceLabel(type: string, interval: number | null) {
  switch (type) {
    case 'none': return '仅一次'
    case 'daily': return '每天提醒'
    case 'monthly': return '每月一次'
    case 'yearly': return '每年一次'
    case 'interval_days': return `每隔 ${interval} 天`
    default: return '未知'
  }
}

function getStatusText(status: string) {
  switch (status) {
    case 'pending': return '待执行'
    case 'completed': return '已发送'
    case 'skipped': return '已跳过'
    case 'canceled': return '已取消'
    default: return status
  }
}

onMounted(() => {
  fetchTodos()
})
</script>

<template>
  <div class="dashboard-container">
    <div class="bg-glow"></div>

    <!-- Header Section -->
    <div class="dashboard-header">
      <div class="header-info">
        <h1 class="dashboard-title">提醒事项控制台</h1>
        <p class="dashboard-subtitle">配置的提醒会在您的目标日（公历或农历）如期通过邮件发出。</p>
      </div>

      <RouterLink to="/todos/new" class="create-btn-glowing">
        <Plus :size="18" />
        <span>新建周期提醒</span>
      </RouterLink>
    </div>

    <!-- Stats Bar -->
    <div class="stats-row">
      <div class="stat-card glass">
        <div class="stat-icon-wrap blue">
          <Activity :size="20" />
        </div>
        <div class="stat-details">
          <span class="stat-value">{{ stats.activeRules }}</span>
          <span class="stat-label">运行中的规则</span>
        </div>
      </div>

      <div class="stat-card glass">
        <div class="stat-icon-wrap purple">
          <Mail :size="20" />
        </div>
        <div class="stat-details">
          <span class="stat-value">{{ stats.recipientsCount }}</span>
          <span class="stat-label">接收邮箱数</span>
        </div>
      </div>

      <div class="stat-card glass">
        <div class="stat-icon-wrap pink">
          <CalendarDays :size="20" />
        </div>
        <div class="stat-details">
          <span class="stat-value">{{ stats.totalRules }}</span>
          <span class="stat-label">总任务量</span>
        </div>
      </div>
    </div>

    <!-- Search and Filters -->
    <div class="filters-row glass">
      <div class="search-input-wrap">
        <Search :size="16" class="search-icon" />
        <input
          type="text"
          v-model="searchQuery"
          placeholder="搜索描述或邮箱..."
          class="search-input"
        />
      </div>

      <div class="selects-row">
        <div class="select-wrapper">
          <select v-model="filterCalendar" class="filter-select">
            <option value="all">历法：全部</option>
            <option value="solar">历法：阳历 (公历)</option>
            <option value="lunar">历法：农历 (阴历)</option>
          </select>
        </div>

        <div class="select-wrapper">
          <select v-model="filterRecurrence" class="filter-select">
            <option value="all">循环：全部</option>
            <option value="none">循环：仅一次</option>
            <option value="daily">循环：每天</option>
            <option value="monthly">循环：每月</option>
            <option value="yearly">循环：每年</option>
            <option value="interval_days">循环：自定义天数</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Main Content List -->
    <div class="main-list-section">
      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <Loader2 :size="40" class="spinner-svg" />
        <p>正在读取提醒列表，请稍候...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="errorMessage" class="error-state glass">
        <AlertCircle :size="36" class="error-icon" />
        <p>{{ errorMessage }}</p>
        <button @click="fetchTodos" class="retry-btn">重新加载</button>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredTodos.length === 0" class="empty-state glass">
        <Inbox :size="48" class="empty-icon" />
        <h3>没有找到匹配的提醒事项</h3>
        <p v-if="todos.length === 0">您还没有创建任何提醒事项。现在就开始设定您的第一个农历/公历生日提醒吧！</p>
        <p v-else>请尝试更换搜索关键字或历法过滤器。</p>
        
        <RouterLink v-if="todos.length === 0" to="/todos/new" class="empty-cta">
          <span>创建首个周期提醒</span>
          <ArrowRight :size="16" />
        </RouterLink>
      </div>

      <!-- Grid Cards of Rules -->
      <div v-else class="cards-grid">
        <div
          v-for="todo in filteredTodos"
          :key="todo.id"
          class="todo-card glass card-glow-devtools"
          :class="{ expanded: expandedTodos[todo.id] }"
        >
          <!-- Card Body -->
          <div class="card-inner">
            <div class="card-main-info">
              <div class="card-header-row">
                <span 
                  class="calendar-badge"
                  :class="todo.calendar_type"
                >
                  {{ todo.calendar_type === 'solar' ? '阳历' : '农历' }}
                </span>

                <span class="recurrence-badge">
                  {{ getRecurrenceLabel(todo.recurrence_type, todo.interval_days) }}
                </span>
              </div>

              <h3 class="card-title">{{ todo.description }}</h3>

              <div class="card-meta-list">
                <div class="meta-item">
                  <Mail :size="14" class="meta-icon" />
                  <span class="meta-val">{{ todo.recipient_email }}</span>
                </div>

                <div class="meta-item">
                  <CalendarIcon :size="14" class="meta-icon" />
                  <span class="meta-val">
                    起始：{{ formatDate(todo.task_date) }}
                    <strong v-if="todo.calendar_type === 'lunar'" class="lunar-val-highlight">
                      ({{ getLunarLabelForDate(todo.task_date) }})
                    </strong>
                  </span>
                </div>

                <div class="meta-item">
                  <Clock :size="14" class="meta-icon" />
                  <span class="meta-val">
                    提前 <strong>{{ todo.remind_days_before }}</strong> 天提醒邮件
                  </span>
                </div>
              </div>
            </div>

            <!-- Card-level notification -->
            <transition name="fade">
              <div v-if="cardStatus[todo.id]" class="card-status-alert" :class="cardStatus[todo.id]?.type">
                <AlertCircle v-if="cardStatus[todo.id]?.type === 'error'" :size="14" />
                <CheckCircle2 v-else :size="14" />
                <span>{{ cardStatus[todo.id]?.text }}</span>
              </div>
            </transition>

            <!-- Actions Row -->
            <div class="card-actions">
              <button
                @click="toggleExpand(todo.id)"
                class="action-btn toggle-btn"
                :class="{ active: expandedTodos[todo.id] }"
              >
                <span>{{ expandedTodos[todo.id] ? '收起周期' : '查看周期' }}</span>
                <ChevronDown v-if="!expandedTodos[todo.id]" :size="16" />
                <ChevronUp v-else :size="16" />
              </button>

              <div class="right-actions">
                <button
                  @click="handleTestEmail(todo.id)"
                  class="action-btn test-email-btn"
                  :disabled="testEmailLoading[todo.id] || ((testEmailCooldowns[todo.id] || 0) > 0)"
                >
                  <Loader2 v-if="testEmailLoading[todo.id]" :size="15" class="spinner-svg" />
                  <Send v-else :size="15" />
                  <span>
                    {{ testEmailLoading[todo.id] ? '发送中...' : (((testEmailCooldowns[todo.id] || 0) > 0) ? `${testEmailCooldowns[todo.id]}s` : '测试发送') }}
                  </span>
                </button>

                <RouterLink
                  :to="`/todos/${todo.id}/edit`"
                  class="action-btn edit-btn"
                >
                  <Edit :size="15" />
                  <span>编辑</span>
                </RouterLink>

                <button
                  @click="confirmDelete(todo)"
                  class="action-btn delete-btn"
                >
                  <Trash2 :size="15" />
                  <span>删除</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Collapsible Cycles Timeline -->
          <transition name="slide-down">
            <div v-if="expandedTodos[todo.id]" class="cycles-section">
              <div v-if="cyclesLoading[todo.id]" class="cycles-loading">
                <Loader2 :size="20" class="spinner-svg" />
                <span>正在获取提醒日程...</span>
              </div>
              
              <div v-else-if="!todoCycles[todo.id] || todoCycles[todo.id]?.length === 0" class="cycles-empty">
                <p>未发现已生成的提醒周期日程。</p>
              </div>

              <div v-else class="cycles-timeline">
                <h4 class="cycles-header">Reminder Cycles Timeline 提醒轮次</h4>
                <div class="timeline-items">
                  <div
                    v-for="cycle in todoCycles[todo.id] || []"
                    :key="cycle.id"
                    class="timeline-row"
                  >
                    <div class="timeline-marker">
                      <div class="marker-dot" :class="cycle.status"></div>
                      <div class="marker-line"></div>
                    </div>

                    <div class="timeline-box">
                      <div class="box-header">
                        <span class="cycle-seq">第 {{ cycle.sequence }} 期</span>
                        <span class="status-pill" :class="cycle.status">
                          <CheckCircle2 v-if="cycle.status === 'completed'" :size="12" />
                          <Clock v-else-if="cycle.status === 'pending'" :size="12" />
                          <AlertCircle v-else :size="12" />
                          <span>{{ getStatusText(cycle.status) }}</span>
                        </span>
                      </div>

                      <div class="box-dates">
                        <div class="target-date-row">
                          <span class="solar-d">{{ formatDate(cycle.target_date) }}</span>
                          <span class="lunar-d" v-if="todo.calendar_type === 'lunar'">
                            {{ getLunarLabelForDate(cycle.target_date) }}
                          </span>
                        </div>

                        <div class="window-row">
                          <span class="label">邮件推送时间段:</span>
                          <span class="val">
                            {{ formatDate(cycle.reminder_start_date) }} 至 {{ formatDate(cycle.reminder_end_date) }}
                          </span>
                        </div>
                      </div>

                      <!-- Email Logs for this cycle -->
                      <div v-if="emailLogs[todo.id]?.[cycle.id]" class="cycle-email-logs">
                        <div class="email-logs-title">
                          <Mail :size="12" />
                          <span>邮件发送记录 ({{ emailLogs[todo.id]?.[cycle.id]?.length || 0 }})</span>
                        </div>
                        <div
                          v-for="log in emailLogs[todo.id]?.[cycle.id] || []"
                          :key="log.id"
                          class="email-log-item"
                          :class="log.status"
                        >
                          <div class="log-meta">
                            <span class="log-status" :class="log.status">
                              {{ log.status === 'success' ? '发送成功' : '发送失败' }}
                            </span>
                            <span class="log-time">{{ formatDateTime(log.sent_at) }}</span>
                          </div>
                          <div class="log-detail">
                            <strong>主题:</strong> {{ log.subject }} 接收邮箱: {{ log.recipient_email }}
                          </div>
                          <div v-if="log.error_message" class="log-error">
                            <strong>错误信息:</strong> {{ log.error_message }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </div>

    <!-- Glass Delete Confirmation Modal -->
    <transition name="fade">
      <div v-if="isDeleteModalOpen" class="modal-overlay" @click.self="closeDeleteModal">
        <div class="modal-content glass">
          <div class="modal-icon-wrap">
            <Trash2 :size="32" class="modal-icon" />
          </div>

          <h3 class="modal-title">删除提醒规则</h3>
          <p class="modal-description">
            您确定要删除 <strong>“{{ todoToDelete?.description }}”</strong> 吗？
            <br />
            删除后，该规则以及其下所有尚未发送的提醒周期日程将被<strong>永久删除</strong>，此操作不可撤销。
          </p>

          <div class="modal-actions">
            <button
              @click="closeDeleteModal"
              class="modal-btn cancel-btn"
              :disabled="deleteLoading"
            >
              取消
            </button>

            <button
              @click="handleDelete"
              class="modal-btn confirm-btn"
              :disabled="deleteLoading"
            >
              <Loader2 v-if="deleteLoading" :size="16" class="spinner-svg" />
              <span v-else>确认删除</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.dashboard-container {
  min-height: calc(100vh - 120px);
  padding: 20px 0 60px;
  position: relative;
}

.bg-glow {
  position: absolute;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.05) 0%, transparent 70%);
  top: -5%;
  right: 5%;
  pointer-events: none;
  z-index: 1;
}

/* Header */
.dashboard-header {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 35px;
  position: relative;
  z-index: 5;
}

@media (min-width: 768px) {
  .dashboard-header {
    flex-direction: row;
    align-items: center;
  }
}

.dashboard-title {
  font-size: 1.85rem;
  font-weight: 800;
  color: #ffffff;
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.dashboard-subtitle {
  font-size: 0.92rem;
  color: #94a3b8;
  margin: 0;
}

/* Glowing Create Button (Aura style) */
.create-btn-glowing {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(20, 22, 45, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #ffffff;
  padding: 10px 20px;
  border-radius: 12px;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.92rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: visible;
  z-index: 1;
}

.create-btn-glowing::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120%;
  height: 140%;
  background: var(--gradient-devtools);
  transform: translate(-50%, -50%) scale(0.85);
  border-radius: inherit;
  filter: blur(15px);
  opacity: 0;
  transition: opacity 0.4s ease, transform 0.4s ease;
  z-index: -1;
  pointer-events: none;
}

.create-btn-glowing:hover {
  transform: translateY(-2px);
  border-color: rgba(54, 228, 218, 0.4);
  background: rgba(20, 22, 45, 0.95);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}

.create-btn-glowing:hover::before {
  opacity: 0.55;
  transform: translate(-50%, -50%) scale(1.05);
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
  margin-bottom: 30px;
  position: relative;
  z-index: 5;
}

@media (min-width: 576px) {
  .stats-row {
    grid-template-columns: repeat(3, 1fr);
  }
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-radius: 18px;
}

.stat-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon-wrap.blue {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.25);
  color: #60a5fa;
}

.stat-icon-wrap.purple {
  background: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.25);
  color: #c084fc;
}

.stat-icon-wrap.pink {
  background: rgba(236, 72, 153, 0.1);
  border: 1px solid rgba(236, 72, 153, 0.25);
  color: #f472b6;
}

.stat-details {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.45rem;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.8rem;
  color: #64748b;
  font-weight: 500;
}

/* Search and Filters Bar */
.filters-row {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 16px;
  margin-bottom: 30px;
  position: relative;
  z-index: 5;
}

@media (min-width: 768px) {
  .filters-row {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}

.search-input-wrap {
  position: relative;
  flex: 1;
  max-width: 400px;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #475569;
}

.search-input {
  width: 100%;
  padding: 10px 14px 10px 40px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  color: #ffffff;
  font-size: 0.88rem;
  transition: all 0.3s;
  box-sizing: border-box;
}

.search-input:focus {
  outline: none;
  border-color: #6366f1;
  background: rgba(0, 0, 0, 0.35);
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.1);
}

.selects-row {
  display: flex;
  gap: 12px;
}

.filter-select {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: #ffffff;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 0.88rem;
  cursor: pointer;
  outline: none;
  transition: all 0.3s;
  min-width: 140px;
}

.filter-select:focus {
  border-color: #6366f1;
}

/* Glassmorphism Styles */
.glass {
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

/* Main list wrapper */
.main-list-section {
  position: relative;
  z-index: 5;
}

/* States */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 60px 30px;
  border-radius: 24px;
}

.spinner-svg {
  animation: spin 1s linear infinite;
  color: #6366f1;
  margin-bottom: 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-state {
  border-color: rgba(239, 68, 68, 0.15);
}

.error-icon {
  color: #f87171;
  margin-bottom: 16px;
}

.retry-btn {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 8px 20px;
  border-radius: 8px;
  margin-top: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.retry-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}

.empty-icon {
  color: #475569;
  margin-bottom: 16px;
}

.empty-state h3 {
  color: #ffffff;
  margin: 0 0 10px 0;
  font-size: 1.2rem;
}

.empty-state p {
  color: #64748b;
  font-size: 0.88rem;
  max-width: 420px;
  line-height: 1.5;
  margin: 0 0 25px 0;
}

.empty-cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
  padding: 10px 22px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.3s;
}

.empty-cta:hover {
  background: rgba(99, 102, 241, 0.25);
  transform: translateX(2px);
}

/* Cards Grid */
.cards-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 25px;
}

.todo-card {
  border-radius: 20px;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.todo-card:hover {
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.3);
}

.todo-card.expanded {
  border-color: rgba(99, 102, 241, 0.25);
}

.card-inner {
  padding: 24px;
}

.card-header-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.calendar-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  text-transform: uppercase;
}

.calendar-badge.solar {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.25);
  color: #fbbf24;
}

.calendar-badge.lunar {
  background: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.25);
  color: #c084fc;
}

.recurrence-badge {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #94a3b8;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
}

.card-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 16px 0;
  line-height: 1.4;
}

.card-meta-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 0.85rem;
}

.meta-icon {
  color: #475569;
  flex-shrink: 0;
}

.lunar-val-highlight {
  color: #c084fc;
  font-weight: 700;
  margin-left: 4px;
}

/* Card Actions */
.card-actions {
  display: flex;
  justify-content: space-between;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding-top: 16px;
}

.action-btn {
  background: transparent;
  border: none;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  transition: all 0.3s;
}

.toggle-btn {
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.05);
  border: 1px solid rgba(99, 102, 241, 0.1);
}

.toggle-btn:hover,
.toggle-btn.active {
  color: #ffffff;
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.3);
}

.delete-btn {
  color: #fca5a5;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
}

.right-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.edit-btn {
  color: #c084fc;
  text-decoration: none;
}

.edit-btn:hover {
  background: rgba(192, 132, 252, 0.1);
  color: #c084fc;
}

.test-email-btn {
  color: #38bdf8;
}

.test-email-btn:hover:not(:disabled) {
  background: rgba(56, 189, 248, 0.1);
  color: #38bdf8;
}

.test-email-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  color: #64748b;
}

.card-status-alert {
  margin: 12px 24px 0 24px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.78rem;
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
}

.card-status-alert.success {
  background: rgba(52, 211, 153, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.15);
  color: #a7f3d0;
}

.card-status-alert.error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: #fecaca;
}

/* Expanded Cycles Section */
.cycles-section {
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding: 24px;
}

.cycles-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
  font-size: 0.85rem;
  padding: 20px 0;
}

.cycles-empty {
  color: #64748b;
  font-size: 0.85rem;
  text-align: center;
  padding: 10px 0;
}

.cycles-header {
  font-size: 0.78rem;
  color: #64748b;
  text-transform: uppercase;
  font-weight: 700;
  margin: 0 0 16px 0;
  letter-spacing: 0.5px;
}

.cycles-timeline {
  display: flex;
  flex-direction: column;
}

.timeline-items {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.timeline-row {
  display: flex;
  gap: 16px;
  position: relative;
}

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 14px;
}

.marker-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 6px;
  z-index: 2;
}

.marker-dot.pending {
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}

.marker-dot.completed {
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}

.marker-dot.skipped,
.marker-dot.canceled {
  background: #64748b;
}

.marker-line {
  width: 1px;
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  margin-top: 4px;
}

.timeline-row:last-child .marker-line {
  display: none;
}

.timeline-box {
  flex: 1;
  background: rgba(255, 255, 255, 0.01);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  padding: 10px 14px;
}

.box-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.cycle-seq {
  font-size: 0.8rem;
  font-weight: 700;
  color: #ffffff;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 5px;
}

.status-pill.pending {
  background: rgba(245, 158, 11, 0.08);
  color: #f59e0b;
}

.status-pill.completed {
  background: rgba(16, 185, 129, 0.08);
  color: #10b981;
}

.status-pill.skipped,
.status-pill.canceled {
  background: rgba(255, 255, 255, 0.04);
  color: #94a3b8;
}

.box-dates {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.target-date-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.solar-d {
  font-size: 0.82rem;
  font-weight: 600;
  color: #f1f2f6;
}

.lunar-d {
  font-size: 0.74rem;
  color: #c084fc;
  font-weight: 600;
  background: rgba(168, 85, 247, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
}

.window-row {
  font-size: 0.74rem;
  color: #64748b;
}

/* Glass Confirm Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal-content {
  width: 90%;
  max-width: 440px;
  border-radius: 24px;
  padding: 30px;
  text-align: center;
  animation: modalIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-sizing: border-box;
}

@keyframes modalIn {
  from {
    transform: scale(0.9) translateY(10px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-icon-wrap {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #f87171;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 800;
  color: #ffffff;
  margin: 0 0 10px 0;
}

.modal-description {
  font-size: 0.88rem;
  color: #94a3b8;
  line-height: 1.5;
  margin: 0 0 25px 0;
}

.modal-actions {
  display: flex;
  gap: 12px;
}

.modal-btn {
  flex: 1;
  border: none;
  padding: 11px 0;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.confirm-btn {
  background: #ef4444;
  color: #ffffff;
}

.confirm-btn:hover {
  background: #dc2626;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
}

/* Animations */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease-out;
  max-height: 800px;
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Email Logs inside Timeline Box */
.cycle-email-logs {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}

.email-logs-title {
  font-size: 0.76rem;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.email-log-item {
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 0.78rem;
  text-align: left;
}

.email-log-item:last-child {
  margin-bottom: 0;
}

.email-log-item.success {
  border-left: 3px solid #34d399; /* Green for success */
  background: rgba(52, 211, 153, 0.02);
}

.email-log-item.failed {
  border-left: 3px solid #f87171; /* Red for failure */
  background: rgba(248, 113, 113, 0.02);
}

.log-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.log-status {
  font-weight: 600;
  font-size: 0.74rem;
}

.log-status.success {
  color: #34d399;
}

.log-status.failed {
  color: #f87171;
}

.log-time {
  color: #64748b;
  font-size: 0.72rem;
}

.log-detail {
  color: #cbd5e1;
  word-break: break-all;
}

.log-error {
  margin-top: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.1);
  border-radius: 6px;
  color: #fca5a5;
  font-size: 0.74rem;
  font-family: monospace;
  word-break: break-all;
}
</style>
