# -*- coding: utf-8 -*-
"""B1 · 采集框架骨架（BaseSpider）

流水线：fetch → parse_list → parse_detail → normalize → hash

约定（见 services/crawler/AGENTS.md）：
- 默认 CRAWL_MODE=fixture：所有网络请求被短路，读 fixtures/html/{source_id}/ 下离线文件
- 去重哈希锁死：sha256(title + source_url)
- 选择器不写在本文件：各数据源的选择器放在对应源的 selectors 模块（B5~B7 落地）
- 控制台日志格式锁死（[db] / [crawl] finished 两行由 B8/B9 入库阶段补充）：
    [crawl] source=ev_news mode=fixture
    [crawl] fetched=20 parsed=18 dropped_short=2
    [clean] done

零第三方依赖：fixture 模式仅用标准库即可运行；live 模式才延迟导入 requests。
"""

from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# B4 规则分类与关键词提取（本目录内模块，纯标准库实现）
from classifier import classify as rule_classify
from classifier import extract_keywords as rule_extract_keywords

# 仓库根目录：services/crawler/base.py → 上两级
REPO_ROOT = Path(__file__).resolve().parents[2]
# 离线种子 HTML 根目录：fixtures/html/{source_id}/list.html、detail*.html
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "html"

# 正文最小长度：清洗后不足 80 字视为无效，计入 dropped_short（任务卡 B2/B3）
MIN_CONTENT_LEN = 80

# 合法分类枚举（契约 packages/schemas/enums.py，只消费不自造）
NEWS_CATEGORIES = ("policy", "company", "market", "tech", "risk", "other")

# 运行模式
MODE_FIXTURE = "fixture"  # 默认：离线读 fixtures，答辩不依赖外网
MODE_LIVE = "live"        # 真实网络采集（能上网时用）


@dataclass
class RawItem:
    """列表页解析出的一条「待抓详情」条目。

    url：live 模式是详情页网址；fixture 模式取其文件名部分，
    映射到 fixtures/html/{source_id}/ 下的同名离线文件。
    """

    url: str
    title: str = ""
    published_at: Optional[datetime] = None  # 列表页能拿到就带上，详情页可覆盖
    extra: dict = field(default_factory=dict)  # 源特有临时字段（栏目名、摘要等）


@dataclass
class NewsItem:
    """normalize 之后的标准化新闻。

    字段对齐契约 packages/schemas/news.py 的 NewsOut（id 等入库字段由 B8 生成）。
    """

    title: str
    published_at: datetime
    source: str  # 即 source_id：miit_policy | ev_news | oem_news
    source_url: str
    category: str  # 只能取 NEWS_CATEGORIES 中的值
    company: Optional[str] = None
    content: str = ""
    keywords: list = field(default_factory=list)
    content_hash: str = ""  # sha256(title+source_url)，normalize 时自动填充
    is_duplicate: bool = False  # 入库阶段（B8）查重后回填


@dataclass
class CrawlStats:
    """一次采集的统计口径（字段名对齐契约 CrawlerTaskOut）。"""

    fetched: int = 0  # 列表页解析出的条目数
    parsed: int = 0  # 详情页解析成功、进入 normalize 的条数（含后续因过短被丢弃的）
    dropped_short: int = 0  # 正文过短被丢弃的条数
    inserted: int = 0  # 入库新增（B8 填写）
    duplicated: int = 0  # 判定重复（B8 填写）


class BaseSpider(ABC):
    """采集器基类：子类只需实现 parse_list / parse_detail（B5~B7 各源落地）。

    用法示例：
        class EvNewsSpider(BaseSpider):
            source_id = "ev_news"
            list_url = "https://example.com/news/list"

            def parse_list(self, html): ...    # 选择器来自该源的 selectors 模块
            def parse_detail(self, html, item): ...
    """

    source_id: str = ""  # 数据源标识（miit_policy | ev_news | oem_news），子类必须覆写
    list_url: str = ""  # live 模式列表页地址；fixture 模式固定映射 list.html

    request_interval: float = 1.0  # 限速：相邻请求最小间隔秒数（任务卡 B10，仅 live 生效）
    request_timeout: float = 10.0  # 网络请求超时秒数（仅 live 生效）
    use_browser: bool = False  # live 模式走 Selenium 无头浏览器（任务卡 B11：WAF 站点用）
    max_pages: int = 1  # live 模式列表翻页数（任务卡 B16）；fixture 模式恒 1 页

    def __init__(self, mode: str = MODE_FIXTURE) -> None:
        if not self.source_id:
            raise ValueError("子类必须定义 source_id（miit_policy | ev_news | oem_news）")
        self.mode = mode  # 运行模式：fixture（默认）/ live
        self._last_request_at = 0.0  # 上次网络请求时间戳，用于限速

    # ---------- 流水线入口 ----------

    def run(self) -> tuple[list[NewsItem], CrawlStats]:
        """执行完整流水线，返回 (标准化新闻列表, 统计)。

        入库（B8）与 CrawlResult 封装（B9）由上层负责，本方法只到 [clean] done。
        单条详情失败只跳过该条，不中断整个源。
        """
        # 固定格式日志：第 1 行
        print(f"[crawl] source={self.source_id} mode={self.mode}")

        stats = CrawlStats()

        # 1) 抓列表页（live 支持多页翻页，任务卡 B16）→ 汇总待抓条目
        raw_items: list[RawItem] = []
        for page, list_html in enumerate(self._list_page_htmls(self._effective_max_pages()), start=1):
            rows = self.parse_list(list_html)
            if not rows:
                break
            raw_items.extend(rows)
            if self.mode == MODE_LIVE and len(raw_items) > 0:
                print(f"[crawl] list page {page} rows={len(rows)} total={len(raw_items)}")
        stats.fetched = len(raw_items)

        items: list[NewsItem] = []
        for raw in raw_items:
            # 2) 逐条抓详情页并解析
            try:
                detail_html = self.fetch(raw.url)
                parsed = self.parse_detail(detail_html, raw)
            except Exception as exc:  # 单条失败不影响其他条目
                print(f"[crawl] detail failed url={raw.url} error={exc}")
                continue
            if not parsed:
                continue
            stats.parsed += 1

            # 3) 清洗、对齐契约字段、计算去重哈希
            item = self.normalize(parsed)
            if item is None:
                stats.dropped_short += 1
                continue
            items.append(item)

        # 固定格式日志：第 2、3 行
        print(
            f"[crawl] fetched={stats.fetched} "
            f"parsed={stats.parsed} dropped_short={stats.dropped_short}"
        )
        print("[clean] done")
        return items, stats

    # ---------- 流水线各环节 ----------

    def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
        """取页面 HTML。fixture 模式读本地离线文件（网络被短路）；live 模式才发请求。

        is_list=True 表示列表页：fixture 模式映射 fixtures/html/{source_id}/list.html
        （多页时第 n 页读 list_{n}.html，任务卡 B16）。
        live 模式：use_browser=True 的源（如工信部，创宇盾 WAF）走 Selenium 渲染，
        其余走 requests + 浏览器头。
        page：列表页页码（fixture 多页文件名约定），live 模式不参与 URL 构造。
        """
        if self.mode == MODE_FIXTURE:
            return self._fetch_fixture(url, is_list=is_list, page=page)
        if self.use_browser:
            return self._fetch_live_browser(url)
        return self._fetch_live(url)

    # ---------- 多页翻页（任务卡 B16，live 生效） ----------

    def _effective_max_pages(self) -> int:
        """live 模式返回 max_pages；fixture 模式恒 1 页（答辩模式零影响）。"""
        return self.max_pages if self.mode == MODE_LIVE else 1

    def _list_url_for_page(self, page: int) -> str | None:
        """第 page 页列表页 URL。默认仅第 1 页（list_url）；子类翻页覆写此方法。"""
        if page <= 1:
            return self.list_url
        return None  # 无更多页

    def _list_page_htmls(self, max_pages: int) -> Iterator[str]:
        """逐页产出列表页 HTML。第 1 页失败向上抛（B10：配错 URL 冒泡给源级容错）；
        第 n>1 页失败记日志停止翻页，不影响已收集条目。
        """
        for page in range(1, max_pages + 1):
            url = self._list_url_for_page(page)
            if url is None:
                break
            try:
                yield self.fetch(url, is_list=True, page=page)
            except Exception as exc:
                if page == 1:
                    raise
                print(f"[crawl] list page {page} failed error={exc}, stop paging")
                break

    def _fetch_fixture(self, url: str, *, is_list: bool, page: int = 1) -> str:
        """离线模式：url 映射到 fixtures/html/{source_id}/ 下同名文件并读取。"""
        if is_list:
            name = "list.html" if page == 1 else f"list_{page}.html"  # 多页约定 list_2.html...
        else:
            # 详情页取 url 文件名部分（如 https://x.com/n/1 → 1.html 需源侧配合命名）
            name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "detail.html"
        path = FIXTURE_ROOT / self.source_id / name
        if not path.exists():
            # URL 不带扩展名时，允许 fixtures 文件补 .html 后缀（如 /n/recall-12w → recall-12w.html）
            path = FIXTURE_ROOT / self.source_id / f"{name}.html"
        if not path.exists():
            raise FileNotFoundError(f"fixture 文件不存在: {path}")
        return path.read_text(encoding="utf-8")

    # live 模式默认请求头（任务卡 B11）：真实站点普遍拦截 python-requests 默认 UA
    # （实测：第一电动对裸 requests 403，带浏览器头 200）
    LIVE_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    def _fetch_live(self, url: str) -> str:
        """真实网络请求（限速 + 浏览器头 + 超时）。fixture 模式下永远不会执行到这里。"""
        import requests  # 延迟导入：保证 fixture 模式零第三方依赖

        self._throttle()  # 限速：距上次请求不足 request_interval 则等待
        response = requests.get(url, headers=self.LIVE_HEADERS, timeout=self.request_timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def _fetch_live_browser(self, url: str) -> str:
        """Selenium 无头浏览器取数（任务卡 B11：创宇盾等 WAF 站点）。

        同样走 _throttle 限速（B10 契约对浏览器请求同样成立）；
        browser 模块懒加载 selenium，未安装时抛 BrowserUnavailableError
        → runner 源级容错接住 → job_log error，其他源不受影响。
        """
        import browser

        self._throttle()
        return browser.fetch(url)

    def _throttle(self) -> None:
        """限速（任务卡 B10）：保证相邻网络请求间隔至少 request_interval 秒。"""
        now = time.monotonic()
        wait = self.request_interval - (now - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    @abstractmethod
    def parse_list(self, html: str) -> list[RawItem]:
        """解析列表页 → 待抓详情条目列表。选择器写在对应源的 selectors 模块。"""

    @abstractmethod
    def parse_detail(self, html: str, item: RawItem) -> Optional[dict]:
        """解析详情页 → 原始字段 dict。

        返回 dict 至少含 content 与 source_url；title / published_at / company
        缺省时 normalize 会用列表页带来的值或默认值兜底。
        """

    # ---------- 标准化 / 去重 / 清洗 ----------

    def normalize(self, raw: dict) -> Optional[NewsItem]:
        """把详情页原始字段清洗、对齐契约字段，并计算去重哈希。

        无效条目（缺 title/source_url，或正文清洗后不足 MIN_CONTENT_LEN 字）
        返回 None，由上层计入 dropped_short。
        """
        title = self.clean_text(str(raw.get("title") or ""))
        source_url = str(raw.get("source_url") or "").strip()
        if not title or not source_url:
            return None  # 缺关键字段视为无效

        content = self.clean_html(raw.get("content") or "")
        if len(content) < MIN_CONTENT_LEN:
            return None  # 正文过短：无效情报，丢弃

        published_at = self.parse_datetime(raw.get("published_at")) or datetime.now()

        # 分类钩子（B4 覆写）：骨架默认 other；返回非法枚举值时兜底 other
        category = self.classify(title, content)
        if category not in NEWS_CATEGORIES:
            category = "other"

        company = str(raw.get("company") or "").strip() or None

        return NewsItem(
            title=title,
            published_at=published_at,
            source=self.source_id,
            source_url=source_url,
            category=category,
            company=company,
            content=content,
            keywords=self.extract_keywords(title, content),
            content_hash=self.make_hash(title, source_url),
        )

    @staticmethod
    def make_hash(title: str, source_url: str) -> str:
        """去重哈希（契约锁死不可改）：sha256(title + source_url) 十六进制摘要。"""
        return hashlib.sha256(f"{title}{source_url}".encode("utf-8")).hexdigest()

    def clean_text(self, text: str) -> str:
        """压缩空白：任意连续空白字符合并为单个空格并去首尾。"""
        return re.sub(r"\s+", " ", str(text)).strip()

    def clean_html(self, html: str) -> str:
        """清洗 HTML → 纯文本（B3 强化版：BeautifulSoup 去导航残渣 + 正文密度）。

        已安装 beautifulsoup4 时走 cleaner 的密度抽取；未安装时回退 B1 正则版，
        保证 base.py 在零依赖环境（如 CI 冒烟）依然可用。
        """
        try:
            from cleaner import extract_main_text  # 延迟导入：可选依赖
        except ImportError:
            extract_main_text = None
        if extract_main_text is not None:
            text = extract_main_text(html)
            # 密度抽取拿不到足够正文时（极简 HTML），退回全量清洗兜底
            if len(text) >= MIN_CONTENT_LEN:
                return text
            from cleaner import clean_html as full_clean
            return full_clean(html)
        # 正则兜底版（无 bs4 环境）
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", str(html))
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        return self.clean_text(text)

    @staticmethod
    def parse_datetime(value) -> Optional[datetime]:
        """尽量把各种日期值解析成 datetime（时区信息去掉，库表用本地时间）；失败返回 None。"""
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        if not value:
            return None
        text = str(value).strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",  # 工信部详情页「发布时间：2026-08-04 17:10」（B12）
            "%Y年%m月%d日",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:  # ISO8601 兜底（含带时区的 2026-08-18T09:00:00+08:00）
            dt = datetime.fromisoformat(text)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            return None

    # ---------- 分类 / 关键词钩子（任务卡 B4：规则分类已实现） ----------

    def classify(self, title: str, content: str) -> str:
        """分类（B4 规则）：风险词（召回/停产/断供等）命中必为 risk；否则按关键词计分。"""
        return rule_classify(title, content)

    def extract_keywords(self, title: str, content: str) -> list:
        """关键词提取（B4 规则）：命中词按首现排序、去子串，最多 5 个。"""
        return rule_extract_keywords(title, content)


# ---------- B1 自测：不访问网络、不依赖 fixtures 文件 ----------

if __name__ == "__main__":
    # 内置迷你数据：3 条列表，其中第 3 条正文过短应被丢弃
    DEMO_LIST = "\n".join(
        [
            "某车企宣布召回12万辆新能源车|https://example.com/n/1|2026-08-18",
            "工信部就动力电池回收利用公开征求意见|https://example.com/n/2|2026-08-17",
            "超短无效情报|https://example.com/n/3|2026-08-16",
        ]
    )
    # 详情页含 script/style 干扰，验证清洗
    DEMO_DETAIL = (
        "<html><head><style>.ad{display:none}</style>"
        "<script>alert('x')</script></head>"
        "<body><p>某新能源汽车企业今日宣布召回12万辆汽车，初步原因为电池模组存在过热隐患。"
        "公司称将免费更换相关零部件，并同步通知经销商与车主。此次召回可能影响品牌信誉及供应链订单。</p>"
        "</body></html>"
    )
    DEMO_DETAIL_SHORT = "<p>这条正文太短，会被丢弃。</p>"

    class _DemoSpider(BaseSpider):
        """自测用最小采集器：覆写 fetch 注入内置 HTML，验证流水线编排本身。"""

        source_id = "demo_b1"

        def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
            if is_list:
                return DEMO_LIST
            return DEMO_DETAIL_SHORT if url.endswith("/3") else DEMO_DETAIL

        def parse_list(self, html: str) -> list[RawItem]:
            # 极简「选择器」：每行一条 标题|url|日期
            items = []
            for line in html.strip().splitlines():
                title, url, day = (part.strip() for part in line.split("|"))
                items.append(
                    RawItem(url=url, title=title, published_at=datetime.strptime(day, "%Y-%m-%d"))
                )
            return items

        def parse_detail(self, html: str, item: RawItem) -> Optional[dict]:
            return {
                "title": item.title,
                "source_url": item.url,
                "published_at": item.published_at,
                "content": html,
            }

    spider = _DemoSpider(mode=MODE_FIXTURE)
    items, stats = spider.run()

    # 断言式自检：流水线贯通、清洗生效、哈希符合契约
    assert stats.fetched == 3, stats
    assert stats.parsed == 3 and stats.dropped_short == 1, stats
    assert len(items) == 2, stats
    assert all(len(i.content) >= MIN_CONTENT_LEN for i in items)
    assert "alert" not in items[0].content and "display" not in items[0].content
    assert items[0].content_hash == BaseSpider.make_hash(items[0].title, items[0].source_url)
    assert items[0].published_at == datetime(2026, 8, 18)
    assert items[0].category == "risk"  # B4 硬规则：含「召回」必为 risk
    assert "召回" in items[0].keywords  # B4 关键词提取生效

    print(f"[selftest] ok items={len(items)} hash_example={items[0].content_hash[:12]}...")

    # ---------- B10 专项验收：限速（1秒/请求）+ 容错（单条失败只跳过该条） ----------

    # 1) 默认限速间隔必须是 1.0 秒（任务卡 B10 契约值）
    assert BaseSpider.request_interval == 1.0

    # 2) _throttle 计时实测：第 1 次不等待，第 2 次应等待约 1 秒
    throttle_spider = _DemoSpider(mode=MODE_FIXTURE)
    t0 = time.monotonic()
    throttle_spider._throttle()
    throttle_spider._throttle()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.99, f"限速未生效: {elapsed:.3f}s"
    assert elapsed < 3.0, f"限速异常（等待过久）: {elapsed:.3f}s"
    print(f"[selftest] throttle ok interval=1.0s elapsed={elapsed:.2f}s")

    # 3) _fetch_live 全链路（mock requests，零真实网络）：
    #    限速在 live 路径生效 + 超时参数传递 + 非 2xx 正确抛错（供源级容错接住）
    import sys
    import types

    class _FakeResponse:
        def __init__(self, text, status_code=200, apparent_encoding="utf-8"):
            self.text = text
            self.status_code = status_code
            self.apparent_encoding = apparent_encoding
            self.encoding = None

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    fake_calls: list = []
    fake_responses: list = []

    def _fake_get(url, headers=None, timeout=None):
        fake_calls.append((url, timeout, headers))
        return fake_responses.pop(0)

    fake_requests = types.ModuleType("requests")
    fake_requests.get = _fake_get
    saved_requests = sys.modules.get("requests")
    sys.modules["requests"] = fake_requests
    try:
        live = _DemoSpider(mode=MODE_LIVE)
        fake_responses.extend(
            [
                _FakeResponse("<html><body>live page A</body></html>"),
                _FakeResponse("<html><body>live page B</body></html>"),
            ]
        )
        t0 = time.monotonic()
        page_a = live._fetch_live("https://example.com/live/a")
        page_b = live._fetch_live("https://example.com/live/b")
        elapsed = time.monotonic() - t0
        assert "live page A" in page_a and "live page B" in page_b
        assert elapsed >= 0.99, f"live 路径限速未生效: {elapsed:.3f}s"
        assert all(t == 10.0 for _, t, _ in fake_calls), fake_calls  # 超时参数已传递
        assert all(h and "Mozilla" in h["User-Agent"] for _, _, h in fake_calls), fake_calls
        assert live._last_request_at > 0

        # 404 → raise_for_status 抛错冒泡（runner 的源级容错正是接住这个异常）
        fake_responses.append(_FakeResponse("Not Found", status_code=404))
        try:
            live._fetch_live("https://example.com/live/404")
            raise AssertionError("404 应当抛出异常")
        except RuntimeError as exc:
            assert "404" in str(exc)
        print(
            f"[selftest] live fetch ok elapsed={elapsed:.2f}s timeout=10s "
            f"browser-ua=headers[User-Agent] http-error-propagates"
        )
    finally:
        if saved_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = saved_requests

    # 4) 容错：单条详情请求失败 → 只跳过该条，其余条目照常走完流水线
    class _FlakyDetailSpider(_DemoSpider):
        """B10 自测：第 2 条详情请求失败（模拟网络错误），第 3 条正文过短。"""

        source_id = "demo_b10"

        def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
            if is_list:
                return DEMO_LIST
            if url.endswith("/2"):
                raise ConnectionError("simulated connection reset")
            return DEMO_DETAIL_SHORT if url.endswith("/3") else DEMO_DETAIL

    flaky = _FlakyDetailSpider(mode=MODE_FIXTURE)
    flaky_items, flaky_stats = flaky.run()
    assert flaky_stats.fetched == 3, flaky_stats
    assert flaky_stats.parsed == 2 and flaky_stats.dropped_short == 1, flaky_stats
    assert len(flaky_items) == 1 and flaky_items[0].source_url == "https://example.com/n/1"
    print("[selftest] flaky detail ok（失败1条仅跳过，其余照常进入流水线）")
    print("[selftest] B10 限速+容错 专项验收通过")
