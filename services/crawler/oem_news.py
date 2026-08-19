# -*- coding: utf-8 -*-
"""B7 · 数据源 3：oem_news（XX汽车新闻中心·车企动态）

三件套：本文件（spider 编排）+ selectors_oem_news.py（DOM 选择器）
+ fixtures/html/oem_news/（离线种子：list.html + 6 个详情页）。

验收（任务卡 B7）：fixture 至少解析出 5 条 → 自测 6 条全通过。

与种子的关系（答辩关键设计）：其中 2 条新闻与 fixtures/seed/news.json 同题同 URL
（「新款纯电SUV」「智驾NOA」→ content_hash 一致），保证：
- 中台 mock 预置的种子数据与本地爬虫插入的数据可跨模式去重（B2 生效）
-车企动态 source=oem_news + company=XX汽车 恒定，供前端按企业筛选
"""

from __future__ import annotations

import selectors_oem_news as selectors
from base import MODE_FIXTURE, MODE_LIVE, BaseSpider, RawItem


class OemNewsSpider(BaseSpider):
    """车企新闻中心源：列表页（标题+链接+圆点日期）→ 详情页（标题+日期时间+正文）。

    与前两个源的差异：
    - 日期为站点特有圆点格式「2026.08.13」，由 selectors 规范化为 ISO
    - 列表页只有日期、详情页才有时间（详情时间优先）
    - company 恒为站点主体（官方新闻中心，不需要从正文提取）
    - fixture/live 双轨 selectors（B14）：按 self.mode 分发
    - live 取数分流（B14 快照取证）：列表卡片是 Vue 挂载后经 API 加载
      （requests 原始 HTML 只有「暂无数据」占位）→ 列表页走 Selenium 渲染；
      详情页服务端渲染 → requests 即可（快且轻，同一站点不必全走浏览器）
    DOM 细节全部委托 selectors 模块，本类只做编排与字段映射。
    """

    source_id = "oem_news"
    # live 入口：比亚迪官方新闻中心·中国站
    # 注意：byd.com.cn/news.html 会重定向到欧洲站，真实入口是 byd.com/cn/news
    list_url = "https://www.byd.com/cn/news"

    def fetch(self, url: str, *, is_list: bool = False) -> str:
        """live 分流：列表页 Selenium 渲染（Vue API 加载卡片），详情页 requests。"""
        if self.mode == MODE_FIXTURE:
            return self._fetch_fixture(url, is_list=is_list)
        if is_list:
            return self._fetch_live_browser(url)  # 列表：Vue API 渲染，必须浏览器
        return self._fetch_live(url)  # 详情：服务端渲染，requests 足够

    def parse_list(self, html: str) -> list[RawItem]:
        """列表页 → 待抓条目（fixture/live 结构不同，分发到对应 selectors）。"""
        parse = selectors.parse_list_live if self.mode == MODE_LIVE else selectors.parse_list
        items: list[RawItem] = []
        for row in parse(html):
            published = self.parse_datetime(row["date"]) if row["date"] else None
            items.append(RawItem(url=row["url"], title=row["title"], published_at=published))
        return items

    def parse_detail(self, html: str, item: RawItem) -> dict | None:
        """详情页 → normalize 待消费的字段（日期时间取详情页，缺失退回列表页）。"""
        parse = selectors.parse_detail_live if self.mode == MODE_LIVE else selectors.parse_detail
        detail = parse(html)
        if detail is None:
            return None
        return {
            "title": detail["title"] or item.title,
            "source_url": item.url,
            "published_at": detail["datetime"] or item.published_at,
            "content": detail["content_html"],
            "company": detail["company"],  # 车企新闻中心：恒为 XX汽车
        }


# ---------------------------------------------------------------------------
# B7 自测：fixture 模式跑通全流水线（不访问网络）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from collections import Counter
    from datetime import datetime

    from base import REPO_ROOT

    spider = OemNewsSpider(mode=MODE_FIXTURE)
    items, stats = spider.run()

    # B7 验收：fixture 至少 5 条，全部解析成功、无过短丢弃
    assert stats.fetched >= 5, stats
    assert stats.parsed == 6 and stats.dropped_short == 0, stats
    assert len(items) == 6, stats

    # 契约字段
    assert all(i.source == "oem_news" for i in items)
    assert all(len(i.content) >= 80 for i in items)
    assert all(isinstance(i.published_at, datetime) for i in items)
    assert all(i.content_hash == BaseSpider.make_hash(i.title, i.source_url) for i in items)

    # 车企新闻中心：company 恒为站点主体
    assert all(i.company == "XX汽车" for i in items)

    # 混合分类（B4 规则）：company 3 / tech 2 / market 1；本源无 risk（召回在 ev_news）
    counter = Counter(i.category for i in items)
    assert counter == {"company": 3, "tech": 2, "market": 1}, counter

    # 圆点日期规范化 + 详情时间优先：SUV 新闻 2026.08.13 19:00（与种子时刻一致）
    suv = next(i for i in items if "SUV" in i.title)
    assert suv.published_at == datetime(2026, 8, 13, 19, 0), suv.published_at
    assert "预售" in suv.keywords or "新车" in suv.keywords, suv.keywords

    # 与组长种子数据同题同 URL → content_hash 一致（跨模式去重的关键）
    seed = json.loads((REPO_ROOT / "fixtures" / "seed" / "news.json").read_text(encoding="utf-8"))
    seed_hashes = {
        BaseSpider.make_hash(row["title"], row["source_url"])
        for row in seed
        if row["source"] == "oem_news"
    }
    mirrored = [i for i in items if i.content_hash in seed_hashes]
    assert len(mirrored) == 2, [i.title for i in mirrored]
    # 镜像条目分类必须与种子一致（company / tech）
    mirrored_by_title = {i.title: i.category for i in mirrored}
    for row in seed:
        if row["source"] == "oem_news":
            assert mirrored_by_title[row["title"]] == row["category"]

    # 清洗防泄漏：元信息行/相关新闻/媒体资料/导航不混入正文；段落不重复
    assert all("发布日期" not in i.content and "来源" not in i.content for i in items)
    assert all("相关新闻" not in i.content and "媒体资料" not in i.content for i in items)
    assert all("首页" not in i.content for i in items)
    assert suv.content.count("预售") >= 1 and suv.content.count("CLTC") == 1

    for index, i in enumerate(items, 1):
        print(
            f"[selftest] {index}. {i.title[:22]}… | {i.category:<7} | "
            f"{i.published_at:%m-%d %H:%M} | company={i.company} | kw={i.keywords}"
        )
    print(
        f"[selftest] B7 验收通过：oem_news fixture 解析 {len(items)} 条（≥5），"
        f"与种子同哈希 {len(mirrored)} 条"
    )

    # ------------------------------------------------------------------
    # B14 自测：live 快照离线跑通（不访问网络）
    # 用渲染快照（list_rendered.html，Selenium 渲染后存档）+ 9 个详情页快照
    # 验证 live selectors + mode 分发 + fetch 分流逻辑
    # ------------------------------------------------------------------
    from pathlib import Path

    import re

    live_dir = Path(__file__).resolve().parents[2] / "fixtures" / "html" / "live" / "oem_news"
    snapshot = {p.name: p.read_text(encoding="utf-8") for p in live_dir.glob("detail*.html")}
    assert snapshot, "live 快照缺失 detail*.html"
    list_rendered = (live_dir / "list_rendered.html").read_text(encoding="utf-8")

    class _LiveSnapshotSpider(OemNewsSpider):
        """live 模式但 fetch 读快照：全流水线离线可测（不发网络请求）。

        列表 → list_rendered.html（Selenium 渲染版）；详情 → detailN.html。
        快照只存了 9 个详情页，列表其余条目 fetch 抛 KeyError → 单条容错跳过。
        """

        def fetch(self, url: str, *, is_list: bool = False) -> str:
            if is_list:
                return list_rendered
            name = url.rstrip("/").rsplit("/", 1)[-1] + ".html"  # /cn/detail632 → detail632.html
            return snapshot[name]

    live_spider = _LiveSnapshotSpider(mode=MODE_LIVE)
    live_items, live_stats = live_spider.run()

    # B14 验收：live 快照全流水线 ≥5 条有效长文（海报式快讯 dropped_short 可有）
    assert live_stats.fetched >= 5, live_stats
    assert len(live_items) >= 5, live_stats
    assert all(i.source_url.startswith("https://www.byd.com/cn/detail") for i in live_items)
    assert all(isinstance(i.published_at, datetime) and i.published_at.hour > 0 for i in live_items)
    assert all(len(i.content) >= 80 for i in live_items)
    assert all(i.company == "比亚迪" for i in live_items)  # live 站点主体
    assert all(i.content_hash == BaseSpider.make_hash(i.title, i.source_url) for i in live_items)

    # 海报式快讯（销量战报：正文+大图）：允许 dropped_short > 0（契约行为不造假）
    if live_stats.dropped_short:
        print(f"[selftest] 海报式快讯 dropped_short={live_stats.dropped_short}（契约行为）")

    # 清洗防泄漏：返回列表/栏目名/日期不混入正文
    for i in live_items:
        assert "返回列表" not in i.content, i.title
        assert "公司新闻" not in i.content, i.title
        assert "发布于" not in i.content, i.title

    # 列表解析专项：渲染快照卡片数、URL/日期格式
    rows = selectors.parse_list_live(list_rendered)
    assert len(rows) >= 5, len(rows)
    assert all(r["url"].startswith("https://www.byd.com/cn/detail") for r in rows)
    assert all(re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", r["date"]) for r in rows), rows[:3]

    # 详情解析专项：标题/时间（发布于 → ISO 去秒）/company
    detail_check = selectors.parse_detail_live(snapshot["detail620.html"])
    assert detail_check["title"] == "比亚迪发布2025年ESG报告，积极履行可持续发展承诺"
    assert detail_check["datetime"] == "2026-04-01 10:32", detail_check["datetime"]
    assert detail_check["company"] == "比亚迪"

    live_counter = Counter(i.category for i in live_items)
    print(
        f"[selftest] live rows={len(rows)} parsed={live_stats.parsed} "
        f"items={len(live_items)} dropped={live_stats.dropped_short} cats={dict(live_counter)}"
    )
    for i in live_items[:3]:
        print(
            f"[selftest] live {i.title[:24]}… | {i.category:<7} | "
            f"{i.published_at:%m-%d %H:%M} | len={len(i.content)}"
        )
    print("[selftest] B14 验收通过：oem_news live 快照解析（≥5 条全流水线 + fetch 分流）")
