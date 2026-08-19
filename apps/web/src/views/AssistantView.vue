<script setup lang="ts">
import { ArrowUp, Bot, CheckCircle2, LoaderCircle, Sparkles } from 'lucide-vue-next'
import { ref } from 'vue'

import CitationItem from '@/components/CitationItem.vue'
import { api } from '@/services/api'
import type { ChatOut } from '@/types/api'

const query = ref('X1 产品最大日处理能力是多少？')
const loading = ref(false)
const error = ref('')
const result = ref<ChatOut | null>(null)
const quickQuestions = ['X1 产品最大日处理能力是多少？', '最近 7 天有哪些值得关注的行业风险？', '召回事件可能影响哪些供应链环节？']

async function ask(question = query.value) {
  if (!question.trim() || loading.value) return
  query.value = question
  loading.value = true
  error.value = ''
  try {
    result.value = await api.chat(question.trim())
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '问答请求失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page standard-page assistant-page">
    <header class="page-header split-header">
      <div><p class="eyebrow">KNOWLEDGE COPILOT</p><h1>AI 助手</h1><p>让公开情报与企业私有知识，在同一次回答中相互印证。</p></div>
      <div class="workflow-indicator"><span><CheckCircle2 :size="16" />RAGFlow 已连接</span><span><CheckCircle2 :size="16" />WF1 可用</span></div>
    </header>

    <div class="assistant-layout">
      <section class="question-panel">
        <div class="assistant-avatar"><Bot :size="26" /></div>
        <p class="assistant-greeting">你好，我是智讯通助手。<br />今天想从哪条线索开始？</p>
        <form class="ask-box" @submit.prevent="ask()">
          <textarea v-model="query" rows="4" aria-label="输入问题" placeholder="输入关于产品、供应链或行业情报的问题…" @keydown.ctrl.enter="ask()" />
          <div class="ask-actions"><span>Ctrl + Enter 发送</span><button type="submit" :disabled="loading || !query.trim()"><LoaderCircle v-if="loading" :size="18" class="spin" /><ArrowUp v-else :size="18" /></button></div>
        </form>
        <div class="quick-questions"><span>推荐问题</span><button v-for="item in quickQuestions" :key="item" type="button" @click="ask(item)">{{ item }}</button></div>
      </section>

      <section class="answer-panel">
        <div class="answer-head"><span><Sparkles :size="17" />综合回答</span><small v-if="result">{{ result.workflow }}</small></div>
        <div v-if="loading" class="answer-loading"><span /><span /><span /><p>正在检索企业知识并执行工作流…</p></div>
        <div v-else-if="error" class="answer-empty error-state"><strong>暂时无法完成回答</strong><p>{{ error }}</p></div>
        <div v-else-if="result" class="answer-content">
          <p>{{ result.answer }}</p>
          <div class="answer-note"><CheckCircle2 :size="16" />回答已由企业知识库引用支撑，请结合原文复核后决策。</div>
          <div class="citations-block">
            <div class="subsection-title"><span>引用来源</span><small>{{ result.citations.length }} 条证据</small></div>
            <CitationItem v-for="(citation, index) in result.citations" :key="`${citation.doc}-${index}`" :citation="citation" :index="index" />
          </div>
        </div>
        <div v-else class="answer-empty"><Sparkles :size="28" /><strong>答案将在这里出现</strong><p>系统会同时检索企业文档与 AI 工作流，并保留可核验的引用来源。</p></div>
      </section>
    </div>
  </div>
</template>
