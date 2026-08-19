export type NewsCategory = 'policy' | 'company' | 'market' | 'tech' | 'risk' | 'other'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type TaskStatus = 'pending' | 'running' | 'success' | 'failed'

export interface PageMeta { total: number; page: number; page_size: number }
export interface Citation { doc: string; page: number | null; snippet: string; score: number | null }
export interface NewsItem {
  id: number; title: string; published_at: string; source: string; source_url: string
  category: NewsCategory; company: string | null; content: string; content_hash: string
  keywords: string[]; is_duplicate: boolean
}
export interface NewsListOut { items: NewsItem[]; meta: PageMeta }
export interface AlertItem {
  alert_id: string; level: RiskLevel; company: string; title: string; summary: string
  impact: string; suggestion: string; news_id: number; citations: Citation[]; created_at: string | null
}
export interface AlertListOut { items: AlertItem[]; meta: PageMeta }
export interface KnowledgeDocument {
  id: number; filename: string; dataset: string; status: string; chunk_count: number; created_at: string
}
export interface KnowledgeSearchOut { query: string; citations: Citation[]; documents: KnowledgeDocument[] }
export interface ChatOut { answer: string; citations: Citation[]; workflow: string }
export interface ReportItem {
  id: number | null; title: string; kind: 'daily' | 'weekly' | 'incident'
  range_days: number; content_md: string; created_at: string | null
}
export interface ReportListOut { items: ReportItem[]; meta: PageMeta }
export interface CrawlerTask {
  task_id: string; source_id: string; status: TaskStatus; fetched: number; parsed: number
  dropped_short: number; inserted: number; duplicated: number; error_message: string | null
  started_at: string | null; finished_at: string | null
}
export interface NotifyOut { ok: boolean; channel: string; message: string }
export interface DemoRecallOut { task: CrawlerTask; alert: AlertItem; notifications: NotifyOut[] }
