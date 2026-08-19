<script setup lang="ts">
import { BookOpen, ChevronRight } from 'lucide-vue-next'
import type { Citation } from '@/types/api'

defineProps<{ citation: Citation; index: number }>()
</script>

<template>
  <article class="citation-item">
    <div class="citation-icon"><BookOpen :size="17" /></div>
    <div class="citation-body">
      <div class="citation-meta">
        <strong>[{{ index + 1 }}] {{ citation.doc }}</strong>
        <span v-if="citation.page">第 {{ citation.page }} 页</span>
        <span v-if="citation.score">相关度 {{ Math.round(citation.score * 100) }}%</span>
      </div>
      <p>{{ citation.snippet }}</p>
    </div>
    <ChevronRight :size="17" class="citation-arrow" />
  </article>
</template>
