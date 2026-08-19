import { mkdir } from 'node:fs/promises'
import { chromium } from '@playwright/test'

const baseUrl = 'http://127.0.0.1:5173'
const outputDir = 'artifacts/ui-check'
const executablePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch({ executablePath, headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN' })
const page = await context.newPage()
const pageErrors = []
const consoleErrors = []

page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: '欢迎回来' }).waitFor()
  await page.screenshot({ path: `${outputDir}/01-login.png`, fullPage: true })

  await page.getByLabel('账号').fill('demo')
  await page.getByLabel('密码').fill('demo123')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await page.locator('.login-layer').waitFor({ state: 'detached' })
  await page.locator('.hero-content h1').waitFor()
  await page.screenshot({ path: `${outputDir}/02-home.png`, fullPage: true })

  const routes = await page.locator('.main-nav .nav-link').count()
  if (routes !== 5) throw new Error(`主导航数量错误：${routes}`)

  await page.getByRole('link', { name: 'AI 助手' }).click()
  await page.getByRole('heading', { name: 'AI 助手' }).waitFor()
  await page.locator('.ask-box button[type="submit"]').click()
  await page.locator('.answer-content').waitFor()
  await page.getByText('6800 件').waitFor()

  await page.getByRole('link', { name: '知识库' }).click()
  await page.getByRole('heading', { name: '企业知识库' }).waitFor()
  await page.getByRole('button', { name: '开始检索' }).click()
  await page.locator('.search-results').waitFor()

  await page.getByRole('link', { name: '情报监控' }).click()
  await page.getByRole('heading', { name: '情报监控' }).waitFor()
  await page.locator('.report-sections article').first().waitFor()
  const reportSections = await page.locator('.report-sections article').count()
  if (reportSections !== 6) throw new Error(`周报标题数量错误：${reportSections}`)

  await page.getByRole('link', { name: '预警列表' }).click()
  await page.getByRole('heading', { name: '预警列表' }).waitFor()
  await page.getByRole('button', { name: '推送钉钉' }).click()
  await page.getByText('钉钉预警已进入发送队列').waitFor()

  await page.getByRole('link', { name: '总览' }).click()
  await page.getByRole('button', { name: '跑一次召回闭环' }).click()
  await page.locator('.demo-success').waitFor({ timeout: 15_000 })
  await page.screenshot({ path: `${outputDir}/03-demo-recall.png`, fullPage: true })

  const mobilePage = await context.newPage()
  await mobilePage.setViewportSize({ width: 390, height: 844 })
  await mobilePage.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await mobilePage.locator('.hero-content h1').waitFor()
  await mobilePage.screenshot({ path: `${outputDir}/04-mobile.png`, fullPage: true })
  await mobilePage.close()

  console.log(JSON.stringify({ ok: true, routes, reportSections, pageErrors, consoleErrors }, null, 2))
} finally {
  await browser.close()
}

if (pageErrors.length || consoleErrors.length) process.exitCode = 1
