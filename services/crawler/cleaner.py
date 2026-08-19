# -*- coding: utf-8 -*-
"""B3 · 清洗强化模块（BeautifulSoup 实现）

职责（任务卡 B3）：
- 去 script/style/注释/隐藏元素
- 去导航残渣：header/nav/footer/aside/面包屑/页码/版权/相关推荐等非正文噪音
- 正文密度：按「文本块」计算密度并打分，选出正文容器，抽出高密度文本
- 压缩空白：任意连续空白 → 单空格

入口：
- clean_html(html)      粗暴全量清洗（B1 骨架版 clean_html 的 BS4 替代，适合列表页/兜底）
- extract_main_text(html) 密度算法抽取正文（适合详情页）

约定：
- 本模块不解析具体站点选择器（那是各源 selectors.py 的职责）；
  只提供「任意 HTML → 干净文本」的通用能力
- 脏 HTML 进、干净 text 出；正文长度不足 80 字（MIN_CONTENT_LEN）由调用方丢弃
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

from base import MIN_CONTENT_LEN

# ---------------------------------------------------------------------------
# 规则表（可按数据源微调，但不改契约字段）
# ---------------------------------------------------------------------------

# 整块移除的标签：脚本/样式/模板/弹窗等
STRIP_TAGS = ("script", "style", "noscript", "template", "iframe", "form", "button", "input", "select", "textarea")

# 导航/残渣标签：header/nav/footer/aside 在正文页里几乎不承载正文
NAV_TAGS = ("header", "nav", "footer", "aside")

# 按属性值匹配的残渣（class/id 正则，命中即移除整个块）
NOISE_ATTR_PATTERNS = (
    re.compile(r"crumb|breadcrumb", re.I),            # 面包屑
    re.compile(r"pagination|pager", re.I),            # 分页
    re.compile(r"\bnav\b|menu|sidebar", re.I),        # 导航/菜单/侧栏
    re.compile(r"share|comment|related|recommend", re.I),  # 分享/评论/相关推荐
    re.compile(r"copyright", re.I),                   # 版权
)

# 元信息行（发布时间/来源/责编等）：叶子块文本以此开头即视为元信息，不入正文
META_LINE_RE = re.compile(
    r"^(发布时间|发布日期|来源|出处|责编|编辑|作者|记者|浏览|点击|阅读|分享|标签|关键词)[:：\s　]"
)
# 纯日期时间行（如「2026-08-18 09:00」），同样视为元信息
DATETIME_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([\s　]*\d{1,2}:\d{2}(:\d{2})?)?$")

# 容器收紧阈值：子容器得分达到父容器该比例时，认为子容器更贴近正文
TIGHTEN_RATIO = 0.6


# ---------------------------------------------------------------------------
# 基础清洗
# ---------------------------------------------------------------------------

def _strip_noise(soup: BeautifulSoup) -> None:
    """移除噪音节点：script/style 等标签 + 导航残渣标签 + 属性命中的残渣块。"""
    # 1) 整块移除的标签
    for tag_name in STRIP_TAGS + NAV_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 2) 按属性命中残渣：拼接 class/id 属性值，命中正则即整块移除
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag) or tag.decomposed:
            continue
        attr_text = ""
        for key in ("class", "id"):
            value = tag.get(key)
            if value:
                attr_text += " " + (" ".join(value) if isinstance(value, list) else str(value))
        for pattern in NOISE_ATTR_PATTERNS:
            if pattern.search(attr_text):
                tag.decompose()
                break


def clean_text(text: str) -> str:
    """压缩空白：任意连续空白字符合并为单个空格并去首尾。"""
    return re.sub(r"\s+", " ", str(text)).strip()


def clean_html(html: str) -> str:
    """全量粗暴清洗：任意 HTML → 干净纯文本（去噪音标签后取全部文本）。

    适合列表页摘要或正文容器已明确时的兜底。
    """
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    _strip_noise(soup)
    return clean_text(soup.get_text(" ", strip=True))


# ---------------------------------------------------------------------------
# 正文密度抽取
# ---------------------------------------------------------------------------

# 一个「文本块」：块级标签（p/div/section/article 等）内直接持有的文本
BLOCK_TAGS = ("p", "div", "section", "article", "li", "td", "blockquote", "pre")


def _tag_score(tag: Tag) -> tuple[int, int]:
    """计算单个块级标签的 (文本长度, 链接文本长度)。

    链接文本占比高 → 大概率是目录/导航残渣，密度算法据此降权。
    """
    text_len = len(tag.get_text(" ", strip=True))
    link_len = 0
    for a in tag.find_all("a"):
        link_len += len(a.get_text(" ", strip=True))
    return text_len, link_len


def _block_score(tag: Tag) -> float:
    """块级容器得分：文本量 − 链接文本量×2（链接占比高 = 导航嫌疑）。"""
    text_len, link_len = _tag_score(tag)
    return text_len - link_len * 2


def _best_descendant(tag: Tag):
    """tag 的后代块级元素中得分最高者及其得分；无候选返回 (None, -1)。"""
    best: Tag | None = None
    best_score = -1.0
    for child in tag.find_all(BLOCK_TAGS):
        if not isinstance(child, Tag) or child.decomposed:
            continue
        score = _block_score(child)
        if score > best_score:
            best, best_score = child, score
    return best, best_score


def extract_main_text(html: str, min_density: float = 0.3, min_block_len: int = 30) -> str:
    """正文密度抽取：容器收紧 → 叶子块收集 → 三重过滤。

    算法（B3 强化版）：
    1. 去噪后给所有块级容器打分，取最高者为初始正文容器
    2. 容器收紧：只要后代块得分 ≥ 父容器×TIGHTEN_RATIO，就下潜到该后代——
       防止「外层壳」（含标题/元信息/热文的 article 壳）抢走正文容器的位置
    3. 只收集叶子文本块（自身不再包含块级子元素）——防止「容器 + 其内部段落」
       被重复拼接两次
    4. 叶子块三重过滤：长度、元信息行（发布时间/来源/责编等）、链接密度

    min_density：叶子块内非链接文本占比的最低值，低于则视为导航/推荐残渣
    min_block_len：短于该长度的叶子块视为残渣丢弃（页码、分享行等）
    """
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    _strip_noise(soup)  # 先去 script/style/导航残渣

    # 1) 全部块级候选打分，取最高者为初始正文容器
    main: Tag | None = None
    main_score = -1.0
    for tag in soup.find_all(BLOCK_TAGS):
        if not isinstance(tag, Tag) or tag.decomposed:
            continue
        score = _block_score(tag)
        if score > main_score:
            main, main_score = tag, score
    if main is None or main_score <= 0:
        return clean_text(soup.get_text(" ", strip=True))  # 无有效块：兜底取全文

    # 2) 容器收紧：下潜到得分足够高的子容器，贴紧真正的正文区
    while True:
        child, child_score = _best_descendant(main)
        if child is not None and child_score >= main_score * TIGHTEN_RATIO:
            main, main_score = child, child_score
        else:
            break

    # 3) 收集叶子文本块（含块级子元素的容器跳过，其叶子后代会被单独收集）
    parts: list[str] = []
    for block in main.find_all(BLOCK_TAGS):
        if not isinstance(block, Tag) or block.decomposed:
            continue
        if block.find(BLOCK_TAGS):
            continue  # 非叶子：跳过，避免段落被重复拼接
        text = clean_text(block.get_text(" ", strip=True))
        # 4) 三重过滤：长度 / 元信息行 / 链接密度
        if len(text) < min_block_len:
            continue  # 短块：残渣（页码、分享行、热文标题等）
        if META_LINE_RE.match(text) or DATETIME_LINE_RE.match(text):
            continue  # 元信息行：发布时间/来源/责编等不入正文
        text_len, link_len = _tag_score(block)
        if text_len == 0:
            continue
        if (text_len - link_len) / text_len < min_density:
            continue  # 链接占比过高：导航/推荐残渣
        parts.append(text)

    # 正文容器本身就是叶子（如整页只有一个 <p>）时，直接取其全文
    if not parts:
        fallback = clean_text(main.get_text(" ", strip=True))
        return fallback if len(fallback) >= MIN_CONTENT_LEN else ""

    return clean_text(" ".join(parts))


# ---------------------------------------------------------------------------
# B3 自测：脏 HTML → 干净 text（任务卡 B3 验收）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 场景1：带导航/面包屑/页码/推荐/版权的详情页
    dirty_detail = """
    <html><head><title>某车企宣布召回12万辆新能源车</title><style>.a{}</style></head>
    <body>
      <div class="header"><a href="/">首页</a><a href="/news">资讯</a></div>
      <div class="crumb">首页 &gt; 资讯 &gt; 行业新闻</div>
      <nav><a href="/p2">下一页</a><a href="/p3">下下页</p></nav>
      <div class="main-content">
        <h1>某车企宣布召回12万辆新能源车</h1>
        <p class="date">2026-08-18 09:00</p>
        <div id="content">
          <p>某新能源汽车企业今日宣布召回12万辆汽车，初步原因为电池模组存在过热隐患，公司将免费更换相关零部件，并同步通知经销商与车主处理后续事宜。</p>
          <p>此次召回可能影响品牌信誉及供应链订单，业内预计相关电池供应商短期承压，公司股价盘前一度下挫超过三个百分点。</p>
          <p>公司回应称已启动应急预案，将逐批排查问题模组，并在三十天内向监管部门提交完整的技术分析报告与整改计划。</p>
        </div>
        <div class="recommend"><a href="/n/9">相关阅读：电池安全新国标</a><a href="/n/8">猜你想看：冬季续航指南</a></div>
        <div class="copyright">Copyright © 2026 Example News. All rights reserved.</div>
      </div>
      <script>alert('x')</script>
    </body></html>
    """
    text1 = extract_main_text(dirty_detail)
    assert "召回12万辆" in text1, text1
    assert "电池模组" in text1 and "整改计划" in text1, text1
    assert "首页" not in text1 and "相关阅读" not in text1, text1
    assert "Copyright" not in text1 and "下一页" not in text1, text1
    assert "script" not in text1.lower() and "{" not in text1
    print(f"[selftest] detail ok len={len(text1)}")

    # 场景2：纯噪音页（无正文块）→ 空串，调用方丢弃
    pure_noise = '<html><body><nav><a href="/1">一</a><a href="/2">二</a></nav><div class="share">分享到微博</div></body></html>'
    assert extract_main_text(pure_noise) == ""
    print("[selftest] noise ok")

    # 场景3：clean_html 全量清洗（列表页摘要/兜底用）
    dirty_fragment = '<div class="sidebar"><a href="/a">链接甲</a></div><p>正文段落，这是一段足够长的正文内容，用来验证全量清洗后链接文本不会混入。</p><script>var x=1;</script>'
    text3 = re.sub(r"\s+", " ", clean_html(dirty_fragment)).strip()
    assert "链接甲" not in text3, text3
    assert "正文段落" in text3 and "var x" not in text3, text3
    print(f"[selftest] clean_html ok len={len(text3)}")

    # 场景4：嵌套容器 + 元信息行 + 热文链接（详情页典型结构）
    #   - 外层壳(.news-detail 含标题/元信息/热文) 得分高于正文容器 → 必须收紧下潜
    #   - 正文容器内多个 <p> → 叶子收集，段落不得重复拼接
    nested = """
    <div class="news-detail">
      <h1 class="news-title">某车企宣布召回12万辆新能源车</h1>
      <div class="meta">发布时间：2026-08-18 09:00　来源：新能源车资讯网　责编：王某</div>
      <div class="article-body">
        <p>XX汽车今日宣布召回12万辆新能源汽车，初步原因为电池模组存在过热隐患，公司称将免费更换相关零部件，并同步通知经销商与车主。</p>
        <p>此次召回可能影响品牌信誉及供应链订单，业内预计相关电池供应商短期承压，XX汽车已成立专项小组逐批排查问题模组。</p>
      </div>
      <div class="hot-news"><a href="/h1">热文：某新车上市</a><a href="/h2">热文：续航实测</a></div>
    </div>
    """
    text4 = extract_main_text(nested)
    assert "发布时间" not in text4 and "责编" not in text4, text4
    assert "热文" not in text4 and "上市" not in text4, text4
    assert "过热隐患" in text4 and "品牌信誉" in text4, text4
    assert text4.count("过热隐患") == 1, text4  # 段落不重复拼接
    print(f"[selftest] nested ok len={len(text4)}")

    print("[selftest] B3 清洗强化全部通过")
