# -*- coding: utf-8 -*-
"""B15 前置 · live 取数分流逻辑验证（纯离线，零网络）

验证目标（三站点在 live 模式下的取数通道，B11~B14 快照取证结论）：
- miit_policy（use_browser=True，创宇盾 WAF）  → 列表+详情 全部走 Selenium 浏览器
- ev_news（use_browser=False，无 fetch 覆写）  → 列表+详情 全部走 requests+浏览器头
- oem_news（覆写 fetch，Vue API 列表 + SSR 详情）→ 列表走浏览器（且仅列表），详情走 requests

做法：给 spider 实例打桩替换 _fetch_live / _fetch_live_browser，
记录每次调用（含 is_list 标志）并返回已存档的 live 快照 HTML（缺详情页抛
KeyError 模拟单条失败 → 容错跳过），随后跑完整流水线，断言：
- 各源分流通道调用次数 / is_list 标志符合预期（browser 通道不滥用）
- 列表页永远走 is_list=True（详情页永远 False，杜绝错位）
- 快照离线产出条目数达标（miit≥5 / ev≥8 / oem≥5），证明分流后的解析正确
- requests 与浏览器两条通道总调用与快照行数严格吻合

用法：python services/crawler/test_routing_live.py（退出码 0 = 通过）
"""

from __future__ import annotations

import sys
from pathlib import Path

CRAWLER_DIR = Path(__file__).resolve().parent
REPO_ROOT = CRAWLER_DIR.parents[1]
for _path in (str(CRAWLER_DIR), str(REPO_ROOT / "packages")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from base import MODE_LIVE, BaseSpider  # noqa: E402
from ev_news import EvNewsSpider  # noqa: E402
from miit_policy import MiitPolicySpider  # noqa: E402
from oem_news import OemNewsSpider  # noqa: E402

LIVE_ROOT = REPO_ROOT / "fixtures" / "html" / "live"


def build_stub(source_id: str, list_url: str):
    """构造记录型打桩：替换 _fetch_live 与 _fetch_live_browser 为快照读取。

    返回 (stub, channel_calls)；channel_calls 元素 = {"channel", "url"}。
    底层取数方法不接收 is_list（分流决策在 fetch()），stub 按 URL 识别列表页；
    is_list 分流由 fetch 包装器另行记录（见 run_spider）。
    缺详情页快照 → KeyError（模拟单条抓取失败，验证容错且不影响分流计数）。
    """
    snap_dir = LIVE_ROOT / source_id
    list_name = "list_rendered.html" if source_id == "oem_news" else "list.html"
    list_html = (snap_dir / list_name).read_text(encoding="utf-8")
    detail_cache = {p.name: p.read_text(encoding="utf-8") for p in snap_dir.glob("*.html")}

    channel_calls: list[dict] = []

    def _resolve(url: str) -> str:
        if url == list_url:
            return list_html
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if not name.endswith(".html"):
            name += ".html"
        return detail_cache[name]

    def _req(url: str) -> str:
        channel_calls.append({"channel": "requests", "url": url})
        return _resolve(url)

    def _brw(url: str) -> str:
        channel_calls.append({"channel": "browser", "url": url})
        return _resolve(url)

    return _req, _brw, channel_calls


def run_spider(spider, source_id: str):
    """对实例打桩 → 跑完整流水线 → 返回 (items, stats, fetch_calls, channel_calls)。

    fetch_calls 记录每次 fetch 的「(url, is_list) → 实际通道」决策，
    即验证的对象：分流逻辑在 fetch() 层，底层取数方法不感知 is_list。
    """
    _req, _brw, channel_calls = build_stub(source_id, spider.list_url)
    spider._fetch_live = _req
    spider._fetch_live_browser = _brw

    # 路由测试聚焦分流决策：固定单页，翻页由 B16 专项（ev_news.py）覆盖
    spider.max_pages = 1
    if source_id == "miit_policy":
        # miit 覆写了 live 点击翻页（会触发真实浏览器）→ 换回基类 URL 翻页路径
        import types

        spider._list_page_htmls = types.MethodType(
            lambda self, n: BaseSpider._list_page_htmls(self, n), spider
        )

    fetch_calls: list[dict] = []
    orig_fetch = spider.fetch

    def _fetch_wrapper(url: str, *, is_list: bool = False, page: int = 1) -> str:
        n_before = len(channel_calls)
        try:
            html = orig_fetch(url, is_list=is_list)
        finally:
            # 无论成功与否都记录决策（详情快照缺失 → KeyError 也在 finally 记录，
            # channel 标记 none，便于断言「全部 fetch 都走了正确的通道」）
            if len(channel_calls) > n_before:
                channel = channel_calls[n_before]["channel"]
            else:
                channel = "none"
            fetch_calls.append({"url": url, "is_list": is_list, "channel": channel})
        return html

    spider.fetch = _fetch_wrapper
    items, stats = spider.run()
    return items, stats, fetch_calls, channel_calls


def main() -> None:
    # ---------- 1) miit_policy：WAF 站点，列表+详情全走浏览器 ----------
    miit = MiitPolicySpider(mode=MODE_LIVE)
    assert miit.use_browser, "miit 应声明 use_browser=True（创宇盾 WAF）"
    miit_items, miit_stats, miit_fetch, miit_ch = run_spider(miit, "miit_policy")
    miit_browser = [c for c in miit_fetch if c["channel"] == "browser"]
    miit_req = [c for c in miit_fetch if c["channel"] == "requests"]
    assert len(miit_browser) == miit_stats.fetched + 1, (len(miit_browser), miit_stats.fetched)  # 列表1次 + 每条详情
    assert len(miit_req) == 0, f"miit 不应走 requests，实际 {len(miit_req)} 次"
    assert miit_fetch[0]["is_list"] is True and all(not c["is_list"] for c in miit_fetch[1:])
    assert len(miit_items) >= 5, f"miit live 条目不足: {len(miit_items)}"
    print(f"[routing] miit_policy  列表+详情→browser  browser={len(miit_browser)} requests=0  "
          f"rows={miit_stats.fetched} items={len(miit_items)}")

    # ---------- 2) ev_news：普通站点，列表+详情全走 requests ----------
    ev = EvNewsSpider(mode=MODE_LIVE)
    assert not ev.use_browser, "ev_news 不应声明 use_browser"
    ev_items, ev_stats, ev_fetch, ev_ch = run_spider(ev, "ev_news")
    ev_req = [c for c in ev_fetch if c["channel"] == "requests"]
    ev_browser = [c for c in ev_fetch if c["channel"] == "browser"]
    assert len(ev_req) == ev_stats.fetched + 1, len(ev_req)
    assert len(ev_browser) == 0, f"ev_news 不应走浏览器，实际 {len(ev_browser)} 次"
    assert ev_fetch[0]["is_list"] is True and all(not c["is_list"] for c in ev_fetch[1:])
    assert len(ev_items) >= 8, f"ev_news live 条目不足: {len(ev_items)}"
    print(f"[routing] ev_news      列表+详情→requests browser=0 requests={len(ev_req)}  "
          f"rows={ev_stats.fetched} items={len(ev_items)}")

    # ---------- 3) oem_news：Vue 列表 + SSR 详情，分流各司其职 ----------
    oem = OemNewsSpider(mode=MODE_LIVE)
    oem_items, oem_stats, oem_fetch, oem_ch = run_spider(oem, "oem_news")
    oem_browser = [c for c in oem_fetch if c["channel"] == "browser"]
    oem_req = [c for c in oem_fetch if c["channel"] == "requests"]
    assert len(oem_browser) == 1 and oem_browser[0]["is_list"] is True, (
        f"oem 列表页应且仅走一次浏览器，实际 {len(oem_browser)} 次"
    )
    assert len(oem_req) == oem_stats.fetched, (
        f"oem 每条详情走 requests，实际 {len(oem_req)} vs 行数 {oem_stats.fetched}"
    )
    assert all(not c["is_list"] for c in oem_req), "oem 详情请求 is_list 必须为 False"
    assert len(oem_items) >= 5, f"oem_news live 条目不足: {len(oem_items)}"
    print(f"[routing] oem_news     列表→browser 详情→requests browser=1 requests={len(oem_req)}  "
          f"rows={oem_stats.fetched} items={len(oem_items)} (dropped_short={oem_stats.dropped_short})")

    # ---------- 4) 汇总：URL 域与设计一致 ----------
    assert all(
        i.source_url.startswith(("https://www.miit.gov.cn", "https://www.d1ev.com/news", "https://www.byd.com/cn/detail"))
        for i in (miit_items + ev_items + oem_items)
    )
    print("[routing] B15 前置分流验证通过：三站点取数通道与 is_list 标志全部符合设计")


if __name__ == "__main__":
    main()
