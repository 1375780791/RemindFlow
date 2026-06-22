<script setup lang="ts">
import {
  CalendarDays,
  Mail,
  Bell,
  Clock,
  Sparkles,
  ArrowRight,
  Heart,
  Github
} from 'lucide-vue-next'
</script>

<template>
  <div class="about-container">
    <div class="bg-glow"></div>

    <div class="about-card glass">
      <!-- Title -->
      <div class="about-header">
        <div class="logo-wrap">
          <Clock :size="32" class="logo-icon" />
        </div>
        <h1 class="about-title">关于 RemindFlow</h1>
        <p class="about-tagline">双历智醒待办 · 精准邮件投递</p>
      </div>

      <!-- Introduction -->
      <div class="section intro-section">
        <p>
          <strong>RemindFlow</strong> 是一款专为中国用户使用习惯打造的、支持“公历/农历双历循环”的现代化提醒待办系统。
          无论是亲友的农历生日、中秋除夕等传统佳节，还是阳历的例行事务、信用卡还款，您都只需设定一次，系统即可自动转换双历日期并自动为您推算未来各期的提醒时刻。
        </p>
      </div>

      <!-- Feature Grid -->
      <div class="section features-section">
        <h3 class="section-title">
          <Sparkles :size="16" class="title-icon" />
          <span>核心功能特色</span>
        </h3>
        
        <div class="features-grid">
          <div class="feature-item">
            <div class="feat-icon-wrap yellow">
              <CalendarDays :size="18" />
            </div>
            <div class="feat-content">
              <h4>公历农历智能换算</h4>
              <p>采用精准历法引擎，农历生日自动计算公历日期。支持润月及跨年日期自动回滚，确保无漏报。</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feat-icon-wrap purple">
              <Bell :size="18" />
            </div>
            <div class="feat-content">
              <h4>多天提前提醒机制</h4>
              <p>提供 0~10 天的自由提前量设置。系统会在目标日前自动开始发送提醒邮件，帮助您提前做好准备。</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feat-icon-wrap blue">
              <Mail :size="18" />
            </div>
            <div class="feat-content">
              <h4>无缝邮件通知服务</h4>
              <p>无需常驻客户端，所有提醒均通过邮件直接发送到您的邮箱。支持自定义接收邮箱地址。</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feat-icon-wrap pink">
              <Clock :size="18" />
            </div>
            <div class="feat-content">
              <h4>自由循环机制</h4>
              <p>支持单次、每日、每月、每年以及按自定义间隔天数等多种循环规则，并可在前台实时预览结果。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Tech Stack -->
      <div class="section tech-section">
        <h3 class="section-title">
          <span>技术与架构</span>
        </h3>
        <p class="tech-desc">RemindFlow 构建于现代前后端分离技术栈之上，保障流畅的用户体验与高效的数据响应：</p>
        
        <div class="tech-tags">
          <span class="tech-tag">Vue 3 (Composition API)</span>
          <span class="tech-tag">Vite & TypeScript</span>
          <span class="tech-tag">Pinia State Management</span>
          <span class="tech-tag">FastAPI (Python)</span>
          <span class="tech-tag">SQLModel & SQLite</span>
          <span class="tech-tag">solarlunar (历法引擎)</span>
        </div>
      </div>

      <!-- Footer / Credits -->
      <div class="about-footer">
        <p class="love-note">
          <span>Made with</span>
          <Heart :size="14" class="heart-icon" />
          <span>for a simpler life.</span>
        </p>
        <p class="copyright">© 2026 RemindFlow Inc. 保留所有权利。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.about-container {
  min-height: calc(100vh - 120px);
  padding: 20px 0 60px;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
}

.bg-glow {
  position: absolute;
  width: 700px;
  height: 700px;
  background: radial-gradient(circle, rgba(168, 85, 247, 0.05) 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 1;
}

.about-card {
  max-width: 760px;
  width: 100%;
  border-radius: 24px;
  padding: 40px;
  position: relative;
  z-index: 5;
  box-sizing: border-box;
}

.glass {
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

/* Header */
.about-header {
  text-align: center;
  margin-bottom: 35px;
}

.logo-wrap {
  width: 60px;
  height: 60px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  color: #6366f1;
}

.about-title {
  font-size: 1.8rem;
  font-weight: 800;
  color: #ffffff;
  margin: 0 0 6px 0;
  letter-spacing: -0.5px;
}

.about-tagline {
  font-size: 0.9rem;
  color: #a855f7;
  font-weight: 600;
  margin: 0;
  letter-spacing: 1px;
}

/* Sections */
.section {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 30px;
  margin-bottom: 30px;
}

.intro-section p {
  color: #cbd5e1;
  font-size: 0.95rem;
  line-height: 1.7;
  margin: 0;
}

.section-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 20px 0;
}

.title-icon {
  color: #c084fc;
}

/* Features Grid */
.features-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}

@media (min-width: 576px) {
  .features-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.feature-item {
  display: flex;
  gap: 14px;
}

.feat-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.feat-icon-wrap.yellow {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.25);
  color: #fbbf24;
}

.feat-icon-wrap.purple {
  background: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.25);
  color: #c084fc;
}

.feat-icon-wrap.blue {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.25);
  color: #60a5fa;
}

.feat-icon-wrap.pink {
  background: rgba(236, 72, 153, 0.1);
  border: 1px solid rgba(236, 72, 153, 0.25);
  color: #f472b6;
}

.feat-content h4 {
  font-size: 0.95rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 6px 0;
}

.feat-content p {
  font-size: 0.8rem;
  color: #94a3b8;
  line-height: 1.5;
  margin: 0;
}

/* Tech Section */
.tech-desc {
  font-size: 0.88rem;
  color: #94a3b8;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tech-tag {
  font-size: 0.76rem;
  font-weight: 600;
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 4px 10px;
  border-radius: 6px;
}

/* Footer */
.about-footer {
  text-align: center;
  border: none;
  margin: 0;
  padding: 10px 0 0 0;
}

.love-note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: #64748b;
  font-size: 0.8rem;
  font-weight: 500;
  margin: 0 0 6px 0;
}

.heart-icon {
  color: #f43f5e;
  animation: heartbeat 1.5s infinite;
}

.copyright {
  font-size: 0.74rem;
  color: #475569;
  margin: 0;
}

@keyframes heartbeat {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}
</style>
