# -*- coding: utf-8 -*-
"""B6/B13 · ev_news 源选择器（第一电动网资讯频道）

只放 DOM 解析，不放业务逻辑（业务在 ev_news.py，流水线在 base.py）。
live 模式若站点改版，只改本文件的选择器常量，不动其他代码。

两套结构（fixture 演示 / live 真实站点，B13 快照实测）：
- fixture（fixtures/html/ev_news/ 种子，演示与答辩）：
  列表 .news-list .news-item：a.news-title（绝对链接+标题）+ .pub-time
  详情 h1.news-title / .meta（时间+来源行）/ .article-body（正文）
- live（https://www.d1ev.com/news，B11 快照取证）：
  列表 .ws-news .article--wraped：.article--content .article_p a（相对链接+标题）
        + .article--time time（datetime 属性「2026-08-19 08:09」）
  详情 .ws-title h1（标题）/ .ws-title-infor time（datetime 属性）/
        div[id^=showall]（正文容器；来源行/返回链接/广告在其内部需剔除）
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# 站点域名：live 相对链接在此拼接（fixture 种子的链接全为绝对地址，不经此分支）
BASE_URL = "https://www.d1ev.com"

# 列表页选择器（fixture 演示结构）
LIST_ITEM_SEL = ".news-list .news-item"   # 单条新闻条目
LIST_TITLE_SEL = "a.news-title"           # 标题链接（绝对 URL）
LIST_TIME_SEL = ".pub-time"               # 发布时间（YYYY-MM-DD HH:MM）

# 详情页选择器（fixture 演示结构）
DETAIL_TITLE_SEL = "h1.news-title"        # 标题
DETAIL_META_SEL = ".meta"                 # 发布时间 / 来源行
DETAIL_CONTENT_SEL = ".article-body"      # 正文容器

# live 选择器（真实站点结构，B11 快照取证）
LIVE_LIST_ITEM_SEL = ".ws-news .article--wraped"       # 单条新闻（含图+内容块）
LIVE_LIST_TITLE_SEL = ".article--content .article_p a"  # 标题链接（相对路径）
LIVE_LIST_TIME_SEL = ".article--time time"              # time[datetime] 属性优先
LIVE_DETAIL_TITLE_SEL = ".ws-title h1"                  # 详情标题
LIVE_DETAIL_TIME_SEL = ".ws-title-infor time"           # time[datetime] 属性优先
LIVE_DETAIL_CONTENT_SEL = 'div[id^=showall]'            # 正文容器（id=showallNNN）

# live 正文容器内需剔除的噪音块（B13 快照取证：均在 showall 容器内部）
LIVE_NOISE_SELECTORS = (
    ".source--wrapper",       # 「来源：/作者：/本文地址：」行
    ".article_back--wrapper",  # 「返回第一电动网首页」链接
    ".ads-container",          # 版权信息上下方广告位
    ".ws-copyright",           # 转载声明/图片侵权声明
    ".ad--wrapper",            # 开篇广告位
    "script",
    "style",
)

# 日期时间提取：YYYY-MM-DD[ HH:MM[:SS]]（列表时间行与详情 meta 行通用）
_DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)")

# 已知企业名单：标题/正文命中即作为 company 字段（fixture 演示用 XX汽车，
# live 真实站点主流车企/电池厂，按文中最早出现位置命中）
KNOWN_COMPANIES = (
    "XX汽车",  # fixture 演示主体（答辩主线：召回新闻的 company）
    "宁德时代",
    "比亚迪",
    "蔚来",
    "小鹏汽车",
    "理想汽车",
    "特斯拉",
    "吉利",
    "长安汽车",
    "奇瑞",
    "广汽",
    "上汽",
    "长城汽车",
    "华为",
    "大众",
    "丰田",
)


def _abs_url(href: str) -> str:
    """相对链接 → 绝对链接；已是绝对地址则原样返回。"""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return BASE_URL + href
    return href


def parse_list(html: str) -> list[dict]:
    """解析列表页 → [{url, title, datetime}]。

    - 只取 LIST_ITEM_SEL 命中的条目，导航/分页/页脚不会进来
    - 跳过无链接、锚点或 javascript 链接的行
    - 标题优先取 a 文本，为空时退回 title 属性
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for item in soup.select(LIST_ITEM_SEL):
        link = item.select_one(LIST_TITLE_SEL)
        if link is None or not link.get("href"):
            continue
        href = link["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        title = link.get_text(strip=True) or (link.get("title") or "").strip()
        if not title:
            continue
        time_el = item.select_one(LIST_TIME_SEL)
        time_text = time_el.get_text(strip=True) if time_el else ""
        match = _DATETIME_RE.search(time_text)
        rows.append(
            {
                "url": _abs_url(href),
                "title": title,
                "datetime": match.group(1) if match else "",
            }
        )
    return rows


def parse_detail(html: str) -> dict | None:
    """解析详情页 → {title, datetime, content_html, company}；正文容器缺失返回 None。

    content_html 取正文容器的「外层 HTML」（含 .article-body 包裹）：
    交给 normalize → clean_html 做密度抽取时，收紧算法会下潜到该容器，
    其内部叶子段落得以完整保留。
    """
    soup = BeautifulSoup(html, "html.parser")
    content_el = soup.select_one(DETAIL_CONTENT_SEL)
    if content_el is None:
        return None
    title_el = soup.select_one(DETAIL_TITLE_SEL)
    meta_el = soup.select_one(DETAIL_META_SEL)
    datetime_text = ""
    if meta_el is not None:
        match = _DATETIME_RE.search(meta_el.get_text())
        if match:
            datetime_text = match.group(1)
    # 企业提取：扫标题 + 正文可见文本（企业名在标题或正文中出现即命中）
    full_text = " ".join(
        el.get_text(" ", strip=True) for el in (title_el, content_el) if el is not None
    )
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "datetime": datetime_text,
        "content_html": content_el.decode(),
        "company": extract_company(full_text),
    }


def extract_company(text: str) -> str | None:
    """标题/正文中命中已知企业名即返回该企业名；未命中返回 None。

    多个企业同时命中时取「文中最早出现」的那个（确定性规则，live 正文
    常同时提及多家车企/供应商）。
    """
    best_name, best_pos = None, -1
    for name in KNOWN_COMPANIES:
        pos = text.find(name)
        if pos >= 0 and (best_pos < 0 or pos < best_pos):
            best_name, best_pos = name, pos
    return best_name


# ---------------------------------------------------------------------------
# live 解析（真实站点结构，B11 快照取证；与 fixture 版返回结构完全一致）
# ---------------------------------------------------------------------------


def parse_list_live(html: str) -> list[dict]:
    """解析 live 列表页 → [{url, title, datetime}]。

    与 fixture 版的差异（快照实测）：
    - 标题链接为站点相对路径（/news/shichang/310950 → 拼域名）
    - 时间在 time[datetime] 属性（显示文本相同，属性更规整，优先取属性）
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for item in soup.select(LIVE_LIST_ITEM_SEL):
        link = item.select_one(LIVE_LIST_TITLE_SEL)
        if link is None or not link.get("href"):
            continue
        href = link["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        title = link.get_text(strip=True) or (link.get("title") or "").strip()
        if not title:
            continue
        datetime_text = ""
        time_el = item.select_one(LIVE_LIST_TIME_SEL)
        if time_el is not None:
            datetime_text = (time_el.get("datetime") or "").strip() or time_el.get_text(strip=True)
        match = _DATETIME_RE.search(datetime_text)
        rows.append(
            {
                "url": _abs_url(href),
                "title": title,
                "datetime": match.group(1) if match else "",
            }
        )
    return rows


def parse_detail_live(html: str) -> dict | None:
    """解析 live 详情页 → {title, datetime, content_html, company}；正文容器缺失返回 None。

    - 时间取 .ws-title-infor time[datetime] 属性
    - 正文容器 div[id^=showall]：先剔除容器内的噪音块（来源行/返回链接/
      广告位/转载声明/script），再取外层 HTML 交给密度清洗——
      推荐位与广告（新闻推荐 articleList 等）在容器外，天然隔离
    """
    soup = BeautifulSoup(html, "html.parser")
    content_el = soup.select_one(LIVE_DETAIL_CONTENT_SEL)
    if content_el is None:
        return None
    title_el = soup.select_one(LIVE_DETAIL_TITLE_SEL)
    time_el = soup.select_one(LIVE_DETAIL_TIME_SEL)
    datetime_text = ""
    if time_el is not None:
        datetime_text = (time_el.get("datetime") or "").strip() or time_el.get_text(strip=True)
    match = _DATETIME_RE.search(datetime_text)

    # 剔除正文容器内部的噪音块（拷贝修改，不动入参 soup）
    for sel in LIVE_NOISE_SELECTORS:
        for node in content_el.select(sel):
            node.decompose()

    # 企业提取：扫标题 + 正文可见文本（剔除噪音后的）
    full_text = " ".join(
        el.get_text(" ", strip=True) for el in (title_el, content_el) if el is not None
    )
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "datetime": match.group(1) if match else "",
        "content_html": content_el.decode(),
        "company": extract_company(full_text),
    }
