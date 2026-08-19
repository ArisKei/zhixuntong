<script setup lang="ts">
import type { NewsCategory } from '@/types/api'

const props = defineProps<{ category: NewsCategory }>()
const labels: Record<NewsCategory, string> = {
  policy: '政策', company: '企业', market: '市场', tech: '技术', risk: '风险', other: '其他',
}
</script>

<template>
  <span class="category-tag" :class="`category-${props.category}`">{{ labels[props.category] }}</span>
</template>
