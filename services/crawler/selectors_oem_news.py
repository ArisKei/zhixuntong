# -*- coding: utf-8 -*-
"""B7/B14 · oem_news 源选择器（比亚迪官方新闻中心·中国站）

只放 DOM 解析，不放业务逻辑（业务在 oem_news.py，流水线在 base.py）。
live 模式若站点改版，只改本文件的选择器常量，不动其他代码。

两套结构（fixture 演示 / live 真实站点，B14 快照取证）：
- fixture（fixtures/html/oem_news/ 种子，演示与答辩）：
  列表 .press-list li：a（相对链接+标题）+ .p-date（2026.08.13 圆点格式）
  详情 h1.press-title / .press-meta（日期+来源行）/ .press-content（正文）
- live（https://www.byd.com/cn/news，B14 渲染快照取证）：
  ⚠️ 列表卡片是 Vue 挂载后经 API 加载（requests 原始 HTML 只有「暂无数据」
     占位），列表页必须 Selenium 渲染；详情页服务端渲染，requests 可用
  列表 .cmp-news__cards-body .news-card：
        .news-card__info（两 span：栏目「公司新闻」+ ISO 日期时间）
        .news-card__title a（href 已是终态 /cn/detailN，无需归一化）
  详情 .cmp-news__detail-title / .cmp-news__detail-date（「发布于 YYYY-MM-DD HH:MM:SS」）
        / .cmp-news__detail-content（正文容器，.news-text 文本块 + .news-image 图块）
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# 站点域名：把列表页的相对链接拼成绝对 URL
# （fixture 种子链接指向 example.com 演示域；live 相对链接拼真实站点）
BASE_URL = "https://www.byd.com"

# 车企官方新闻中心：所有新闻的企业主体就是站点方
SITE_COMPANY = "XX汽车"          # fixture 演示主体
LIVE_SITE_COMPANY = "比亚迪"      # live 真实站点主体

# 列表页选择器（fixture 演示结构）
LIST_ITEM_SEL = ".press-list li"    # 单条新闻条目
LIST_DATE_SEL = ".p-date"           # 发布日期（2026.08.13 圆点格式）

# 详情页选择器（fixture 演示结构）
DETAIL_TITLE_SEL = "h1.press-title"   # 标题
DETAIL_META_SEL = ".press-meta"       # 发布日期 + 来源行
DETAIL_CONTENT_SEL = ".press-content" # 正文容器

# live 选择器（真实站点结构，B14 渲染快照取证）
LIVE_LIST_ITEM_SEL = ".cmp-news__cards-body .news-card"  # 单张新闻卡片
LIVE_LIST_TITLE_SEL = ".news-card__title a"              # 标题链接（href=/cn/detailN）
LIVE_LIST_INFO_SEL = ".news-card__info"                  # 栏目 + ISO 日期时间（两 span）
LIVE_DETAIL_TITLE_SEL = ".cmp-news__detail-title"        # 详情标题（h2）
LIVE_DETAIL_DATE_SEL = ".cmp-news__detail-date"          # 「发布于 YYYY-MM-DD HH:MM:SS」
LIVE_DETAIL_CONTENT_SEL = ".cmp-news__detail-content"    # 正文容器

# 站点日期：圆点/横线/斜杠分隔统一兼容，时间为可选 → 规范化为 YYYY-MM-DD[ HH:MM]
_SITE_DATE_RE = re.compile(
    r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})(?:\s+(\d{1,2}:\d{2})(?::\d{2})?)?"
)


def _abs_url(href: str) -> str:
    """相对链接 → 绝对链接；已是绝对地址则原样返回。"""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return BASE_URL + href
    return href


def _norm_datetime(text: str) -> str:
    """把站点圆点日期「2026.08.13 19:00」规范化为 ISO「2026-08-13 19:00」。"""
    match = _SITE_DATE_RE.search(text or "")
    if not match:
        return ""
    date = f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return f"{date} {match.group(4)}" if match.group(4) else date


def parse_list(html: str) -> list[dict]:
    """解析列表页 → [{url, title, date}]（列表页只有日期，时间在详情页）。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for li in soup.select(LIST_ITEM_SEL):
        link = li.select_one("a")
        if link is None or not link.get("href"):
            continue
        href = link["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        title = link.get_text(strip=True) or (link.get("title") or "").strip()
        if not title:
            continue
        date_el = li.select_one(LIST_DATE_SEL)
        rows.append(
            {
                "url": _abs_url(href),
                "title": title,
                "date": _norm_datetime(date_el.get_text(strip=True) if date_el else ""),
            }
        )
    return rows


def parse_detail(html: str) -> dict | None:
    """解析详情页 → {title, datetime, content_html, company}；正文容器缺失返回 None。

    content_html 取正文容器的「外层 HTML」（含 .press-content 包裹），
    交给 normalize → clean_html 做密度抽取时收紧算法会下潜到该容器。
    company 恒为 SITE_COMPANY：车企新闻中心的新闻主体就是站点方。
    """
    soup = BeautifulSoup(html, "html.parser")
    content_el = soup.select_one(DETAIL_CONTENT_SEL)
    if content_el is None:
        return None
    title_el = soup.select_one(DETAIL_TITLE_SEL)
    meta_el = soup.select_one(DETAIL_META_SEL)
    datetime_text = ""
    if meta_el is not None:
        datetime_text = _norm_datetime(meta_el.get_text())
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "datetime": datetime_text,
        "content_html": content_el.decode(),
        "company": SITE_COMPANY,
    }


# ---------------------------------------------------------------------------
# live 解析（真实站点结构，B14 渲染快照取证；与 fixture 版返回结构完全一致）
# ---------------------------------------------------------------------------


def parse_list_live(html: str) -> list[dict]:
    """解析 live 列表页（Selenium 渲染后）→ [{url, title, date}]。

    与 fixture 版的差异（渲染快照实测）：
    - 卡片选择器 .news-card；标题在 .news-card__title a（href 已是 /cn/detailN
      终态形式——requests 原始 HTML 里的 /page/byd-cn/... 是 JS 重写前的地址）
    - 日期时间在 .news-card__info 的第二个 span（ISO 带秒），列表页就带完整时间
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(LIVE_LIST_ITEM_SEL):
        link = card.select_one(LIVE_LIST_TITLE_SEL)
        if link is None or not link.get("href"):
            continue
        href = link["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        title = link.get_text(strip=True) or (link.get("title") or "").strip()
        if not title:
            continue
        info_el = card.select_one(LIVE_LIST_INFO_SEL)
        date = _norm_datetime(info_el.get_text(" ", strip=True) if info_el else "")
        rows.append({"url": _abs_url(href), "title": title, "date": date})
    return rows


def parse_detail_live(html: str) -> dict | None:
    """解析 live 详情页 → {title, datetime, content_html, company}；正文容器缺失返回 None。

    - 时间在 .cmp-news__detail-date（「发布于 2026-04-01 10:32:58」），规范化去秒
    - 正文容器 .cmp-news__detail-content 取外层 HTML 交给密度清洗：
      .news-text 文本块保留、.news-image 图块无文本自然被密度过滤
    - company 恒为 LIVE_SITE_COMPANY（比亚迪官方新闻中心）
    - 海报式快讯（销量战报：一两句话+大图）正文不足 80 字 → normalize 的
      dropped_short 契约行为丢弃，不造假正文（B14 任务卡约定）
    """
    soup = BeautifulSoup(html, "html.parser")
    content_el = soup.select_one(LIVE_DETAIL_CONTENT_SEL)
    if content_el is None:
        return None
    title_el = soup.select_one(LIVE_DETAIL_TITLE_SEL)
    date_el = soup.select_one(LIVE_DETAIL_DATE_SEL)
    datetime_text = ""
    if date_el is not None:
        datetime_text = _norm_datetime(date_el.get_text(strip=True))
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "datetime": datetime_text,
        "content_html": content_el.decode(),
        "company": LIVE_SITE_COMPANY,
    }
