<script setup lang="ts">
import { Check, Database, FileText, LoaderCircle, Search, Upload, X } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'

import CitationItem from '@/components/CitationItem.vue'
import { api } from '@/services/api'
import type { Citation, KnowledgeDocument } from '@/types/api'

const documents = ref<KnowledgeDocument[]>([])
const citations = ref<Citation[]>([])
const searchQuery = ref('X1 最大日处理能力')
const loading = ref(true)
const searching = ref(false)
const uploading = ref(false)
const uploadName = ref('')
const uploadProgress = ref(0)
const error = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

async function loadDocuments() {
  loading.value = true
  try {
    const result = await api.searchKnowledge()
    documents.value = result.documents
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '文档列表加载失败'
  } finally {
    loading.value = false
  }
}

async function search() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  error.value = ''
  try {
    const result = await api.searchKnowledge(searchQuery.value.trim(), 5)
    citations.value = result.citations
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '知识检索失败'
  } finally {
    searching.value = false
  }
}

async function upload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  uploading.value = true
  uploadName.value = file.name
  uploadProgress.value = 18
  error.value = ''
  const timer = window.setInterval(() => { uploadProgress.value = Math.min(88, uploadProgress.value + 8) }, 160)
  try {
    const document = await api.uploadKnowledge(file)
    uploadProgress.value = 100
    documents.value.unshift(document)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '上传失败'
  } finally {
    window.clearInterval(timer)
    window.setTimeout(() => {
      uploading.value = false; uploadName.value = ''; uploadProgress.value = 0; target.value = ''
    }, 650)
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
}

onMounted(loadDocuments)
</script>

<template>
  <div class="page standard-page knowledge-page">
    <header class="page-header split-header">
      <div><p class="eyebrow">ENTERPRISE KNOWLEDGE</p><h1>企业知识库</h1><p>把产品文档、供应链报告和内部资料，变成可检索、可引用的决策证据。</p></div>
      <button class="primary-button" type="button" @click="fileInput?.click()"><Upload :size="17" />上传文档</button>
      <input ref="fileInput" class="sr-only" type="file" accept=".pdf,.doc,.docx,.txt" @change="upload" />
    </header>

    <div v-if="uploading" class="upload-progress">
      <div><FileText :size="20" /><span><strong>{{ uploadName }}</strong><small>正在上传并解析文档</small></span></div>
      <div class="progress-track"><i :style="{ width: `${uploadProgress}%` }" /></div><span>{{ uploadProgress }}%</span>
    </div>
    <div v-if="error" class="inline-error"><span>{{ error }}</span><button type="button" @click="error = ''"><X :size="15" />关闭</button></div>

    <section class="knowledge-search-section">
      <div class="section-heading compact"><div><p class="eyebrow">RETRIEVAL TEST</p><h2>试检索</h2></div><span class="section-note">验证文档是否已被正确切片和召回</span></div>
      <form class="search-bar" @submit.prevent="search">
        <Search :size="20" /><input v-model="searchQuery" aria-label="知识库检索" placeholder="输入要在企业资料中核验的问题…" />
        <button type="submit" :disabled="searching"><LoaderCircle v-if="searching" :size="18" class="spin" />{{ searching ? '检索中' : '开始检索' }}</button>
      </form>
      <div v-if="citations.length" class="search-results">
        <div class="subsection-title"><span>命中片段</span><small>{{ citations.length }} 条结果</small></div>
        <CitationItem v-for="(citation, index) in citations" :key="`${citation.doc}-${index}`" :citation="citation" :index="index" />
      </div>
      <div v-else class="search-hint"><Database :size="20" /><span>输入问题，查看文档片段、页码与相关度。</span></div>
    </section>

    <section class="documents-section">
      <div class="section-heading compact"><div><p class="eyebrow">DOCUMENT INDEX</p><h2>已接入文档</h2></div><span class="document-total">{{ documents.length }} 份资料</span></div>
      <div class="document-table">
        <div class="document-row table-head"><span>文档名称</span><span>数据集</span><span>切片数</span><span>更新时间</span><span>状态</span></div>
        <div v-if="loading" class="table-loading">正在读取知识库索引…</div>
        <div v-for="document in documents" v-else :key="document.id" class="document-row">
          <span class="document-name"><FileText :size="18" /><strong>{{ document.filename }}</strong></span><span>{{ document.dataset }}</span><span>{{ document.chunk_count }}</span><span>{{ formatDate(document.created_at) }}</span><span class="ready-status"><Check :size="14" />{{ document.status }}</span>
        </div>
      </div>
    </section>
  </div>
</template>
