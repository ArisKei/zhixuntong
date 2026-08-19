<script setup lang="ts">
import { BellRing, Bot, Database, Gauge, LogOut, Menu, Radar, ShieldCheck, X } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api, apiMode } from '@/services/api'

const route = useRoute()
const navOpen = ref(false)
const showLogin = ref(!api.isAuthenticated())
const username = ref('demo')
const password = ref('demo123')
const loginLoading = ref(false)
const loginError = ref('')

const navItems = [
  { to: '/', label: '总览', icon: Gauge },
  { to: '/assistant', label: 'AI 助手', icon: Bot },
  { to: '/knowledge', label: '知识库', icon: Database },
  { to: '/intel', label: '情报监控', icon: Radar },
  { to: '/alerts', label: '预警列表', icon: BellRing },
]

const pageTitle = computed(() => String(route.meta.title ?? '总览'))

async function submitLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    await api.login(username.value.trim(), password.value)
    showLogin.value = false
  } catch (error) {
    loginError.value = error instanceof Error ? error.message : '登录失败，请稍后重试'
  } finally {
    loginLoading.value = false
  }
}

function logout() {
  api.logout()
  showLogin.value = true
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand-mark" aria-label="智讯通首页">
        <span class="brand-symbol"><ShieldCheck :size="20" stroke-width="2.2" /></span><span>智讯通</span>
      </RouterLink>
      <nav class="main-nav" :class="{ 'is-open': navOpen }" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link" @click="navOpen = false">
          <component :is="item.icon" :size="16" />{{ item.label }}
        </RouterLink>
      </nav>
      <div class="topbar-actions">
        <div class="service-status" :title="api.baseUrl"><span class="status-dot" />{{ apiMode === 'mock' ? '演示数据' : '中台在线' }}</div>
        <button class="user-button" type="button" title="退出登录" @click="logout"><span>DEMO</span><LogOut :size="15" /></button>
        <button class="mobile-menu" type="button" aria-label="切换导航" @click="navOpen = !navOpen"><X v-if="navOpen" :size="21" /><Menu v-else :size="21" /></button>
      </div>
    </header>

    <main><div class="mobile-page-title">{{ pageTitle }}</div><RouterView /></main>

    <footer class="app-footer">
      <span>ZHIXUNTONG INTELLIGENCE OS</span><span>公开情报 × 企业知识 × AI 研判</span><span>数据更新于 2026.08.19</span>
    </footer>

    <div v-if="showLogin" class="login-layer">
      <div class="login-visual">
        <div class="login-visual-inner">
          <p class="eyebrow light">ENTERPRISE INTELLIGENCE</p>
          <h1>让每条情报<br />成为可行动的判断</h1>
          <p>连接公开资讯、企业知识与 AI 工作流，把风险发现、研判与触达收束在一个界面。</p>
          <div class="login-signal"><span>01 采集</span><i /><span>02 研判</span><i /><span>03 触达</span></div>
        </div>
      </div>
      <form class="login-panel" @submit.prevent="submitLogin">
        <div class="login-brand"><span class="brand-symbol"><ShieldCheck :size="20" /></span>智讯通</div>
        <div class="login-copy"><p class="eyebrow">SECURE ACCESS</p><h2>欢迎回来</h2><p>登录企业情报工作台，继续今天的研判任务。</p></div>
        <label><span>账号</span><input v-model="username" name="username" autocomplete="username" placeholder="请输入账号" /></label>
        <label><span>密码</span><input v-model="password" type="password" name="password" autocomplete="current-password" placeholder="请输入密码" /></label>
        <p v-if="loginError" class="form-error">{{ loginError }}</p>
        <button class="primary-button login-submit" type="submit" :disabled="loginLoading">{{ loginLoading ? '正在验证…' : '进入工作台' }}</button>
        <p class="login-tip">演示账号已预填：demo / demo123</p>
      </form>
    </div>
  </div>
</template>
