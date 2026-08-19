# -*- coding: utf-8 -*-
"""B6 · 数据源 2：ev_news（行业新闻，混合 market/tech/risk 分类）

三件套：本文件（spider 编排）+ selectors_ev_news.py（DOM 选择器）
+ fixtures/html/ev_news/（离线种子：list.html + 8 个详情页）。

验收（任务卡 B6）：fixture 至少解析出 8 条 → 自测 8 条全通过。

与种子的关系（答辩关键设计）：其中 4 条新闻与 fixtures/seed/news.json 同题同 URL
（标题 + 链接完全一致 → content_hash 一致），保证：
- 中台 mock 预置的种子数据与本地爬虫插入的数据可跨模式去重（B2 生效）
- 「召回」新闻是答辩主线 demo_recall 的数据来源（含召回 → risk + company）
"""

from __future__ import annotations

import selectors_ev_news as selectors
from base import MODE_FIXTURE, MODE_LIVE, BaseSpider, RawItem


class EvNewsSpider(BaseSpider):
    """行业新闻源：列表页（标题+绝对链接+时间）→ 详情页（标题+时间+正文+企业）。

    与 miit_policy 源的差异：
    - 链接为绝对地址（miit 为站点相对路径）
    - 时间带时分（miit 只有日期）
    - 正文可能点名企业 → company 可非空（miit 恒为 None）
    - fixture/live 双轨 selectors（B13）：按 self.mode 分发
    DOM 细节全部委托 selectors 模块，本类只做编排与字段映射。
    """

    source_id = "ev_news"
    # live 入口：第一电动网资讯频道（B11 实测：requests + 浏览器头 200，无需浏览器渲染）
    list_url = "https://www.d1ev.com/news"
    max_pages = 10  # 多页采集（B16）：分页规律 /news/list-N，快照实测最后一页 6782

    def _list_url_for_page(self, page: int) -> str | None:
        """第 N 页 URL：https://www.d1ev.com/news/list-N（第 1 页为裸 URL）。"""
        if page <= 1:
            return self.list_url
        return f"{self.list_url}/list-{page}"

    def parse_list(self, html: str) -> list[RawItem]:
        """列表页 → 待抓条目（fixture/live 结构不同，分发到对应 selectors）。"""
        parse = selectors.parse_list_live if self.mode == MODE_LIVE else selectors.parse_list
        items: list[RawItem] = []
        for row in parse(html):
            published = self.parse_datetime(row["datetime"]) if row["datetime"] else None
            items.append(RawItem(url=row["url"], title=row["title"], published_at=published))
        return items

    def parse_detail(self, html: str, item: RawItem) -> dict | None:
        """详情页 → normalize 待消费的字段（时间取详情页，缺失退回列表页）。"""
        parse = selectors.parse_detail_live if self.mode == MODE_LIVE else selectors.parse_detail
        detail = parse(html)
        if detail is None:
            return None
        return {
            "title": detail["title"] or item.title,
            "source_url": item.url,
            "published_at": detail["datetime"] or item.published_at,
            "content": detail["content_html"],
            "company": detail["company"],  # 行业新闻可能点名企业（如 XX汽车）
        }


# ---------------------------------------------------------------------------
# B6 自测：fixture 模式跑通全流水线（不访问网络）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from collections import Counter
    from datetime import datetime

    from base import REPO_ROOT

    spider = EvNewsSpider(mode=MODE_FIXTURE)
    items, stats = spider.run()

    # B6 验收：fixture 至少 8 条，全部解析成功、无过短丢弃
    assert stats.fetched >= 8, stats
    assert stats.parsed == 8 and stats.dropped_short == 0, stats
    assert len(items) == 8, stats

    # 契约字段
    assert all(i.source == "ev_news" for i in items)
    assert all(len(i.content) >= 80 for i in items)
    assert all(isinstance(i.published_at, datetime) for i in items)
    assert all(i.content_hash == BaseSpider.make_hash(i.title, i.source_url) for i in items)

    # 混合分类（B4 规则）：risk 1 / market 4 / tech 3
    counter = Counter(i.category for i in items)
    assert counter == {"risk": 1, "market": 4, "tech": 3}, counter

    # 召回新闻（答辩主线）：risk + 企业主体 + 关键词含召回
    recall = next(i for i in items if "召回" in i.title)
    assert recall.category == "risk" and recall.company == "XX汽车", recall
    assert "召回" in recall.keywords, recall.keywords

    # 与组长种子数据同题同 URL → content_hash 一致（跨模式去重的关键）
    seed = json.loads((REPO_ROOT / "fixtures" / "seed" / "news.json").read_text(encoding="utf-8"))
    seed_hashes = {
        BaseSpider.make_hash(row["title"], row["source_url"])
        for row in seed
        if row["source"] == "ev_news"
    }
    mirrored = [i for i in items if i.content_hash in seed_hashes]
    assert len(mirrored) == 4, [i.title for i in mirrored]

    # 清洗防泄漏：元信息行/热文链接/导航不混入正文；段落不重复
    assert all("发布时间" not in i.content for i in items)
    assert all("责编" not in i.content and "热文" not in i.content for i in items)
    assert all("首页" not in i.content for i in items)
    assert recall.content.count("过热隐患") == 1

    for index, i in enumerate(items, 1):
        print(
            f"[selftest] {index}. {i.title[:22]}… | {i.category:<6} | "
            f"{i.published_at:%m-%d %H:%M} | company={i.company} | kw={i.keywords}"
        )
    print(
        f"[selftest] B6 验收通过：ev_news fixture 解析 {len(items)} 条（≥8），"
        f"与种子同哈希 {len(mirrored)} 条"
    )

    # ------------------------------------------------------------------
    # B13 自测：live 快照离线跑通（不访问网络）
    # 用 B11/B13 存档的第一电动真实快照验证 live selectors + mode 分发
    # ------------------------------------------------------------------
    from pathlib import Path

    live_dir = Path(__file__).resolve().parents[2] / "fixtures" / "html" / "live" / "ev_news"
    snapshot = {p.name: p.read_text(encoding="utf-8") for p in live_dir.glob("*.html")}
    assert "list.html" in snapshot, "live 快照缺失 list.html"

    class _LiveSnapshotSpider(EvNewsSpider):
        """live 模式但 fetch 读快照：全流水线离线可测（不发网络请求）。"""

        max_pages = 1  # B13 快照测试固定第 1 页；多页见 B16 专项自测

        def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
            if is_list:
                return snapshot["list.html"]
            name = url.rstrip("/").rsplit("/", 1)[-1] + ".html"
            return snapshot[name]  # KeyError = 快照缺该详情页（测试资产问题）

    live_spider = _LiveSnapshotSpider(mode=MODE_LIVE)
    live_items, live_stats = live_spider.run()

    # B13 验收：live 快照全流水线 ≥8 条（列表 11 条、快照 11 个详情页）
    assert live_stats.fetched >= 8, live_stats
    assert len(live_items) >= 8, live_stats
    assert all(i.source_url.startswith("https://www.d1ev.com/news/") for i in live_items)
    assert all(isinstance(i.published_at, datetime) and i.published_at.hour > 0 for i in live_items)
    assert all(len(i.content) >= 80 for i in live_items)
    assert all(i.content_hash == BaseSpider.make_hash(i.title, i.source_url) for i in live_items)

    # 混合分类（B4 规则在真实站点内容上依旧工作）
    live_counter = Counter(i.category for i in live_items)
    assert len(live_counter) >= 2, live_counter  # 多分类混合

    # 推荐位/广告/来源行零泄漏（B13 验收重点）
    for i in live_items:
        assert "新闻推荐" not in i.content, i.title
        assert "来源：" not in i.content and "本文地址" not in i.content, i.title
        assert "返回第一电动网" not in i.content, i.title
        assert "转载自" not in i.content, i.title

    # 列表解析专项：相对链接 → 绝对、时间带时分
    rows = selectors.parse_list_live(snapshot["list.html"])
    assert len(rows) >= 8, len(rows)
    assert all(r["url"].startswith("https://www.d1ev.com/news/") for r in rows)

    # 详情解析专项：标题/时间属性/正文容器/企业提取
    first = live_items[0]
    detail_check = selectors.parse_detail_live(snapshot["310950.html"])
    assert detail_check["title"] == "零碳叙事，“宁王”新利器来了", detail_check["title"]
    assert detail_check["datetime"].startswith("2026-08-19 08:09"), detail_check["datetime"]
    assert detail_check["company"] == "宁德时代", detail_check["company"]  # 最早出现优先

    print(
        f"[selftest] live rows={len(rows)} parsed={live_stats.parsed} items={len(live_items)} "
        f"cats={dict(live_counter)}"
    )
    print(
        f"[selftest] live first='{first.title[:22]}…' | {first.category} | "
        f"company={first.company} | content_len={len(first.content)}"
    )
    print("[selftest] B13 验收通过：ev_news live 快照解析（≥8 条全流水线 + 零噪音泄漏）")

    # ------------------------------------------------------------------
    # B16 自测：live 多页翻页（任务卡 B16，离线快照）
    # 验证：分页 URL 生成（/news/list-N）、逐页解析汇总、跨页条目不丢
    # ------------------------------------------------------------------
    paged_snapshots = {k: v for k, v in snapshot.items() if k.startswith("list_")}
    assert "list_2.html" in paged_snapshots and "list_3.html" in paged_snapshots, "B16 缺多页快照"

    class _PagedSnapshotSpider(EvNewsSpider):
        max_pages = 3

        def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
            if is_list:
                return snapshot[f"list.html" if page == 1 else f"list_{page}.html"]
            name = url.rstrip("/").rsplit("/", 1)[-1] + ".html"
            if name in snapshot:
                return snapshot[name]
            return snapshot["310950.html"]  # 复用已有详情快照供流水线消费

    paged = _PagedSnapshotSpider(mode=MODE_LIVE)
    pages_used: list[str] = []

    orig_fetch = paged.fetch

    def record_fetch(url, **kw):
        if kw.get("is_list"):
            pages_used.append(url)
        return orig_fetch(url, **kw)

    paged.fetch = record_fetch
    paged_items, paged_stats = paged.run()

    # 验收：3 页 URL 按序、行数累加、流水线全通
    assert pages_used == [
        "https://www.d1ev.com/news",
        "https://www.d1ev.com/news/list-2",
        "https://www.d1ev.com/news/list-3",
    ], pages_used
    expected_rows = sum(
        len(selectors.parse_list_live(snapshot[f"list_{p}.html" if p > 1 else "list.html"]))
        for p in (1, 2, 3)
    )
    assert paged_stats.fetched == expected_rows, (paged_stats.fetched, expected_rows)
    assert paged_stats.fetched >= 40, paged_stats  # 3 页 × 20 条
    assert len(paged_items) >= 8, paged_stats
    assert all(i.content_hash == BaseSpider.make_hash(i.title, i.source_url) for i in paged_items)
    print(
        f"[selftest] B16 多页：ev_news live 3 页 URL={pages_used[1]} fetched={paged_stats.fetched} "
        f"items={len(paged_items)}"
    )
    print("[selftest] B16 验收通过：live 多页翻页（URL 生成/逐页汇总/跨页流水线）")
