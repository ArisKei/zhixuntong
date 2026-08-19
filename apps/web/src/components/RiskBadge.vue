<script setup lang="ts">
import type { RiskLevel } from '@/types/api'

const props = defineProps<{ level: RiskLevel }>()
const labels: Record<RiskLevel, string> = { low: '低风险', medium: '中风险', high: '高风险', critical: '紧急' }
</script>

<template>
  <span class="risk-badge" :class="`risk-${props.level}`"><span class="risk-dot" />{{ labels[props.level] }}</span>
</template>
