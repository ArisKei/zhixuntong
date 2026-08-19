import { createRouter, createWebHistory } from 'vue-router'

import AlertsView from '@/views/AlertsView.vue'
import AssistantView from '@/views/AssistantView.vue'
import HomeView from '@/views/HomeView.vue'
import IntelView from '@/views/IntelView.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView, meta: { title: '总览' } },
    { path: '/assistant', name: 'assistant', component: AssistantView, meta: { title: 'AI 助手' } },
    { path: '/knowledge', name: 'knowledge', component: KnowledgeView, meta: { title: '知识库' } },
    { path: '/intel', name: 'intel', component: IntelView, meta: { title: '情报监控' } },
    { path: '/alerts', name: 'alerts', component: AlertsView, meta: { title: '预警列表' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title)} · 智讯通`
})

export default router
