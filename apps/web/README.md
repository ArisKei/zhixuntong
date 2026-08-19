# 智讯通前端

基于 Vite + Vue 3 + TypeScript 的五页面演示端，覆盖：首页、AI 助手、知识库、情报监控、预警列表。

> ✅ **开发状态：前端第一版已完成（2026-08-19）**

## 已完成功能

- 五个业务路由及统一导航、登录和响应式布局
- 首页指标、资讯流、今日研判与一键召回风险闭环
- AI 助手问答、RAG 引用文档/页码展示
- 知识库上传、文档索引、切片检索结果展示
- 情报分类筛选、详情查看、近 7 天六段周报
- 预警分级、研判依据、钉钉和预警邮件推送
- 当前行业报告一键发送日报 / 周报邮件
- Mock/真实 FastAPI 双模式 API 适配
- 401 登录过期自动回到登录页
- 类型检查、生产构建和桌面/移动端 UI 自动化验证

## 启动

首次安装依赖：

```powershell
npm install
```

日常开发推荐以前端 Live 模式连接已经启动的 FastAPI 中台：

```powershell
$env:VITE_API_MODE="live"
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1 --port 5173
```

上述变量只对当前 PowerShell 终端生效。需要持久化时，复制 `.env.example` 为 `.env`，然后设置：

```env
VITE_API_MODE=live
VITE_API_BASE_URL=http://127.0.0.1:8000
```

只运行 `npm run dev` 且未配置环境变量时，前端默认使用 `src/mock` 中与 OpenAPI 同结构的演示数据。修改环境变量后需要重启 Vite。

演示账号：`demo` / `demo123`。

## 接口对接

所有接口调用统一收口在 `src/services/api.ts`。每个调用上方的 `API 需求` 注释记录了路径、请求字段、返回字段、鉴权、前端依赖和待后端补充项；字段名以仓库根目录的 `docs/openapi.yaml` 为准。

## 检查

```powershell
npm run typecheck
npm run build
npm run verify:ui
```

验证结果：五个路由、六段周报、AI 问答、知识检索、预警/日报推送和召回闭环在 Mock 与 FastAPI live 模式均通过，页面错误与控制台错误为 0。
