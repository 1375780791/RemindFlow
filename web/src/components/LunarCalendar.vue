<script setup lang="ts">
import { ref, computed, watch } from 'vue'
// @ts-expect-error - solarlunar does not export typings correctly in ES modules
import solarLunar from 'solarlunar'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

// Props & Emits
const props = defineProps<{
  modelValue: string // Selected Solar Date in YYYY-MM-DD format
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

// Navigation state
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth() + 1) // 1-12

// Quick jumps lists
const yearsRange = computed(() => {
  const current = new Date().getFullYear()
  const list = []
  for (let y = current - 50; y <= current + 10; y++) {
    list.push(y)
  }
  return list
})

const monthsList = [
  { value: 1, label: '1月' },
  { value: 2, label: '2月' },
  { value: 3, label: '3月' },
  { value: 4, label: '4月' },
  { value: 5, label: '5月' },
  { value: 6, label: '6月' },
  { value: 7, label: '7月' },
  { value: 8, label: '8月' },
  { value: 9, label: '9月' },
  { value: 10, label: '10月' },
  { value: 11, label: '11月' },
  { value: 12, label: '12月' },
]

const weekdays = ['一', '二', '三', '四', '五', '六', '日']

// Keep calendar page in sync with prop modelValue
watch(
  () => props.modelValue,
  (newVal) => {
    if (newVal) {
      const parts = newVal.split('-').map(Number)
      const y = parts[0]
      const m = parts[1]
      const d = parts[2]
      if (y !== undefined && m !== undefined && d !== undefined && !isNaN(y) && !isNaN(m) && !isNaN(d)) {
        currentYear.value = y
        currentMonth.value = m
      }
    }
  },
  { immediate: true }
)

// Nav actions
function prevMonth() {
  if (currentMonth.value === 1) {
    currentMonth.value = 12
    currentYear.value -= 1
  } else {
    currentMonth.value -= 1
  }
}

function nextMonth() {
  if (currentMonth.value === 12) {
    currentMonth.value = 1
    currentYear.value += 1
  } else {
    currentMonth.value += 1
  }
}

// Generate calendar grid (42 cells: 6 rows x 7 cols)
const daysGrid = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value

  const firstDay = new Date(year, month - 1, 1)
  let startDayOfWeek = firstDay.getDay()
  if (startDayOfWeek === 0) startDayOfWeek = 7 // Monday is 1, Sunday is 7

  const totalDays = new Date(year, month, 0).getDate()
  const prevMonthTotalDays = new Date(year, month - 1, 0).getDate()

  const grid = []

  // 1. Padding days from previous month
  const prevPadding = startDayOfWeek - 1
  for (let i = prevPadding - 1; i >= 0; i--) {
    const d = prevMonthTotalDays - i
    const pm = month === 1 ? 12 : month - 1
    const py = month === 1 ? year - 1 : year
    grid.push(createDayItem(py, pm, d, false))
  }

  // 2. Days of the current month
  for (let d = 1; d <= totalDays; d++) {
    grid.push(createDayItem(year, month, d, true))
  }

  // 3. Padding days from next month
  const nextPadding = 42 - grid.length
  for (let d = 1; d <= nextPadding; d++) {
    const nm = month === 12 ? 1 : month + 1
    const ny = month === 12 ? year + 1 : year
    grid.push(createDayItem(ny, nm, d, false))
  }

  return grid
})

function createDayItem(y: number, m: number, d: number, isCurrentMonth: boolean) {
  const dateString = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`

  // Convert solar to lunar
  let lunarDayName = ''
  let term = ''

  try {
    const info = solarLunar.solar2lunar(y, m, d)
    term = info.term || ''
    lunarDayName = info.dayCn
    
    // Highlight Term or Festival first, then Lunar month if first day, else day name
    if (term) {
      lunarDayName = term
    } else if (info.lDay === 1) {
      lunarDayName = ((info.isLeap && !info.monthCn.startsWith('闰')) ? '闰' : '') + info.monthCn
    }
  } catch (e) {
    lunarDayName = `${d}`
  }

  const today = new Date()
  const isToday = today.getFullYear() === y && today.getMonth() + 1 === m && today.getDate() === d
  const isSelected = props.modelValue === dateString

  return {
    dateString,
    dayNumber: d,
    isCurrentMonth,
    isToday,
    isSelected,
    lunarDayName,
    term,
  }
}

function handleSelect(dateStr: string) {
  emit('update:modelValue', dateStr)
}
</script>

<template>
  <div class="calendar-wrapper">
    <!-- Header: Navigation controls + select selectors -->
    <div class="calendar-header">
      <button type="button" class="nav-arrow" @click="prevMonth">
        <ChevronLeft :size="16" />
      </button>
      
      <div class="selects-wrap">
        <select v-model="currentYear" class="calendar-select">
          <option v-for="y in yearsRange" :key="y" :value="y">{{ y }}年</option>
        </select>
        
        <select v-model="currentMonth" class="calendar-select">
          <option v-for="m in monthsList" :key="m.value" :value="m.value">{{ m.label }}</option>
        </select>
      </div>

      <button type="button" class="nav-arrow" @click="nextMonth">
        <ChevronRight :size="16" />
      </button>
    </div>

    <!-- Weekday headers -->
    <div class="weekdays-grid">
      <span v-for="w in weekdays" :key="w" class="weekday-item">{{ w }}</span>
    </div>

    <!-- Days Grid -->
    <div class="days-grid">
      <button
        v-for="day in daysGrid"
        :key="day.dateString"
        type="button"
        class="day-cell"
        :class="{
          'not-current-month': !day.isCurrentMonth,
          'is-today': day.isToday,
          'is-selected': day.isSelected,
          'has-term': !!day.term
        }"
        @click="handleSelect(day.dateString)"
      >
        <span class="solar-num">{{ day.dayNumber }}</span>
        <span class="lunar-name">{{ day.lunarDayName }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.calendar-wrapper {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  padding: 16px;
  width: 100%;
  box-sizing: border-box;
}

/* Header */
.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.nav-arrow {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #ffffff;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.nav-arrow:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #6366f1;
  border-color: rgba(99, 102, 241, 0.3);
}

.selects-wrap {
  display: flex;
  gap: 8px;
}

.calendar-select {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #ffffff;
  padding: 4px 8px;
  border-radius: 8px;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  outline: none;
  transition: all 0.3s;
}

.calendar-select:focus {
  border-color: #6366f1;
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.2);
}

/* Weekday label grid */
.weekdays-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  padding-bottom: 6px;
}

.weekday-item {
  font-size: 0.78rem;
  color: #64748b;
  font-weight: 700;
}

/* Days Cell Grid */
.days-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.day-cell {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 6px 2px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
}

.day-cell:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: translateY(-1px);
}

.not-current-month {
  opacity: 0.25;
}

.not-current-month:hover {
  opacity: 0.5;
}

.solar-num {
  font-size: 0.95rem;
  font-weight: 700;
  color: #ffffff;
}

.lunar-name {
  font-size: 0.68rem;
  color: #94a3b8;
  font-weight: 500;
}

/* Special statuses styling */
.has-term .lunar-name {
  color: #c084fc; /* purple color for solar term markers */
}

/* Today highlight */
.is-today {
  border: 1px solid rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.05);
}

.is-today .solar-num {
  color: #a5b4fc;
}

/* Selected highlight with premium gradient */
.day-cell.is-selected {
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%) !important;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  transform: scale(1.05) translateY(-1px);
}

.day-cell.is-selected .solar-num,
.day-cell.is-selected .lunar-name {
  color: #ffffff !important;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
</style>
