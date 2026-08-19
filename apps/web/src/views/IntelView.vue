<script setup lang="ts">
import { ArrowRight, CalendarDays, Check, FileText, LoaderCircle, Mail, RefreshCw, Search, Sparkles } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import CategoryTag from '@/components/CategoryTag.vue'
import { api } from '@/services/api'
import type { NewsCategory, NewsItem, ReportItem } from '@/types/api'

const categories: Array<{ value: NewsCategory | 'all'; label: string }> = [
  { value: 'all', label: '全部' }, { value: 'policy', label: '政策' }, { value: 'company', label: '企业' },
  { value: 'market', label: '市场' }, { value: 'tech', label: '技术' }, { value: 'risk', label: '风险' },
]
const news = ref<NewsItem[]>([])
const activeCategory = ref<NewsCategory | 'all'>('all')
const searchQuery = ref('')
const selectedNews = ref<NewsItem | null>(null)
const report = ref<ReportItem | null>(null)
const loading = ref(true)
const generating = ref(false)
const sendingReport = ref(false)
const notifyMessage = ref('')
const error = ref('')

const filteredNews = computed(() => news.value.filter((item) => {
  const matchesCategory = activeCategory.value === 'all' || item.category === activeCategory.value
  const keyword = searchQuery.value.trim().toLowerCase()
  return matchesCategory && (!keyword || `${item.title}${item.content}${item.company ?? ''}`.toLowerCase().includes(keyword))
}))
const reportSections = computed(() => {
  if (!report.value) return []
  return report.value.content_md.split(/^##\s+/m).slice(1).map((section) => {
    const [heading, ...body] = section.trim().split('\n')
    return { heading, body: body.join('\n').trim() }
  }).filter((section) => section.heading)
})

async function load() {
  loading.value = true; error.value = ''
  try {
    const [newsResult, reportsResult] = await Promise.all([api.getNews({ days: 30, pageSize: 50 }), api.getReports(1, 20)])
    news.value = newsResult.items
    report.value = reportsResult.items[0] ?? null
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '情报数据加载失败'
  } finally { loading.value = false }
}

async function generateReport() {
  generating.value = true; error.value = ''; notifyMessage.value = ''
  try { report.value = await api.analyze(7) }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '周报生成失败' }
  finally { generating.value = false }
}

async function sendReport() {
  if (!report.value) return
  sendingReport.value = true; error.value = ''; notifyMessage.value = ''
  try {
    const result = await api.notifyDailyReport(report.value.id)
    notifyMessage.value = result.message
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '日报邮件发送失败'
  } finally { sendingReport.value = false }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(load)
</script>

<template>
  <div class="page standard-page intel-page">
    <header class="page-header split-header">
      <div><p class="eyebrow">INTELLIGENCE MONITOR</p><h1>情报监控</h1><p>按时间与主题浏览行业信号，把分散新闻收束成结构化周报。</p></div>
      <button class="primary-button" type="button" :disabled="generating" @click="generateReport"><LoaderCircle v-if="generating" :size="17" class="spin" /><Sparkles v-else :size="17" />{{ generating ? '正在生成…' : '生成近 7 天周报' }}</button>
    </header>
    <div v-if="error" class="inline-error"><span>{{ error }}</span><button type="button" @click="load"><RefreshCw :size="15" />重试</button></div>

    <div class="intel-workspace">
      <section class="timeline-panel">
        <div class="intel-toolbar">
          <div class="category-tabs"><button v-for="category in categories" :key="category.value" type="button" :class="{ active: activeCategory === category.value }" @click="activeCategory = category.value">{{ category.label }}</button></div>
          <label class="compact-search"><Search :size="17" /><input v-model="searchQuery" aria-label="搜索新闻" placeholder="搜索标题或企业" /></label>
        </div>
        <div v-if="loading" class="timeline-loading"><LoaderCircle :size="20" class="spin" />正在同步情报时间线…</div>
        <div v-else class="intel-timeline">
          <button v-for="item in filteredNews" :key="item.id" type="button" class="timeline-item" :class="{ selected: selectedNews?.id === item.id }" @click="selectedNews = item">
            <time>{{ formatDate(item.published_at) }}</time><span class="timeline-dot" :class="`dot-${item.category}`" />
            <div><div class="news-tags"><CategoryTag :category="item.category" /><span>{{ item.source }}</span></div><h3>{{ item.title }}</h3><p>{{ item.content }}</p></div><ArrowRight :size="17" class="timeline-arrow" />
          </button>
          <div v-if="!filteredNews.length" class="empty-list">没有匹配当前筛选条件的情报。</div>
        </div>
      </section>

      <aside class="report-panel">
        <div v-if="selectedNews" class="news-detail">
          <div class="report-panel-head"><span>情报详情</span><button type="button" @click="selectedNews = null">查看周报</button></div>
          <CategoryTag :category="selectedNews.category" /><h2>{{ selectedNews.title }}</h2>
          <div class="detail-meta"><span>{{ selectedNews.source }}</span><span>{{ formatDate(selectedNews.published_at) }}</span><span v-if="selectedNews.company">{{ selectedNews.company }}</span></div>
          <p>{{ selectedNews.content }}</p><div class="keyword-list"><span v-for="keyword in selectedNews.keywords" :key="keyword"># {{ keyword }}</span></div>
          <a :href="selectedNews.source_url" target="_blank" rel="noreferrer" class="panel-link">查看原始来源<ArrowRight :size="16" /></a>
        </div>
        <div v-else-if="report" class="report-content">
          <div class="report-panel-head"><span><FileText :size="16" />AI 行业周报</span><small><CalendarDays :size="14" />近 {{ report.range_days }} 天</small></div>
          <h2>{{ report.title }}</h2><p class="report-time">生成于 {{ report.created_at ? formatDate(report.created_at) : '刚刚' }}</p>
          <div class="report-actions">
            <button type="button" :disabled="sendingReport" @click="sendReport"><LoaderCircle v-if="sendingReport" :size="15" class="spin" /><Mail v-else :size="15" />{{ sendingReport ? '发送中…' : '发送日报邮件' }}</button>
            <span v-if="notifyMessage"><Check :size="14" />{{ notifyMessage }}</span>
          </div>
          <div class="report-sections"><article v-for="(section, index) in reportSections" :key="section.heading"><span>{{ String(index + 1).padStart(2, '0') }}</span><div><h3>{{ section.heading }}</h3><p>{{ section.body }}</p></div></article></div>
        </div>
        <div v-else class="report-empty"><FileText :size="28" /><strong>还没有行业周报</strong><p>点击“生成近 7 天周报”，让 AI 汇总六个固定主题。</p></div>
      </aside>
    </div>
  </div>
</template>
