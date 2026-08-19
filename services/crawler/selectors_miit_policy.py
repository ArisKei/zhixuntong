# -*- coding: utf-8 -*-
"""B5/B12 · miit_policy 源选择器（工信部装备工业一司「工作动态」栏目）

只放 DOM 解析，不放业务逻辑（业务在 miit_policy.py，流水线在 base.py）。
live 模式若站点改版，只改本文件的选择器常量，不动其他代码。

两套结构（fixture 演示 / live 真实站点，B12 快照实测）：
- fixture（fixtures/html/miit_policy/ 种子，演示与答辩）：
  列表 .zcwj-list li：a（相对链接+标题）+ .date（YYYY-MM-DD）
  详情 .article-title（标题）/ .article-info（发布时间+来源行）/ #content（正文）
- live（https://www.miit.gov.cn/jgsj/zbys/gzdt/index.html，B11 快照取证）：
  列表 .lmy_main_rb .page-content li：a.fl（相对链接，title 属性含完整标题，
        显示文本可能被截断加「...」）+ span.fr（YYYY-MM-DD）
  详情 #con_title（标题）/ #con_time（「发布时间：2026-08-04 17:10」）/
        #con_con（正文容器，取外层 HTML 交给密度清洗）
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# 站点域名：把列表页的相对链接拼成绝对 URL（入库 source_url 必须是绝对地址）
BASE_URL = "https://www.miit.gov.cn"

# 列表页选择器（fixture 演示结构）
LIST_ITEM_SEL = ".zcwj-list li"  # 单条政策条目（导航/分页不在其内，天然隔离）
LIST_DATE_SEL = ".date"          # 发布日期

# 详情页选择器（fixture 演示结构）
DETAIL_TITLE_SEL = ".article-title"   # 标题（h1）
DETAIL_INFO_SEL = ".article-info"     # 发布时间 / 来源行
DETAIL_CONTENT_SEL = "#content"       # 正文容器

# live 选择器（真实站点结构，B11 快照取证；限定 .lmy_main_rb 右栏防误伤）
LIVE_LIST_ITEM_SEL = ".lmy_main_rb .page-content ul li"
LIVE_LIST_LINK_SEL = "a.fl"    # 详情链接：href 相对路径，title 属性是完整标题
LIVE_LIST_DATE_SEL = "span.fr"  # 日期：YYYY-MM-DD
LIVE_DETAIL_TITLE_SEL = "#con_title"    # 详情标题（h1）
LIVE_DETAIL_TIME_SEL = "#con_time"      # 「发布时间：2026-08-04 17:10」
LIVE_DETAIL_CONTENT_SEL = "#con_con"    # 正文容器

# 从任意文本里抠 YYYY-MM-DD（列表日期行与详情 info 行通用）
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _abs_url(href: str) -> str:
    """站点相对链接 → 绝对链接；已是绝对地址则原样返回。"""
    href = href.strip()
    if href.startswith("/"):
        return BASE_URL + href
    return href


def parse_list(html: str) -> list[dict]:
    """解析列表页 → [{url, title, date}]。

    - 只取 LIST_ITEM_SEL 命中的条目，页面其他噪音（导航/分页/页脚）不会进来
    - 跳过无链接、锚点或 javascript 链接的行
    - 标题优先取 a 文本，为空时退回 title 属性
    """
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
        date_text = date_el.get_text(strip=True) if date_el else ""
        match = _DATE_RE.search(date_text)
        rows.append(
            {
                "url": _abs_url(href),
                "title": title,
                "date": match.group(1) if match else "",
            }
        )
    return rows


def parse_detail(html: str) -> dict | None:
    """解析详情页 → {title, date, content_html}；正文容器缺失返回 None。

    content_html 取正文容器的「外层 HTML」（含 <div id="content"> 包裹）：
    交给 normalize → clean_html 做正文密度抽取时，包裹层会成为得分最高的
    正文容器，内部全部段落得以保留（无包裹会导致只抽出第一段）。
    """
    soup = BeautifulSoup(html, "html.parser")
    content_el = soup.select_one(DETAIL_CONTENT_SEL)
    if content_el is None:
        return None
    title_el = soup.select_one(DETAIL_TITLE_SEL)
    info_el = soup.select_one(DETAIL_INFO_SEL)
    date = ""
    if info_el is not None:
        match = _DATE_RE.search(info_el.get_text())
        if match:
            date = match.group(1)
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "date": date,
        "content_html": content_el.decode(),
    }


# ---------------------------------------------------------------------------
# live 解析（真实站点结构，B11 快照取证；与 fixture 版返回结构完全一致）
# ---------------------------------------------------------------------------

# 「发布时间：2026-08-04 17:10」→ 抠出带时分的时间（比 _DATE_RE 多保留 H:M，
# published_at 契约支持时分；parse_datetime 已支持 "%Y-%m-%d %H:%M"）
_DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)")


def parse_list_live(html: str) -> list[dict]:
    """解析 live 列表页 → [{url, title, date}]。

    与 fixture 版的差异（快照实测）：
    - 标题优先取 a 的 title 属性（完整标题），显示文本可能被站点截断加「…」
    - 日期在 span.fr，纯 YYYY-MM-DD
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for li in soup.select(LIVE_LIST_ITEM_SEL):
        link = li.select_one(LIVE_LIST_LINK_SEL)
        if link is None or not link.get("href"):
            continue
        href = link["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        title = (link.get("title") or "").strip() or link.get_text(strip=True)
        if not title:
            continue
        date_el = li.select_one(LIVE_LIST_DATE_SEL)
        match = _DATE_RE.search(date_el.get_text()) if date_el else None
        rows.append(
            {
                "url": _abs_url(href),
                "title": title,
                "date": match.group(1) if match else "",
            }
        )
    return rows


def parse_detail_live(html: str) -> dict | None:
    """解析 live 详情页 → {title, date, content_html}；正文容器缺失返回 None。

    - 时间从 #con_time（「发布时间：2026-08-04 17:10」）抠出带时分的时间串
    - 正文容器 #con_con 取外层 HTML（与 fixture 版同策略：包裹层让密度抽取
      保住全部段落）；二维码/分享/相关推荐都在容器外，天然隔离
    """
    soup = BeautifulSoup(html, "html.parser")
    content_el = soup.select_one(LIVE_DETAIL_CONTENT_SEL)
    if content_el is None:
        return None
    title_el = soup.select_one(LIVE_DETAIL_TITLE_SEL)
    time_el = soup.select_one(LIVE_DETAIL_TIME_SEL)
    date = ""
    if time_el is not None:
        match = _DATETIME_RE.search(time_el.get_text())
        if match:
            date = match.group(1)
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "date": date,
        "content_html": content_el.decode(),
    }
