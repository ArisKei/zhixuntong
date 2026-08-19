import alertMock from '@/mock/alerts.json'
import knowledgeMock from '@/mock/knowledge.json'
import newsMock from '@/mock/news.json'
import reportMock from '@/mock/reports.json'
import type {
  AlertItem, AlertListOut, ChatOut, CrawlerTask, DemoRecallOut, KnowledgeDocument,
  KnowledgeSearchOut, NewsCategory, NewsItem, NewsListOut, NotifyOut, ReportItem, ReportListOut,
} from '@/types/api'

type ApiMode = 'mock' | 'live'
type RequestOptions = RequestInit & { timeout?: number }

const TOKEN_KEY = 'zhixuntong_access_token'
const configuredMode = import.meta.env.VITE_API_MODE ?? 'mock'
const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

export const apiMode: ApiMode = configuredMode

const clone = <T>(data: T): T => JSON.parse(JSON.stringify(data)) as T
const wait = (duration = 260) => new Promise((resolve) => window.setTimeout(resolve, duration))

let mockNews = clone(newsMock) as NewsListOut
let mockAlerts = clone(alertMock) as AlertListOut
let mockKnowledge = clone(knowledgeMock) as KnowledgeSearchOut
let mockReports = clone(reportMock) as ReportListOut

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code = 'request_failed') {
    super(message)
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), options.timeout ?? 12_000)
  const token = localStorage.getItem(TOKEN_KEY)
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { code?: string; message?: string }
      throw new ApiError(body.message ?? `请求失败（${response.status}）`, response.status, body.code)
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('请求超时，请检查中台服务是否启动', 408, 'timeout')
    }
    throw new ApiError('无法连接中台服务，请检查 API 地址与网络', 0, 'network_error')
  } finally {
    window.clearTimeout(timer)
  }
}

async function mockCall<T>(data: T): Promise<T> {
  await wait()
  return clone(data)
}

/**
 * API 接入总约定：
 * - live 模式下除登录外统一携带 `Authorization: Bearer <access_token>`。
 * - 时间统一使用 ISO 8601；枚举只使用 OpenAPI 冻结值，禁止前端自行映射成新值回传。
 * - 错误响应期望为 `{ code: string, message: string }`，401 由登录态处理，503 表示外部服务不可用。
 * - mock 与 live 返回同一 TypeScript 类型，页面层不感知数据来源。
 */
export const api = {
  mode: apiMode,
  baseUrl,

  isAuthenticated() { return Boolean(localStorage.getItem(TOKEN_KEY)) },
  logout() { localStorage.removeItem(TOKEN_KEY) },

  /**
   * API 需求｜登录
   * POST `/api/auth/login`；请求 `{ username, password }`；返回 `{ access_token, token_type }`。
   * 此接口无需 Bearer Token。401 时需返回可直接展示的 `message`；演示账号为 demo / demo123。
   */
  async login(username: string, password: string): Promise<void> {
    if (apiMode === 'mock') {
      await wait(420)
      if (username !== 'demo' || password !== 'demo123') {
        throw new ApiError('账号或密码错误，请使用演示账号', 401, 'invalid_credentials')
      }
      localStorage.setItem(TOKEN_KEY, 'mock-demo-token')
      return
    }
    const result = await request<{ access_token: string; token_type: string }>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password }),
    })
    localStorage.setItem(TOKEN_KEY, result.access_token)
  },

  /**
   * API 需求｜新闻列表
   * GET `/api/news?category&days&page&page_size`；返回 `NewsListOut { items, meta }`。
   * category 为空表示全部；首页需要最近 5 条，情报页需要分类筛选；列表应按 published_at 倒序。
   */
  async getNews(params: { category?: NewsCategory; days?: number; page?: number; pageSize?: number } = {}): Promise<NewsListOut> {
    const { category, days = 7, page = 1, pageSize = 20 } = params
    if (apiMode === 'mock') {
      const items = category ? mockNews.items.filter((item) => item.category === category) : mockNews.items
      return mockCall({ items: items.slice(0, pageSize), meta: { total: items.length, page, page_size: pageSize } })
    }
    const query = new URLSearchParams({ days: String(days), page: String(page), page_size: String(pageSize) })
    if (category) query.set('category', category)
    return request<NewsListOut>(`/api/news?${query.toString()}`)
  },

  /**
   * API 需求｜预警列表
   * GET `/api/alerts?page&page_size`；返回 `AlertListOut { items, meta }`，按 created_at 倒序。
   * 前端在本地按 level 过滤；若数据量增大，建议后端补充 `level` 查询参数并保持兼容。
   */
  async getAlerts(page = 1, pageSize = 20): Promise<AlertListOut> {
    if (apiMode === 'mock') return mockCall(mockAlerts)
    return request<AlertListOut>(`/api/alerts?page=${page}&page_size=${pageSize}`)
  },

  /**
   * API 需求｜启动采集
   * POST `/api/crawler/start`；请求 `{ source_id }`，取 miit_policy / ev_news / oem_news / all / demo_recall。
   * 返回完整 `CrawlerTaskOut`。演示闭环使用 demo_recall，并依赖完成后风险新闻可立即从 `/api/news` 查询。
   */
  async startCrawler(sourceId: string): Promise<CrawlerTask> {
    if (apiMode === 'mock') {
      await wait(700)
      return {
        task_id: `task_${Date.now()}`, source_id: sourceId, status: 'success', fetched: 8, parsed: 8,
        dropped_short: 0, inserted: sourceId === 'demo_recall' ? 1 : 6,
        duplicated: sourceId === 'demo_recall' ? 0 : 2, error_message: null,
        started_at: new Date(Date.now() - 1800).toISOString(), finished_at: new Date().toISOString(),
      }
    }
    return request<CrawlerTask>('/api/crawler/start', {
      method: 'POST', body: JSON.stringify({ source_id: sourceId }), timeout: 30_000,
    })
  },

  /**
   * API 需求｜采集状态
   * GET `/api/crawler/status?task_id`；不传 task_id 返回最近一次任务。
   * 轮询依赖 status 从 pending/running 收敛到 success/failed，并需要 error_message 提供失败原因。
   */
  async getCrawlerStatus(taskId?: string): Promise<CrawlerTask> {
    if (apiMode === 'mock') return this.startCrawler('all')
    const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : ''
    return request<CrawlerTask>(`/api/crawler/status${query}`)
  },

  /**
   * API 需求｜统一问答
   * POST `/api/chat`；请求 `{ query }`；返回 `{ answer, citations, workflow }`。
   * citations 至少含 doc/snippet，page/score 可空；当前整包返回，未来流式化需另增 SSE 契约，不能改变本结构。
   */
  async chat(query: string): Promise<ChatOut> {
    if (apiMode === 'mock') {
      await wait(850)
      const answer = query.includes('6800') || query.includes('日处理')
        ? '根据《X1产品说明书》，X1 产品的最大日处理能力为 6800 件。该数据对应标准运行环境下的额定能力，建议在产能规划时预留设备维护窗口。'
        : '综合企业知识库与近 7 天公开情报，建议优先关注动力电池安全、回收政策落地和海外关税变化，并对高风险事件建立供应链核验清单。'
      return mockCall({ answer, citations: mockKnowledge.citations.slice(0, 1), workflow: 'wf_knowledge_qa' })
    }
    return request<ChatOut>('/api/chat', { method: 'POST', body: JSON.stringify({ query }), timeout: 30_000 })
  },

  /**
   * API 需求｜知识库文档列表 / 检索
   * GET `/api/knowledge/search?query&top_k`；query 为空返回 documents，非空返回 citations。
   * 返回始终保留 `{ query, citations, documents }` 三个字段，空集合用 []，不要省略。
   */
  async searchKnowledge(query = '', topK = 5): Promise<KnowledgeSearchOut> {
    if (apiMode === 'mock') {
      return mockCall({ query, citations: query ? mockKnowledge.citations.slice(0, topK) : [], documents: mockKnowledge.documents })
    }
    const params = new URLSearchParams({ query, top_k: String(topK) })
    return request<KnowledgeSearchOut>(`/api/knowledge/search?${params.toString()}`)
  },

  /**
   * API 需求｜上传企业文档
   * POST `/api/knowledge/upload`，multipart/form-data，字段名必须为 `file`；返回 `{ document: KnowledgeDocOut }`。
   * 需支持 PDF/DOCX/TXT，503 时明确 RAG 服务不可用；当前契约无真实上传进度，前端只能展示请求阶段。
   * 建议后端后续增加异步任务 id 与解析状态查询，避免大文件请求超时。
   */
  async uploadKnowledge(file: File): Promise<KnowledgeDocument> {
    if (apiMode === 'mock') {
      await wait(1000)
      const document: KnowledgeDocument = {
        id: Date.now(), filename: file.name, dataset: 'enterprise', status: 'ready',
        chunk_count: Math.max(4, Math.round(file.size / 12_000)), created_at: new Date().toISOString(),
      }
      mockKnowledge.documents.unshift(document)
      return clone(document)
    }
    const body = new FormData()
    body.append('file', file)
    const result = await request<{ document: KnowledgeDocument }>('/api/knowledge/upload', { method: 'POST', body, timeout: 60_000 })
    return result.document
  },

  /**
   * API 需求｜生成情报周报
   * POST `/api/analyze`；请求 `{ range_days }`；返回 `ReportOut`，content_md 必须包含约定的六个二级标题。
   * 成功响应后应能从 `/api/reports` 查询同一报告；AI 工作流超时建议返回 503 与可读 message。
   */
  async analyze(rangeDays = 7): Promise<ReportItem> {
    if (apiMode === 'mock') {
      await wait(1200)
      const report = clone(mockReports.items[0])
      report.id = Date.now(); report.range_days = rangeDays; report.created_at = new Date().toISOString()
      mockReports.items.unshift(report); mockReports.meta.total += 1
      return report
    }
    return request<ReportItem>('/api/analyze', { method: 'POST', body: JSON.stringify({ range_days: rangeDays }), timeout: 60_000 })
  },

  /**
   * API 需求｜报告列表
   * GET `/api/reports?page&page_size`；返回 `ReportListOut`，按 created_at 倒序。
   * 前端展示原始 Markdown 的固定六段，不要求后端返回 HTML。
   */
  async getReports(page = 1, pageSize = 20): Promise<ReportListOut> {
    if (apiMode === 'mock') return mockCall(mockReports)
    return request<ReportListOut>(`/api/reports?page=${page}&page_size=${pageSize}`)
  },

  /**
   * API 需求｜单条新闻风险研判
   * POST `/api/alert/evaluate`；请求 `{ news_id }`；返回完整 `AlertOut`。
   * 标题含“召回”时业务规则要求 level 至少为 high；成功后该预警应可立即从 `/api/alerts` 查询。
   */
  async evaluateAlert(newsId: number): Promise<AlertItem> {
    if (apiMode === 'mock') {
      const existing = mockAlerts.items.find((item) => item.news_id === newsId)
      if (existing) return mockCall(existing)
      const news = mockNews.items.find((item) => item.id === newsId)
      if (!news) throw new ApiError('未找到待研判新闻', 404, 'news_not_found')
      const alert: AlertItem = {
        alert_id: `alrt_${Date.now()}`, level: news.title.includes('召回') ? 'high' : 'medium',
        company: news.company ?? '行业整体', title: news.title, summary: news.content.slice(0, 80),
        impact: '可能影响品牌信誉、生产计划及供应链订单', suggestion: '核对本公司关联零部件与供应商，建立专项跟踪清单',
        news_id: news.id, citations: [], created_at: new Date().toISOString(),
      }
      mockAlerts.items.unshift(alert); mockAlerts.meta.total += 1
      return clone(alert)
    }
    return request<AlertItem>('/api/alert/evaluate', { method: 'POST', body: JSON.stringify({ news_id: newsId }), timeout: 30_000 })
  },

  /**
   * API 需求｜发送钉钉预警
   * POST `/api/notify/dingtalk`；请求 `{ alert_id }`；返回 `{ ok, channel, message }`。
   * 后端负责按 docs/events.md 锁定模板拼文案；前端不得传可自由编辑的消息正文。
   */
  async notifyDingtalk(alertId: string): Promise<NotifyOut> {
    if (apiMode === 'mock') return mockCall({ ok: true, channel: 'dingtalk', message: '钉钉预警已进入发送队列' })
    return request<NotifyOut>('/api/notify/dingtalk', { method: 'POST', body: JSON.stringify({ alert_id: alertId }) })
  },

  /**
   * API 需求｜发送预警邮件
   * POST `/api/notify/email`；请求 `{ kind: "alert", alert_id, to? }`；返回 `{ ok, channel, message }`。
   * to 为空使用服务端默认收件人；后端需校验 alert_id 并使用固定预警邮件模板。
   */
  async notifyEmail(alertId: string, to?: string): Promise<NotifyOut> {
    if (apiMode === 'mock') return mockCall({ ok: true, channel: 'email', message: '预警邮件已进入发送队列' })
    return request<NotifyOut>('/api/notify/email', {
      method: 'POST', body: JSON.stringify({ kind: 'alert', alert_id: alertId, to: to || null }),
    })
  },

  /**
   * API 需求｜一键召回闭环（前端临时编排）
   * 当前 OpenAPI 无原子 demo 接口，因此依次调用 crawler/start → news → alert/evaluate → 双通道 notify。
   * 建议后端补充 `POST /api/demo/recall`，返回 `{ task, news, alert, notifications }`，并用幂等键避免重复告警；
   * 在该接口落地前，此方法保持对现有冻结接口的兼容，不要求后端改字段。
   */
  async runDemoRecall(): Promise<DemoRecallOut> {
    const task = await this.startCrawler('demo_recall')
    const newsResult = await this.getNews({ category: 'risk', days: 30, pageSize: 20 })
    const recallNews: NewsItem | undefined = newsResult.items.find((item) => item.title.includes('召回'))
    if (!recallNews) throw new ApiError('采集完成，但未找到召回新闻', 404, 'recall_news_not_found')
    const alert = await this.evaluateAlert(recallNews.id)
    const notifications = await Promise.all([this.notifyDingtalk(alert.alert_id), this.notifyEmail(alert.alert_id)])
    return { task, alert, notifications }
  },
}
