<script setup lang="ts">
import { BellRing, Check, LoaderCircle, Mail, MessageSquareText, RefreshCw, Send } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import CitationItem from '@/components/CitationItem.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import { api } from '@/services/api'
import type { AlertItem, RiskLevel } from '@/types/api'

const filters: Array<{ value: RiskLevel | 'all'; label: string }> = [
  { value: 'all', label: '全部预警' }, { value: 'critical', label: '紧急' }, { value: 'high', label: '高风险' },
  { value: 'medium', label: '中风险' }, { value: 'low', label: '低风险' },
]
const alerts = ref<AlertItem[]>([])
const selected = ref<AlertItem | null>(null)
const activeFilter = ref<RiskLevel | 'all'>('all')
const loading = ref(true)
const sending = ref<'dingtalk' | 'email' | ''>('')
const success = ref('')
const error = ref('')
const filteredAlerts = computed(() => activeFilter.value === 'all' ? alerts.value : alerts.value.filter((item) => item.level === activeFilter.value))

async function load() {
  loading.value = true; error.value = ''
  try {
    const result = await api.getAlerts(1, 50)
    alerts.value = result.items; selected.value = result.items[0] ?? null
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '预警加载失败' }
  finally { loading.value = false }
}

async function send(channel: 'dingtalk' | 'email') {
  if (!selected.value) return
  sending.value = channel; error.value = ''; success.value = ''
  try {
    const result = channel === 'dingtalk' ? await api.notifyDingtalk(selected.value.alert_id) : await api.notifyEmail(selected.value.alert_id)
    success.value = result.message
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '推送失败' }
  finally { sending.value = '' }
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(load)
</script>

<template>
  <div class="page standard-page alerts-page">
    <header class="page-header split-header">
      <div><p class="eyebrow">RISK COMMAND CENTER</p><h1>预警列表</h1><p>从风险发现到业务触达，保留每一条判断依据与处理动作。</p></div>
      <div class="alert-summary"><span><strong>{{ alerts.filter((item) => item.level === 'high').length }}</strong> 高风险</span><span><strong>{{ alerts.filter((item) => item.level === 'critical').length }}</strong> 紧急</span></div>
    </header>
    <div v-if="error" class="inline-error"><span>{{ error }}</span><button type="button" @click="load"><RefreshCw :size="15" />重试</button></div>
    <div v-if="success" class="inline-success"><Check :size="16" />{{ success }}</div>

    <div class="alerts-workspace">
      <section class="alert-list-panel">
        <div class="alert-filters"><button v-for="filter in filters" :key="filter.value" type="button" :class="{ active: activeFilter === filter.value }" @click="activeFilter = filter.value">{{ filter.label }}<span>{{ filter.value === 'all' ? alerts.length : alerts.filter((item) => item.level === filter.value).length }}</span></button></div>
        <div v-if="loading" class="timeline-loading"><LoaderCircle :size="20" class="spin" />正在读取预警队列…</div>
        <div v-else class="alert-list">
          <button v-for="item in filteredAlerts" :key="item.alert_id" type="button" class="alert-list-item" :class="[{ selected: selected?.alert_id === item.alert_id }, `alert-border-${item.level}`]" @click="selected = item; success = ''">
            <div class="alert-item-head"><RiskBadge :level="item.level" /><time>{{ formatDate(item.created_at) }}</time></div><h3>{{ item.title }}</h3><p>{{ item.company }} · {{ item.summary }}</p>
          </button>
          <div v-if="!filteredAlerts.length" class="empty-list">当前等级暂无预警。</div>
        </div>
      </section>

      <aside v-if="selected" class="alert-detail-panel">
        <div class="alert-detail-head"><div><p class="eyebrow">ALERT DETAIL</p><span>{{ selected.alert_id }}</span></div><RiskBadge :level="selected.level" /></div>
        <h2>{{ selected.title }}</h2><p class="alert-company"><BellRing :size="16" />{{ selected.company }}<span>{{ formatDate(selected.created_at) }}</span></p>
        <div class="alert-analysis"><div><span>事件摘要</span><p>{{ selected.summary }}</p></div><div><span>影响分析</span><p>{{ selected.impact }}</p></div><div class="suggestion"><span>行动建议</span><p>{{ selected.suggestion }}</p></div></div>
        <div v-if="selected.citations.length" class="alert-citations"><div class="subsection-title"><span>研判依据</span><small>{{ selected.citations.length }} 条引用</small></div><CitationItem v-for="(citation, index) in selected.citations" :key="`${citation.doc}-${index}`" :citation="citation" :index="index" /></div>
        <div class="notify-box">
          <div><p class="eyebrow">NOTIFY TEAM</p><strong>推送给业务负责人</strong></div>
          <div class="notify-buttons">
            <button type="button" :disabled="Boolean(sending)" @click="send('dingtalk')"><LoaderCircle v-if="sending === 'dingtalk'" :size="17" class="spin" /><MessageSquareText v-else :size="17" />推送钉钉</button>
            <button type="button" :disabled="Boolean(sending)" @click="send('email')"><LoaderCircle v-if="sending === 'email'" :size="17" class="spin" /><Mail v-else :size="17" />发送邮件</button>
          </div><p><Send :size="14" />消息正文由服务端按固定模板生成，避免口径漂移。</p>
        </div>
      </aside>
      <aside v-else class="alert-detail-panel report-empty"><BellRing :size="28" /><strong>请选择一条预警</strong><p>这里会展示影响分析、行动建议与触达入口。</p></aside>
    </div>
  </div>
</template>
