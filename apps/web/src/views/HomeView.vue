<script setup lang="ts">
import { ArrowRight, BellRing, Bot, Check, Database, LoaderCircle, Play, RadioTower, RefreshCw, Send, X } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import CategoryTag from '@/components/CategoryTag.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import { api } from '@/services/api'
import type { AlertItem, DemoRecallOut, NewsItem } from '@/types/api'

const news = ref<NewsItem[]>([])
const alerts = ref<AlertItem[]>([])
const loading = ref(true)
const error = ref('')
const demoRunning = ref(false)
const demoResult = ref<DemoRecallOut | null>(null)
const showDemo = ref(false)

const riskCount = computed(() => alerts.value.filter((item) => ['high', 'critical'].includes(item.level)).length)
const policyCount = computed(() => news.value.filter((item) => item.category === 'policy').length)
const companyCount = computed(() => new Set(news.value.map((item) => item.company).filter(Boolean)).size)
const flowSteps = computed(() => [
  { label: '采集召回新闻', detail: demoResult.value ? `新增 ${demoResult.value.task.inserted} 条` : '等待启动', done: Boolean(demoResult.value) },
  { label: 'AI 风险研判', detail: demoResult.value ? demoResult.value.alert.level.toUpperCase() : '等待研判', done: Boolean(demoResult.value) },
  { label: '触达业务人员', detail: demoResult.value ? '钉钉 + 邮件' : '等待推送', done: Boolean(demoResult.value) },
])

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const [newsResult, alertResult] = await Promise.all([api.getNews({ days: 30, pageSize: 20 }), api.getAlerts(1, 20)])
    news.value = newsResult.items
    alerts.value = alertResult.items
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '总览数据加载失败'
  } finally {
    loading.value = false
  }
}

async function runDemo() {
  showDemo.value = true
  demoRunning.value = true
  demoResult.value = null
  error.value = ''
  try {
    demoResult.value = await api.runDemoRecall()
    await loadDashboard()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '召回闭环执行失败'
  } finally {
    demoRunning.value = false
  }
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(loadDashboard)
</script>

<template>
  <div class="page home-page">
    <section class="hero-section">
      <div class="hero-content">
        <p class="eyebrow light">NEW ENERGY VEHICLE INTELLIGENCE</p>
        <h1>智讯通</h1>
        <p class="hero-subtitle">从海量公开资讯中，找到影响下一步决策的那一条。</p>
        <div class="hero-actions">
          <button class="accent-button" type="button" :disabled="demoRunning" @click="runDemo">
            <LoaderCircle v-if="demoRunning" :size="18" class="spin" /><Play v-else :size="17" fill="currentColor" />
            {{ demoRunning ? '正在跑通闭环…' : '跑一次召回闭环' }}
          </button>
          <RouterLink to="/intel" class="text-link light-link">查看今日情报 <ArrowRight :size="17" /></RouterLink>
        </div>
      </div>
      <div class="hero-signal-card">
        <div class="signal-card-head"><span><RadioTower :size="16" /> 实时风险哨兵</span><span class="live-label">LIVE</span></div>
        <p class="signal-index">01</p><strong>电池模组召回事件</strong>
        <p>已识别为高风险，建议立即核验供应链关联。</p>
        <div class="signal-meta"><span>置信度 93%</span><span>4 分钟前</span></div>
      </div>
    </section>

    <section class="metrics-strip" aria-label="关键指标">
      <div><span>近 7 天情报</span><strong>{{ news.length || 8 }}</strong><small>条已入库</small></div>
      <div><span>高等级预警</span><strong class="metric-alert">{{ riskCount }}</strong><small>条需处理</small></div>
      <div><span>政策动态</span><strong>{{ policyCount }}</strong><small>条有更新</small></div>
      <div><span>涉及企业</span><strong>{{ companyCount }}</strong><small>家被追踪</small></div>
      <div class="pipeline-health"><span>情报链路</span><strong>ONLINE</strong><small><i /> 5 个环节正常</small></div>
    </section>

    <div v-if="error" class="inline-error"><span>{{ error }}</span><button type="button" @click="loadDashboard"><RefreshCw :size="15" />重试</button></div>

    <section class="home-grid">
      <div class="news-section">
        <div class="section-heading"><div><p class="eyebrow">LATEST SIGNALS</p><h2>最新情报</h2></div><RouterLink to="/intel" class="text-link">查看全部 <ArrowRight :size="16" /></RouterLink></div>
        <div v-if="loading" class="loading-line"><span />正在汇聚最新情报…</div>
        <div v-else class="news-list">
          <article v-for="(item, index) in news.slice(0, 5)" :key="item.id" class="news-row">
            <span class="news-number">{{ String(index + 1).padStart(2, '0') }}</span>
            <div class="news-main">
              <div class="news-tags"><CategoryTag :category="item.category" /><span>{{ item.source }}</span></div>
              <h3>{{ item.title }}</h3><p>{{ item.content }}</p>
            </div>
            <div class="news-side"><time>{{ formatDate(item.published_at) }}</time><span v-if="item.company">{{ item.company }}</span></div>
          </article>
        </div>
      </div>

      <aside class="briefing-panel">
        <div class="section-heading compact"><div><p class="eyebrow">TODAY'S BRIEF</p><h2>今日研判</h2></div></div>
        <div class="briefing-quote">“政策利好延续，但电池安全事件正在抬高供应链审查优先级。”</div>
        <div class="briefing-point"><span>01</span><div><strong>风险</strong><p>召回事件进入高风险观察清单</p></div></div>
        <div class="briefing-point"><span>02</span><div><strong>机会</strong><p>电池回收政策释放新服务需求</p></div></div>
        <div class="briefing-point"><span>03</span><div><strong>行动</strong><p>本周完成关键零部件供应商核验</p></div></div>
        <RouterLink to="/assistant" class="panel-link"><Bot :size="17" />向 AI 追问今日情报<ArrowRight :size="16" /></RouterLink>
      </aside>
    </section>

    <div v-if="showDemo" class="drawer-layer" @click.self="showDemo = false">
      <aside class="demo-drawer">
        <button class="icon-button drawer-close" type="button" aria-label="关闭" @click="showDemo = false"><X :size="20" /></button>
        <p class="eyebrow">DEMO RECALL LOOP</p><h2>召回风险闭环</h2><p class="drawer-intro">一次点击，串联采集、研判与双通道触达。</p>
        <div class="flow-track">
          <div v-for="(step, index) in flowSteps" :key="step.label" class="flow-step" :class="{ done: step.done }">
            <div class="flow-icon"><LoaderCircle v-if="demoRunning && index === 0" :size="18" class="spin" /><Check v-else-if="step.done" :size="18" /><span v-else>{{ index + 1 }}</span></div>
            <div><strong>{{ step.label }}</strong><p>{{ demoRunning && index > 0 ? '排队中' : step.detail }}</p></div>
          </div>
        </div>
        <div v-if="demoResult" class="demo-success">
          <RiskBadge :level="demoResult.alert.level" /><h3>{{ demoResult.alert.title }}</h3><p>{{ demoResult.alert.impact }}</p>
          <div class="notify-channels"><span><Send :size="15" />钉钉已推送</span><span><BellRing :size="15" />邮件已发送</span></div>
        </div>
        <div v-else-if="demoRunning" class="demo-waiting"><Database :size="22" /><span>正在写入召回种子并执行 AI 风险研判…</span></div>
      </aside>
    </div>
  </div>
</template>
