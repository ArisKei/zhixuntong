# -*- coding: utf-8 -*-
"""B5 · 数据源 1：miit_policy（工信部政策文件发布）

三件套：本文件（spider 编排）+ selectors_miit_policy.py（DOM 选择器）
+ fixtures/html/miit_policy/（离线种子：list.html + art_*.html）。

验收（任务卡 B5）：fixture 至少解析出 5 条 → 自测 6 条全通过。
"""

from __future__ import annotations

import selectors_miit_policy as selectors
from base import MODE_FIXTURE, MODE_LIVE, BaseSpider, RawItem


class MiitPolicySpider(BaseSpider):
    """工信部政策源：列表页（标题+链接+日期）→ 详情页（标题+发布时间+正文）。

    - 政策类新闻无企业主体：company 恒为 None
    - 分类与关键词由 B4 规则自动完成（政策词密集 → policy）
    - DOM 细节全部委托 selectors 模块，本类只做编排与字段映射
    - fixture/live 双轨 selectors（B12）：按 self.mode 分发，
      演示答辩（fixture）与真实采集（live）互不影响
    """

    source_id = "miit_policy"
    # live 入口：工信部装备工业一司·工作动态（B11 实测创宇盾 WAF → live 走 Selenium 渲染）
    list_url = "https://www.miit.gov.cn/jgsj/zbys/gzdt/index.html"
    use_browser = True  # B11 连通性实测：requests 裸连/带 UA 均 403，无头 Chrome 可过
    max_pages = 3  # 多页采集（B16）：分页 JS 驱动（共 86 页）→ live 走浏览器点击翻页

    def _list_page_htmls(self, max_pages: int):
        """live 列表翻页覆写（B16）：工信部分页是 javascript:; 点击翻页，URL 拼不出来。

        live 走 browser.fetch_paged（同会话点击页码）；fixture 退回基类（第 1 页）。
        """
        if self.mode == MODE_LIVE and self.use_browser:
            import browser

            for html in browser.fetch_paged(self.list_url, max_pages):
                yield html
            return
        yield from super()._list_page_htmls(max_pages)

    def parse_list(self, html: str) -> list[RawItem]:
        """列表页 → 待抓条目（fixture/live 结构不同，分发到对应 selectors）。"""
        parse = selectors.parse_list_live if self.mode == MODE_LIVE else selectors.parse_list
        items: list[RawItem] = []
        for row in parse(html):
            published = self.parse_datetime(row["date"]) if row["date"] else None
            items.append(RawItem(url=row["url"], title=row["title"], published_at=published))
        return items

    def parse_detail(self, html: str, item: RawItem) -> dict | None:
        """详情页 → normalize 待消费的字段（日期取详情页，缺失退回列表页）。"""
        parse = selectors.parse_detail_live if self.mode == MODE_LIVE else selectors.parse_detail
        detail = parse(html)
        if detail is None:
            return None
        return {
            "title": detail["title"] or item.title,
            "source_url": item.url,
            "published_at": detail["date"] or item.published_at,
            "content": detail["content_html"],
            "company": None,  # 政策无企业主体
        }

    def classify(self, title: str, content: str) -> str:
        """政策源分类覆写（B12）：栏目语义恒 policy，仅标题命中风险词才 risk。

        工信部工作动态全是监管/政策发布，正文高频出现「隐患/处罚/检查」等
        监管语境词——B4 的正文级风险一票否决会大面积误伤（实测：检验检测
        座谈新闻正文提「风险隐患甄别」被误判 risk）。标题命中（如「关于XX
        召回的处罚通报」）才是真正的风险类通报。
        """
        from classifier import RISK_KEYWORDS

        if any(word in title for word in RISK_KEYWORDS):
            return "risk"
        return "policy"


# ---------------------------------------------------------------------------
# B5 自测：fixture 模式跑通全流水线（不访问网络）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import datetime

    spider = MiitPolicySpider(mode=MODE_FIXTURE)
    items, stats = spider.run()

    # B5 验收：fixture 至少 5 条
    assert stats.fetched >= 5, stats
    assert stats.parsed >= 5 and stats.dropped_short == 0, stats
    assert len(items) >= 5, stats

    # 契约字段与 B4 规则分类（政策词密集，6 条应全部 policy）
    assert all(i.source == "miit_policy" for i in items)
    assert all(i.company is None for i in items)
    assert all(i.category == "policy" for i in items), [i.category for i in items]
    assert all(len(i.content) >= 80 for i in items)
    assert all(i.content_hash == BaseSpider.make_hash(i.title, i.source_url) for i in items)
    assert all(isinstance(i.published_at, datetime) for i in items)

    # 选择器隔离 + 清洗兜底：页面噪音与附件链接行不混入正文
    assert all("当前位置" not in i.content for i in items)
    assert all("主办单位" not in i.content for i in items)
    assert all("docx" not in i.content and "附件" not in i.content for i in items)

    # 清洗防泄漏（B3 强化回归）：元信息行不混入正文、段落不因容器嵌套重复
    assert all("发布时间" not in i.content and "来源" not in i.content for i in items)
    assert items[0].content.count("溯源管理体系") == 1

    # 详情页日期优先于列表页：首条 = 列表最新一条（2026-08-17）
    assert items[0].published_at == datetime(2026, 8, 17), items[0].published_at
    assert "回收" in items[0].keywords and len(items[0].keywords) <= 5

    for index, i in enumerate(items, 1):
        print(
            f"[selftest] {index}. {i.title[:26]}… | {i.category} | "
            f"{i.published_at:%Y-%m-%d} | kw={i.keywords}"
        )
    print(f"[selftest] B5 验收通过：miit_policy fixture 解析 {len(items)} 条（≥5）")

    # ------------------------------------------------------------------
    # B12 自测：live 快照离线跑通（不访问网络）
    # 用 B11 存档的真实站点快照（fixtures/html/live/miit_policy/）验证
    # live selectors + mode 分发，走完整流水线（fetch 被替换为读快照）
    # ------------------------------------------------------------------
    from pathlib import Path

    import re

    live_dir = Path(__file__).resolve().parents[2] / "fixtures" / "html" / "live" / "miit_policy"
    snapshot = {p.name: p.read_text(encoding="utf-8") for p in live_dir.glob("*.html")}
    assert "list.html" in snapshot, "live 快照缺失 list.html"

    class _LiveSnapshotSpider(MiitPolicySpider):
        """live 模式但 fetch 读 B11 快照：全流水线离线可测（不发网络请求）。"""

        use_browser = False  # 快照测试不发真实浏览器请求（B16 点击翻页仅 live+use_browser 走）
        max_pages = 1  # 快照测试固定第 1 页；多页见下方 B16 专项断言

        def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
            if is_list:
                return snapshot["list.html"]
            name = url.rstrip("/").rsplit("/", 1)[-1]
            if not name.endswith(".html"):
                name += ".html"
            return snapshot[name]  # KeyError = 快照缺该详情页（测试资产问题）

    live_spider = _LiveSnapshotSpider(mode=MODE_LIVE)
    live_items, live_stats = live_spider.run()

    # B12 验收：live 快照 ≥5 条（快照列表页 24 条，详情页仅存 2 份 →
    # 其余详情 fetch 会 KeyError？不会：run() 的详情失败只跳过该条）
    assert live_stats.fetched >= 5, live_stats
    assert len(live_items) >= 1, live_stats

    # 快照只存了 2 个详情页：只有对应 2 条能走完全流水线
    ok_items = [i for i in live_items]
    assert len(ok_items) >= 1
    first = ok_items[0]
    assert first.source_url.startswith("https://www.miit.gov.cn/jgsj/zbys/gzdt/art/")
    assert first.title and "…" not in first.title and "..." not in first.title  # title 属性完整标题
    assert first.published_at is not None and first.published_at.hour > 0  # 详情页带时分
    assert len(first.content) >= 80
    assert first.category in ("policy", "other")
    assert first.company is None
    # 清洗防泄漏：元信息/二维码/分享不混入正文
    assert "发布时间" not in first.content and "来源" not in first.content
    assert "扫一扫" not in first.content and "分享" not in first.content

    # 列表解析专项：24 条、URL 全绝对、标题全完整（title 属性）
    rows = selectors.parse_list_live(snapshot["list.html"])
    assert len(rows) >= 5, len(rows)
    assert all(r["url"].startswith("https://www.miit.gov.cn/") for r in rows)
    assert all(r["date"] and re.match(r"\d{4}-\d{2}-\d{2}$", r["date"]) for r in rows)

    # B16 多页：第 2 页快照解析（Selenium 点击翻页存档，结构与第 1 页一致）
    if "list_2.html" in snapshot:
        rows2 = selectors.parse_list_live(snapshot["list_2.html"])
        assert len(rows2) >= 5, len(rows2)
        print(f"[selftest] B16 多页：miit 第 2 页 rows={len(rows2)}")

    # 详情解析专项：带时分的时间串
    detail_files = [k for k in snapshot if k != "list.html"]
    detail = selectors.parse_detail_live(snapshot[detail_files[0]])
    assert detail["title"], detail
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", detail["date"]), detail["date"]
    assert "con_con" in detail["content_html"]

    print(
        f"[selftest] live rows={len(rows)} parsed={live_stats.parsed} "
        f"items={len(live_items)} first='{first.title[:24]}…' "
        f"published_at={first.published_at:%Y-%m-%d %H:%M} content_len={len(first.content)}"
    )
    print("[selftest] B12 验收通过：miit_policy live 快照解析（列表≥5 + 详情完整流水线）")
