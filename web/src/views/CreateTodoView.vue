<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../utils/axios'
import LunarCalendar from '../components/LunarCalendar.vue'
import { ArrowLeft, AlertTriangle, Sparkles, Sun, Moon, Info, Calendar, Bell, Loader2, Keyboard } from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// Edit mode helper
const isEditMode = computed(() => !!route.params.id)
const todoId = computed(() => Number(route.params.id))

// Form states
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const inputMode = ref<'ai' | 'manual'>('ai')
const naturalLanguageText = ref('')
const aiParsing = ref(false)
const aiParseMessage = ref<string | null>(null)
const aiMissingFieldDetails = ref<Array<{ field: string; message: string }>>([])

// Preview states
const previewCycles = ref<any[]>([])
const previewLoading = ref(false)
const calculatedSolarLabel = ref<string | null>(null)
const currentLunarLabel = ref<string>('')

const form = reactive({
  description: '',
  recipient_email: '',
  calendar_type: 'solar', // 'solar' | 'lunar'
  task_date: '', // YYYY-MM-DD
  lunar_month: null as number | null,
  lunar_day: null as number | null,
  lunar_is_leap_month: false,
  remind_days_before: 2,
  recurrence_type: 'none', // 'none' | 'daily' | 'monthly' | 'yearly' | 'interval_days'
  interval_days: null as number | null,
  repeat_count: null as number | null,
})

// Lunar translation lookups
const lunarMonths = [
  { value: 1, label: '正月' },
  { value: 2, label: '二月' },
  { value: 3, label: '三月' },
  { value: 4, label: '四月' },
  { value: 5, label: '五月' },
  { value: 6, label: '六月' },
  { value: 7, label: '七月' },
  { value: 8, label: '八月' },
  { value: 9, label: '九月' },
  { value: 10, label: '十月' },
  { value: 11, label: '十一月' },
  { value: 12, label: '腊月' },
]

const lunarDays = Array.from({ length: 30 }, (_, i) => {
  const d = i + 1
  let label = `${d}日`
  if (d <= 10) {
    const names = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十']
    label = names[d - 1] || ''
  } else if (d < 20) {
    const names = ['十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九']
    label = names[d - 11] || ''
  } else if (d === 20) {
    label = '二十'
  } else if (d < 30) {
    const names = ['廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九']
    label = names[d - 21] || ''
  } else if (d === 30) {
    label = '三十'
  }
  return { value: d, label }
})

async function fetchTodo() {
  loading.value = true
  errorMessage.value = null
  try {
    const response = await api.get(`/todos/${todoId.value}`)
    if (response.data) {
      const todo = response.data
      form.description = todo.description
      form.recipient_email = todo.recipient_email
      form.calendar_type = todo.calendar_type
      form.task_date = todo.task_date
      form.lunar_month = todo.lunar_month
      form.lunar_day = todo.lunar_day
      form.lunar_is_leap_month = todo.lunar_is_leap_month
      form.remind_days_before = todo.remind_days_before
      form.recurrence_type = todo.recurrence_type
      form.interval_days = todo.interval_days
      form.repeat_count = todo.repeat_count
    }
  } catch (err: any) {
    console.error('Failed to load todo:', err)
    errorMessage.value = err.response?.data?.detail || '加载待办事项失败'
  } finally {
    loading.value = false
  }
}

// Set user email by default
onMounted(async () => {
  if (isEditMode.value) {
    await fetchTodo()
  } else {
    if (authStore.user) {
      form.recipient_email = authStore.user.email
    } else {
      authStore.fetchUser().then(() => {
        if (authStore.user) {
          form.recipient_email = authStore.user.email
        }
      }).catch(() => {})
    }

    // Pre-fill base solar date to today
    const today = new Date()
    const yyyy = today.getFullYear()
    const mm = String(today.getMonth() + 1).padStart(2, '0')
    const dd = String(today.getDate()).padStart(2, '0')
    form.task_date = `${yyyy}-${mm}-${dd}`
  }

  // Perform initial conversion to pre-fill Lunar month and day
  await syncLunarFromSolar()
  await updatePreview()
})

// Validation helper
const isFormValid = computed(() => {
  if (!form.description || !form.recipient_email || !form.task_date) {
    return false
  }
  if (form.description.length > 200) {
    return false
  }
  if (form.recurrence_type === 'interval_days' && (form.interval_days === null || form.interval_days <= 0)) {
    return false
  }
  if (form.calendar_type === 'lunar') {
    if (form.lunar_month === null || form.lunar_day === null) {
      return false
    }
  }
  if (form.repeat_count !== null && (form.repeat_count < 1 || form.repeat_count > 100)) {
    return false
  }
  return true
})

const recurrenceLabel = computed(() => {
  const labels: Record<string, string> = {
    none: '单次提醒',
    daily: '每天一次',
    monthly: '每月一次',
    yearly: '每年一次',
    interval_days: form.interval_days ? `每 ${form.interval_days} 天一次` : '按固定间隔天数',
  }
  return labels[form.recurrence_type] || '待识别'
})

const reminderWindowLabel = computed(() => {
  if (!form.task_date) return '待识别'
  if (Number(form.remind_days_before) === 0) {
    return `${formatDayAndMonth(form.task_date)} 当天提醒`
  }
  const targetDate = new Date(form.task_date)
  const startDate = new Date(targetDate)
  startDate.setDate(targetDate.getDate() - Number(form.remind_days_before))
  return `${formatDayAndMonth(startDate.toISOString())} 至 ${formatDayAndMonth(form.task_date)}`
})

const targetDateLabel = computed(() => {
  if (!form.task_date) return '待识别'
  const lunarLabel = currentLunarLabel.value ? ` /  ${currentLunarLabel.value}` : ''
  return `${formatDateString(form.task_date)}${lunarLabel}`
})

const aiRecognitionRows = computed(() => [
  {
    label: '提醒事项',
    value: form.description.trim() || '等待输入提醒内容',
  },
  {
    label: '历法类型',
    value: form.calendar_type === 'lunar' ? '农历' : '阳历',
  },
  {
    label: '目标日期',
    value: targetDateLabel.value,
  },
  {
    label: '提醒周期',
    value: recurrenceLabel.value,
  },
  {
    label: '提醒时间',
    value: reminderWindowLabel.value,
  },
  {
    label: '接收邮箱',
    value: form.recipient_email || '待填写',
  },
])

function applyAiParseResult(result: any) {
  if (result.description) {
    form.description = result.description
  }
  if (result.recipient_email) {
    form.recipient_email = result.recipient_email
  }
  if (result.calendar_type) {
    form.calendar_type = result.calendar_type
  }
  if (result.task_date) {
    form.task_date = result.task_date
  } else if (result.missing_fields?.includes('task_date')) {
    form.task_date = ''
  }
  if (result.calendar_type === 'lunar') {
    form.lunar_month = result.lunar_month
    form.lunar_day = result.lunar_day
    form.lunar_is_leap_month = Boolean(result.lunar_is_leap_month)
  } else if (result.calendar_type === 'solar') {
    form.lunar_month = null
    form.lunar_day = null
    form.lunar_is_leap_month = false
  }
  if (typeof result.remind_days_before === 'number') {
    form.remind_days_before = result.remind_days_before
  }
  if (result.recurrence_type) {
    form.recurrence_type = result.recurrence_type
  }
  form.interval_days = result.recurrence_type === 'interval_days'
    ? result.interval_days
    : null
  form.repeat_count = result.repeat_count
}

async function handleAiParse() {
  const text = naturalLanguageText.value.trim()
  if (!text || aiParsing.value) return

  aiParsing.value = true
  errorMessage.value = null
  successMessage.value = null
  aiParseMessage.value = null
  aiMissingFieldDetails.value = []

  try {
    const response = await api.post('/todos/parse-text', { text })
    const result = response.data.result
    applyAiParseResult(result)
    aiMissingFieldDetails.value = result.missing_field_details || []

    if (response.data.status === 'needs_clarification') {
      aiParseMessage.value = result.clarification_question || '还有信息需要补充'
    } else {
      aiParseMessage.value = '已识别并填充到表单'
    }

    await syncLunarFromSolar()
    await updatePreview()
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || 'AI 识别失败，请稍后重试或手动填写'
  } finally {
    aiParsing.value = false
  }
}

// Parse Solar Date from Lunar selectors
async function syncSolarFromLunar() {
  if (form.calendar_type !== 'lunar') return
  if (form.lunar_month === null || form.lunar_day === null) {
    calculatedSolarLabel.value = null
    return
  }
  
  try {
    const response = await api.post('/todos/convert-date', {
      calendar_type: 'lunar',
      lunar_month: Number(form.lunar_month),
      lunar_day: Number(form.lunar_day),
      lunar_is_leap_month: form.lunar_is_leap_month,
    })
    if (response.data) {
      form.task_date = response.data.solar_date
      calculatedSolarLabel.value = response.data.solar_date_str
      errorMessage.value = null
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || '无效的农历日期配置'
    calculatedSolarLabel.value = null
  }
}

// Parse Lunar Date from Solar Date picker / Calendar click
async function syncLunarFromSolar() {
  if (!form.task_date) return

  try {
    const response = await api.post('/todos/convert-date', {
      calendar_type: 'solar',
      solar_date: form.task_date,
    })
    if (response.data) {
      if (form.calendar_type === 'solar') {
        form.lunar_month = response.data.lunar_month
        form.lunar_day = response.data.lunar_day
        form.lunar_is_leap_month = response.data.lunar_is_leap_month
      } else {
        // In Lunar mode, if user selects a date on the calendar, update dropdowns if they differ
        if (
          form.lunar_month !== response.data.lunar_month ||
          form.lunar_day !== response.data.lunar_day ||
          form.lunar_is_leap_month !== response.data.lunar_is_leap_month
        ) {
          form.lunar_month = response.data.lunar_month
          form.lunar_day = response.data.lunar_day
          form.lunar_is_leap_month = response.data.lunar_is_leap_month
        }
      }
      currentLunarLabel.value = response.data.lunar_date_str.split('年')[1] || response.data.lunar_date_str
      errorMessage.value = null
    }
  } catch (err: any) {
    console.error('Failed to sync lunar date:', err)
  }
}

// Fetch upcoming cycle dates from preview endpoint
async function updatePreview() {
  if (!form.task_date) {
    previewCycles.value = []
    return
  }
  if (form.recurrence_type === 'interval_days' && (form.interval_days === null || form.interval_days <= 0)) {
    previewCycles.value = []
    return
  }

  previewLoading.value = true
  try {
    const payload: any = {
      description: form.description || '预览任务',
      recipient_email: form.recipient_email || 'preview@example.com',
      calendar_type: form.calendar_type,
      task_date: form.task_date,
      remind_days_before: Number(form.remind_days_before),
      recurrence_type: form.recurrence_type,
    }

    if (form.calendar_type === 'lunar' && form.lunar_month !== null && form.lunar_day !== null) {
      payload.lunar_month = Number(form.lunar_month)
      payload.lunar_day = Number(form.lunar_day)
      payload.lunar_is_leap_month = form.lunar_is_leap_month
    }

    if (form.recurrence_type === 'interval_days') {
      payload.interval_days = Number(form.interval_days)
    }

    if (form.recurrence_type !== 'none' && form.repeat_count !== null && form.repeat_count > 0) {
      payload.repeat_count = Number(form.repeat_count)
    }

    const response = await api.post('/todos/preview', payload)
    previewCycles.value = response.data
  } catch (err) {
    console.error('Failed to fetch preview cycles:', err)
    previewCycles.value = []
  } finally {
    previewLoading.value = false
  }
}

// Base date watcher
watch(() => form.task_date, async () => {
  await syncLunarFromSolar()
  await updatePreview()
})

// Lunar selectors watcher
watch(
  [
    () => form.lunar_month,
    () => form.lunar_day,
    () => form.lunar_is_leap_month,
  ],
  async () => {
    if (form.calendar_type === 'lunar') {
      await syncSolarFromLunar()
      await updatePreview()
    }
  }
)

// Calendar type watcher
watch(() => form.calendar_type, async (newVal) => {
  if (newVal === 'solar') {
    calculatedSolarLabel.value = null
    await syncLunarFromSolar()
  } else {
    await syncSolarFromLunar()
  }
  await updatePreview()
})

// Other fields watcher
watch(
  [
    () => form.recurrence_type,
    () => form.interval_days,
    () => form.repeat_count,
    () => form.remind_days_before,
  ],
  () => {
    updatePreview()
  }
)

// Submit form to save
async function handleSubmit() {
  if (!isFormValid.value) return
  loading.value = true
  errorMessage.value = null
  successMessage.value = null

  const payload: any = {
    description: form.description,
    recipient_email: form.recipient_email,
    calendar_type: form.calendar_type,
    task_date: form.task_date,
    remind_days_before: Number(form.remind_days_before),
    recurrence_type: form.recurrence_type,
  }

  if (form.calendar_type === 'lunar') {
    if (form.lunar_month !== null && form.lunar_day !== null) {
      payload.lunar_month = Number(form.lunar_month)
      payload.lunar_day = Number(form.lunar_day)
      payload.lunar_is_leap_month = form.lunar_is_leap_month
    }
  }

  if (form.recurrence_type === 'interval_days') {
    payload.interval_days = Number(form.interval_days)
  }

  if (form.recurrence_type !== 'none' && form.repeat_count !== null && form.repeat_count > 0) {
    payload.repeat_count = Number(form.repeat_count)
  }

  try {
    if (isEditMode.value) {
      await api.patch(`/todos/${todoId.value}`, payload)
      successMessage.value = '提醒事项修改成功！正在返回控制台...'
    } else {
      await api.post('/todos/', payload)
      successMessage.value = '提醒事项创建成功！正在返回控制台...'
    }
    setTimeout(() => {
      router.push('/')
    }, 1500)
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || (isEditMode.value ? '修改失败，请检查数据格式' : '创建失败，请检查数据格式')
  } finally {
    loading.value = false
  }
}

// Formatters
function formatDateString(str: string) {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

function formatDayAndMonth(str: string) {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
</script>

<template>
  <div class="create-container">
    <div class="bg-glow"></div>

    <div class="split-layout">
      <!-- Left side: Configuration form -->
      <div class="glass-form-card">
        <div class="form-header">
          <RouterLink to="/" class="back-link">
            <ArrowLeft :size="14" />
            <span>返回控制台</span>
          </RouterLink>
          <h1 class="page-title">{{ isEditMode ? '编辑周期提醒待办' : '新建周期提醒待办' }}</h1>
          <p class="page-subtitle">设定周期提醒规则，在公历/农历的特定日期给您发送邮件提醒。</p>
        </div>

        <transition name="fade">
          <div v-if="errorMessage" class="alert-box error">
            <AlertTriangle :size="16" class="alert-icon" />
            <span>{{ errorMessage }}</span>
          </div>
        </transition>
        <transition name="fade">
          <div v-if="successMessage" class="alert-box success">
            <Sparkles :size="16" class="alert-icon" />
            <span>{{ successMessage }}</span>
          </div>
        </transition>

        <form @submit.prevent="handleSubmit" class="main-form">
          <!-- Basic information -->
          <div class="form-section">
            <h2 class="section-title"><span class="number">1</span>基本信息</h2>
            
            <div class="input-field">
              <label>提醒事项描述</label>
              <div class="switch-container">
                <button
                  type="button"
                  class="switch-btn"
                  :class="{ active: inputMode === 'ai' }"
                  @click="inputMode = 'ai'"
                >
                  <Sparkles :size="15" />
                  <span>AI 识别</span>
                </button>
                <button
                  type="button"
                  class="switch-btn"
                  :class="{ active: inputMode === 'manual' }"
                  @click="inputMode = 'manual'"
                >
                  <Keyboard :size="15" />
                  <span>手动输入</span>
                </button>
              </div>
              <div class="text-input-wrap">
                <textarea
                  v-if="inputMode === 'ai'"
                  id="natural-language-text"
                  v-model="naturalLanguageText"
                  placeholder="例如：周五提醒我交话费，或者每月 3 号提醒我充话费，提前 2 天发邮件"
                  maxlength="500"
                  rows="4"
                  :disabled="aiParsing"
                ></textarea>
                <textarea
                  v-else
                  id="description"
                  v-model="form.description"
                  placeholder="例如：充话费、农历生日、交房租"
                  maxlength="200"
                  rows="4"
                  required
                ></textarea>
                <span class="char-count">
                  {{ inputMode === 'ai' ? naturalLanguageText.length : form.description.length }}/{{ inputMode === 'ai' ? 500 : 200 }}
                </span>
              </div>
              <button
                v-if="inputMode === 'ai'"
                type="button"
                class="ai-parse-btn"
                :disabled="!naturalLanguageText.trim() || aiParsing"
                @click="handleAiParse"
              >
                <Loader2 v-if="aiParsing" :size="15" class="spinner purple" />
                <Sparkles v-else :size="15" />
                <span>{{ aiParsing ? '识别中...' : '识别并填充' }}</span>
              </button>
              <transition name="slide-down">
                <div v-if="inputMode === 'ai'" class="ai-result-panel">
                  <div class="ai-result-header">
                    <Sparkles :size="15" />
                    <span>AI 识别结果</span>
                  </div>
                  <div v-if="aiParseMessage" class="ai-parse-message">
                    {{ aiParseMessage }}
                  </div>
                  <ul v-if="aiMissingFieldDetails.length" class="ai-missing-list">
                    <li v-for="item in aiMissingFieldDetails" :key="item.field">
                      {{ item.message }}
                    </li>
                  </ul>
                  <div class="ai-result-grid">
                    <div
                      v-for="row in aiRecognitionRows"
                      :key="row.label"
                      class="ai-result-item"
                    >
                      <span class="ai-result-label">{{ row.label }}</span>
                      <span class="ai-result-value">{{ row.value }}</span>
                    </div>
                  </div>
                </div>
              </transition>
            </div>

            <div class="input-field">
              <label for="email">接收提醒邮箱</label>
              <input
                id="email"
                type="email"
                v-model="form.recipient_email"
                placeholder="请输入接收邮件的电子邮箱"
                required
              />
            </div>
          </div>

          <!-- Date configuration -->
          <div class="form-section">
            <h2 class="section-title"><span class="number">2</span>日期与历法设置</h2>
            
            <div class="calendar-switch-group">
              <label>历法类型</label>
              <div class="switch-container">
                <button
                  type="button"
                  class="switch-btn"
                  :class="{ active: form.calendar_type === 'solar' }"
                  @click="form.calendar_type = 'solar'"
                >
                  <Sun :size="15" />
                  <span>阳历 (公历)</span>
                </button>
                <button
                  type="button"
                  class="switch-btn"
                  :class="{ active: form.calendar_type === 'lunar' }"
                  @click="form.calendar_type = 'lunar'"
                >
                  <Moon :size="15" />
                  <span>农历 (阴历)</span>
                </button>
              </div>
            </div>

            <!-- Lunar Calendar Component (Visible in both modes) -->
            <div class="input-field">
              <label>选择基准日期 (公历/农历双历对照)</label>
              <LunarCalendar v-model="form.task_date" />
            </div>

            <!-- Date confirmation labels -->
            <div class="selected-info-box" v-if="form.task_date">
              <span class="label">当前选择公历：</span>
              <span class="value">{{ formatDateString(form.task_date) }}</span>
              <span class="label split">对应农历：</span>
              <span class="value purple">{{ currentLunarLabel || '正在获取...' }}</span>
            </div>

            <!-- Optional Lunar selectors micro-adjust (Visible in Lunar mode only) -->
            <transition name="slide-down">
              <div v-if="form.calendar_type === 'lunar'" class="lunar-details-box">
                <div class="lunar-tips">
                  <Info :size="14" style="flex-shrink: 0; margin-top: 2px;" />
                  <span><strong>微调建议</strong>：您可以在上方日历中直接点选，也可以在下方微调具体的农历月日和闰月状态。</span>
                </div>
                
                <div class="lunar-selects">
                  <div class="select-field">
                    <label for="lunar-month">农历月份</label>
                    <select id="lunar-month" v-model="form.lunar_month" required>
                      <option :value="null" disabled>请选择月份</option>
                      <option v-for="m in lunarMonths" :key="m.value" :value="m.value">
                        {{ m.label }}
                      </option>
                    </select>
                  </div>

                  <div class="select-field">
                    <label for="lunar-day">农历日期</label>
                    <select id="lunar-day" v-model="form.lunar_day" required>
                      <option :value="null" disabled>请选择日期</option>
                      <option v-for="d in lunarDays" :key="d.value" :value="d.value">
                        {{ d.label }}
                      </option>
                    </select>
                  </div>
                </div>

                <div class="leap-checkbox" v-if="form.lunar_month !== null">
                  <input
                    id="leap-month"
                    type="checkbox"
                    v-model="form.lunar_is_leap_month"
                  />
                  <label for="leap-month">该月份为农历闰月</label>
                </div>
              </div>
            </transition>
          </div>

          <!-- Recurrence Rules -->
          <div class="form-section">
            <h2 class="section-title"><span class="number">3</span>提醒与循环策略</h2>

            <div class="slider-group">
              <div class="slider-header">
                <label for="remind-days-before">提前提醒天数</label>
                <span class="slider-val">提前 <strong>{{ form.remind_days_before }}</strong> 天</span>
              </div>
              <input
                id="remind-days-before"
                type="range"
                min="0"
                max="10"
                v-model="form.remind_days_before"
                class="range-slider"
              />
              <p class="slider-desc">
                {{ form.remind_days_before === 0 
                  ? '只在目标日期当天发送提醒邮件。' 
                  : `系统会在目标日提前 ${form.remind_days_before} 天开始发送邮件，直到当天（共提醒 ${form.remind_days_before + 1} 次）。` }}
              </p>
            </div>

            <div class="recurrence-grid">
              <div class="select-field">
                <label for="recurrence-type">循环机制</label>
                <select id="recurrence-type" v-model="form.recurrence_type">
                  <option value="none">单次任务 (不循环)</option>
                  <option value="daily">每天一次</option>
                  <option value="monthly">每月一次</option>
                  <option value="yearly">每年一次</option>
                  <option value="interval_days">按固定间隔天数</option>
                </select>
              </div>

              <transition name="slide-down">
                <div v-if="form.recurrence_type === 'interval_days'" class="select-field">
                  <label for="interval-days">间隔周期天数 (天)</label>
                  <input
                    id="interval-days"
                    type="number"
                    v-model="form.interval_days"
                    min="1"
                    placeholder="例如：30"
                    required
                  />
                </div>
              </transition>

              <transition name="slide-down">
                <div v-if="form.recurrence_type !== 'none'" class="select-field">
                  <label for="repeat-count">生成循环次数限制 (最高 100 次)</label>
                  <input
                    id="repeat-count"
                    type="number"
                    v-model="form.repeat_count"
                    min="1"
                    max="100"
                    placeholder="请输入 1 到 100 之间的数字 (默认 12 期)"
                  />
                  <p class="helper-text" style="color: #64748b; font-size: 0.76rem; margin-top: 2px;">
                    每个任务最大循环次数被限制为 100 次。
                  </p>
                </div>
              </transition>
            </div>
          </div>

          <button
            type="submit"
            class="create-btn"
            :disabled="!isFormValid || loading"
          >
            <span v-if="loading" class="spinner"></span>
            <span v-else>{{ isEditMode ? '保存修改' : '创建提醒事项' }}</span>
          </button>
        </form>
      </div>

      <!-- Right side: Real-time Date Preview Panel Wrapper -->
      <div class="right-column-wrapper">
        <div class="glass-preview-card">
          <h3 class="preview-title">
            <Calendar :size="18" class="preview-icon-svg" />
            <span>未来提醒日期预览</span>
          </h3>
          <p class="preview-subtitle-text">
            根据当前配置，未来各轮次的实际提醒日期如下：
          </p>

          <div v-if="previewLoading" class="preview-state loading">
            <Loader2 :size="24" class="spinner purple" />
            <p>正在计算换算日期...</p>
          </div>

          <div v-else-if="previewCycles.length === 0" class="preview-state empty">
            <Info :size="32" class="empty-icon-svg" />
            <p v-if="form.calendar_type === 'lunar' && (form.lunar_month === null || form.lunar_day === null)">
              请选择农历月日以加载预测周期
            </p>
            <p v-else>
              请选择执行日期以加载预测周期
            </p>
          </div>

          <div v-else class="timeline-container">
            <div 
              v-for="cycle in previewCycles" 
              :key="cycle.sequence" 
              class="timeline-item"
            >
              <div class="timeline-badge">
                第 {{ cycle.sequence }} 期
              </div>
              
              <div class="timeline-content">
                <div class="date-row">
                  <span class="solar-label">{{ formatDateString(cycle.solar_date) }}</span>
                  <span class="lunar-label">{{ cycle.lunar_date.split('年')[1] || cycle.lunar_date }}</span>
                </div>
                
                <div class="reminder-window" v-if="cycle.reminder_start_date !== cycle.solar_date">
                  <Bell :size="13" class="bell-icon" />
                  <span>提醒窗口：{{ formatDayAndMonth(cycle.reminder_start_date) }} 至 {{ formatDayAndMonth(cycle.solar_date) }} (每日发送)</span>
                </div>
                <div class="reminder-window" v-else>
                  <Bell :size="13" class="bell-icon" />
                  <span>仅在当天 {{ formatDayAndMonth(cycle.solar_date) }} 发送邮件提醒</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Disclaimer when preview count is capped -->
          <div v-if="previewCycles.length >= 100" class="preview-disclaimer">
            <Info :size="13" style="flex-shrink: 0; margin-top: 1px;" />
            <span>仅展示前 100 期预测，实际创建将包含全部 {{ form.repeat_count || '无限制' }} 期。</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Page layout split */
.create-container {
  min-height: calc(100vh - 120px);
  padding: 30px 0 60px;
  position: relative;
}

.bg-glow {
  position: absolute;
  width: 800px;
  height: 800px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.06) 0%, transparent 70%);
  top: 5%;
  left: 50%;
  transform: translate(-50%, 0);
  pointer-events: none;
  z-index: 1;
}

.split-layout {
  display: flex;
  flex-direction: column;
  gap: 30px;
  max-width: 1100px;
  margin: 0 auto;
  position: relative;
  z-index: 5;
}

@media (min-width: 992px) {
  .split-layout {
    flex-direction: row;
    align-items: stretch; /* Stretch columns to match height */
  }
}

/* Glass cards styles */
.glass-form-card {
  flex: 1.3;
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  padding: 35px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
  box-sizing: border-box;
}

/* Right side wrapper to absolute stretch children */
.right-column-wrapper {
  flex: 0.9;
  display: flex;
  flex-direction: column;
}

@media (min-width: 992px) {
  .right-column-wrapper {
    position: relative;
    align-self: stretch;
  }
}

.glass-preview-card {
  background: rgba(255, 255, 255, 0.01);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 24px;
  padding: 35px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  width: 100%;
}

@media (min-width: 992px) {
  .glass-preview-card {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
  }
}

/* Header */
.form-header {
  margin-bottom: 30px;
}

.back-link {
  color: #6366f1;
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
  transition: color 0.3s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.back-link:hover {
  color: #818cf8;
}

.page-title {
  font-size: 1.7rem;
  font-weight: 800;
  margin: 0 0 8px 0;
  color: #ffffff;
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 0.88rem;
  color: #94a3b8;
  margin: 0;
  line-height: 1.5;
}

/* Forms layout */
.main-form {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 25px;
}

.form-section:last-of-type {
  border: none;
  padding-bottom: 0;
}

.section-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 5px 0;
}

.section-title .number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 700;
}

/* Fields styling */
.input-field,
.select-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-field label,
.select-field label,
.calendar-switch-group label {
  font-size: 0.85rem;
  color: #94a3b8;
  font-weight: 500;
  padding-left: 2px;
}

.input-field input,
.input-field textarea,
.select-field select,
.select-field input {
  width: 100%;
  padding: 11px 15px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  color: #ffffff;
  font-size: 0.92rem;
  transition: all 0.3s;
  box-sizing: border-box;
}

.input-field textarea {
  min-height: 96px;
  resize: vertical;
  line-height: 1.55;
  padding-bottom: 30px;
}

.text-input-wrap {
  position: relative;
}

.char-count {
  position: absolute;
  right: 12px;
  bottom: 9px;
  color: #64748b;
  font-size: 0.76rem;
  pointer-events: none;
}

.ai-parse-btn {
  width: 100%;
  min-height: 40px;
  border: 1px solid rgba(99, 102, 241, 0.32);
  border-radius: 12px;
  background: rgba(99, 102, 241, 0.12);
  color: #c4b5fd;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  transition: all 0.25s;
}

.ai-parse-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.18);
  border-color: rgba(129, 140, 248, 0.52);
  color: #ffffff;
}

.ai-parse-btn:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.ai-result-panel {
  background: rgba(99, 102, 241, 0.05);
  border: 1px solid rgba(99, 102, 241, 0.16);
  border-radius: 14px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-result-header {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #c4b5fd;
  font-size: 0.86rem;
  font-weight: 700;
}

.ai-parse-message {
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.14);
  border-radius: 10px;
  padding: 9px 11px;
  font-size: 0.82rem;
  line-height: 1.45;
}

.ai-missing-list {
  margin: 0;
  padding: 9px 11px 9px 28px;
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.18);
  border-radius: 10px;
  font-size: 0.82rem;
  line-height: 1.45;
}

.ai-missing-list li + li {
  margin-top: 4px;
}

.ai-result-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

@media (min-width: 560px) {
  .ai-result-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.ai-result-item {
  min-width: 0;
  background: rgba(0, 0, 0, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  padding: 10px 12px;
}

.ai-result-label {
  display: block;
  color: #64748b;
  font-size: 0.74rem;
  margin-bottom: 5px;
}

.ai-result-value {
  display: block;
  color: #ffffff;
  font-size: 0.88rem;
  font-weight: 650;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.input-field input::placeholder,
.input-field textarea::placeholder {
  color: #475569;
}

.input-field input:focus,
.input-field textarea:focus,
.select-field select:focus,
.select-field input:focus {
  outline: none;
  border-color: #6366f1;
  background: rgba(0, 0, 0, 0.35);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
}

.helper-text {
  font-size: 0.78rem;
  color: #64748b;
  margin: 2px 0 0 2px;
  line-height: 1.4;
}

/* Switch */
.calendar-switch-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.switch-container {
  display: flex;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 4px;
}

.switch-btn {
  flex: 1;
  background: transparent;
  border: none;
  color: #94a3b8;
  padding: 9px 0;
  font-size: 0.88rem;
  font-weight: 600;
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.switch-btn.active {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.selected-info-box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 0.88rem;
  margin-top: 5px;
}

.selected-info-box .label {
  color: #64748b;
  font-weight: 500;
}

.selected-info-box .label.split {
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  padding-left: 12px;
}

.selected-info-box .value {
  color: #ffffff;
  font-weight: 700;
}

.selected-info-box .value.purple {
  color: #a855f7;
}

/* Lunar Specific fields */
.lunar-details-box {
  background: rgba(99, 102, 241, 0.03);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 16px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.lunar-tips {
  font-size: 0.78rem;
  color: #a5b4fc;
  margin: 0;
  line-height: 1.45;
  background: rgba(99, 102, 241, 0.08);
  padding: 8px 12px;
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.lunar-selects {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.leap-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 2px;
}

.leap-checkbox input[type="checkbox"] {
  width: 15px;
  height: 15px;
  accent-color: #6366f1;
  cursor: pointer;
}

.leap-checkbox label {
  font-size: 0.85rem;
  color: #94a3b8;
  cursor: pointer;
}

.calculated-solar-box {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  padding: 12px 16px;
  border-radius: 10px;
  color: #86efac;
  font-size: 0.88rem;
  margin-top: 5px;
}

.calculated-solar-box .icon {
  font-size: 1.1rem;
}

/* Warning slider */
.slider-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slider-val {
  font-size: 0.85rem;
  color: #a5b4fc;
}

.range-slider {
  width: 100%;
  height: 5px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  outline: none;
  -webkit-appearance: none;
  accent-color: #6366f1;
}

.range-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #6366f1;
  cursor: pointer;
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.5);
  transition: all 0.2s;
}

.range-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.slider-desc {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0;
  line-height: 1.4;
}

/* Recurrence Grid */
.recurrence-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 480px) {
  .recurrence-grid {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }
}

/* Submit Button */
.create-btn {
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  color: #ffffff;
  border: none;
  border-radius: 12px;
  padding: 13px 0;
  font-size: 0.98rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 10px;
}

.create-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.35);
  filter: brightness(1.08);
}

.create-btn:disabled {
  background: rgba(255, 255, 255, 0.05);
  color: #475569;
  cursor: not-allowed;
  box-shadow: none;
}

/* Alerts */
.alert-box {
  display: flex;
  align-items: center;
  padding: 11px 15px;
  border-radius: 12px;
  margin-bottom: 20px;
  font-size: 0.85rem;
  border: 1px solid;
  animation: slideIn 0.3s ease-out;
}

.alert-box.error {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}

.alert-box.success {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.2);
  color: #86efac;
}

.alert-icon {
  margin-right: 8px;
}

/* Preview Card specific styles */
.preview-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 8px 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.preview-icon {
  font-size: 1.35rem;
}

.preview-subtitle-text {
  font-size: 0.82rem;
  color: #64748b;
  margin: 0 0 25px 0;
  line-height: 1.5;
}

/* States */
.preview-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #64748b;
  flex: 1;
}

.preview-state .icon {
  font-size: 2.2rem;
  margin-bottom: 12px;
}

.preview-state p {
  font-size: 0.88rem;
  margin: 0;
  line-height: 1.4;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #ffffff;
  animation: spin 0.8s linear infinite;
}

.spinner.purple {
  border-color: rgba(99, 102, 241, 0.15);
  border-top-color: #6366f1;
  width: 26px;
  height: 26px;
  margin-bottom: 15px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Timeline Layout */
.timeline-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  max-height: 450px;
  padding-right: 5px;
  flex: 1;
  min-height: 0;
}

@media (min-width: 992px) {
  .timeline-container {
    max-height: none;
  }
}

.timeline-container::-webkit-scrollbar {
  width: 4px;
}
.timeline-container::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
.timeline-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
}

.preview-disclaimer {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.76rem;
  color: #a5b4fc;
  margin-top: 16px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.15);
  padding: 8px 12px;
  border-radius: 8px;
  line-height: 1.4;
}

.timeline-item {
  display: flex;
  gap: 15px;
  position: relative;
  padding-bottom: 5px;
}

.timeline-item::before {
  content: '';
  position: absolute;
  left: 35px;
  top: 30px;
  bottom: -20px;
  width: 1px;
  background: rgba(255, 255, 255, 0.05);
}

.timeline-item:last-child::before {
  display: none;
}

.timeline-badge {
  width: 70px;
  height: 26px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.timeline-content {
  flex: 1;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  padding: 12px 16px;
}

.date-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.solar-label {
  font-size: 0.9rem;
  font-weight: 700;
  color: #ffffff;
}

.lunar-label {
  font-size: 0.8rem;
  color: #a855f7;
  font-weight: 600;
  background: rgba(168, 85, 247, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
}

.reminder-window {
  font-size: 0.76rem;
  color: #94a3b8;
  line-height: 1.3;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.preview-icon-svg {
  color: #6366f1;
}

.empty-icon-svg {
  color: #475569;
  margin-bottom: 12px;
}

.spinner.purple {
  animation: spin 1s linear infinite;
}

/* Animations */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease-out;
  max-height: 250px;
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: 0;
  margin-bottom: 0;
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
</style>
