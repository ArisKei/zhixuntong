# -*- coding: utf-8 -*-
"""B4 · 分类与关键词提取（纯规则实现，不调大模型）

职责（任务卡 B4）：
- 关键词表（召回/政策/补贴/电池/芯片…）→ category + keywords[]
- 硬性规则：含「召回」等风险词的新闻 category 必为 risk
  （与成员 D 的风险升级规则同口径：召回/停产/断供 → 高风险）

分类算法：
1. 风险词一票否决：标题或正文命中任一风险词 → risk
2. 其余按关键词计分：得分 = 标题命中次数×2 + 正文命中次数×1（标题信息量更高）
3. 取最高分分类；全部零分 → other

关键词提取：
- 全部规则词中命中的，按首次出现位置排序（标题词优先）
- 去子串：同时命中「固态电池」和「电池」时只保留长词
- 上限 5 个（对齐种子数据 2~3 个的风格）

边界：本模块只做通用规则，不碰具体站点选择器（那是各源 selectors.py 的职责）；
company 字段由各源选择器提取，不在这里做。
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 风险词：标题或正文任一命中 → category=risk（任务卡 B4 硬性要求）
# 前 3 个与成员 D 的风险升级规则（D3）同口径：召回/停产/断供 → level 不低于 high
RISK_KEYWORDS = (
    "召回", "停产", "断供", "起火", "自燃", "隐患",
    "缺陷", "事故", "处罚", "罚款", "维权",
    # 行业高频风险词补充（live 模式与现场加试题的兜底，种子回归已验证无误伤）
    "热失控", "约谈", "爆燃", "爆炸", "失火", "刹车失灵", "制动失效",
)

# 分类关键词表：计分制，取最高分分类
CATEGORY_KEYWORDS = {
    "policy": (
        "政策", "补贴", "购置税", "工信部", "工业和信息化部", "征求意见",
        "管理办法", "回收", "准入", "发文", "财政部", "法规",
    ),
    "company": (
        "发布", "发布会", "预售", "新款", "新车", "上市",
        "交付", "推出", "合作", "签约", "投产", "战略",
    ),
    "market": (
        "市场", "销量", "装车量", "出口", "关税", "产能",
        "份额", "同比", "排产", "储能", "价格", "成本",
    ),
    "tech": (
        "技术", "电池", "固态电池", "芯片", "智驾", "NOA",
        "领航辅助", "智能网联", "续航", "充电", "能量密度", "中试线",
        "新能源", "高压平台",
    ),
}

# 全部关键词（含风险词、去重保序），供关键词提取使用
ALL_KEYWORDS = tuple(dict.fromkeys(RISK_KEYWORDS + tuple(
    word for words in CATEGORY_KEYWORDS.values() for word in words
)))

# 每条新闻最多提取的关键词数
KEYWORD_LIMIT = 5


def _score(title: str, content: str, words: tuple) -> int:
    """分类计分：标题命中次数×2 + 正文命中次数×1。"""
    return sum(title.count(word) * 2 + content.count(word) for word in words)


def classify(title: str, content: str) -> str:
    """规则分类：风险词一票否决 → risk；否则按关键词计分取最高；零分 → other。"""
    title = title or ""
    content = content or ""
    # 硬性规则：召回/停产/断供等风险词命中即 risk，优先级最高
    for word in RISK_KEYWORDS:
        if word in title or word in content:
            return "risk"
    scores = {
        category: _score(title, content, words)
        for category, words in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)  # 平分时按表定义顺序（policy > company > market > tech）
    return best if scores[best] > 0 else "other"


def extract_keywords(title: str, content: str, limit: int = KEYWORD_LIMIT) -> list:
    """关键词提取：命中词按首次出现位置排序，去掉被更长词包含的子串，截取上限。"""
    text = f"{title or ''}\n{content or ''}"
    hits = [
        (text.index(word), word)
        for word in ALL_KEYWORDS
        if word in text
    ]
    hits.sort()
    words = [word for _, word in hits]
    # 去子串：如同时命中「固态电池」与「电池」，只保留「固态电池」
    deduped = [
        word
        for word in words
        if not any(word != other and word in other for other in words)
    ]
    return deduped[:limit]


# ---------------------------------------------------------------------------
# B4 自测：硬规则 + 用组长种子数据（8 条已标注分类）做全量回归
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1) 硬性规则：满是技术词的新闻，标题含「召回」必为 risk
    assert classify("某车企宣布召回12万辆新能源车", "固态电池能量密度提升，续航更长。") == "risk"
    # 正文命中风险词同样升为 risk
    assert classify("电池供应商突发状况说明", "经排查存在批量缺陷，公司已停产整改。") == "risk"

    # 2) 计分分类：政策/市场/技术各归其位
    assert classify("新能源车购置税减免政策延续至2027年底", "财政部、工信部联合发文，购置税减免政策延续实施。") == "policy"
    assert classify("国内动力电池装车量连续三月增长", "7月装车量同比上升，储能需求回暖，企业排产上调。") == "market"
    assert classify("固态电池中试线投产", "能量密度较现有体系提升约20%，良率仍是瓶颈。") == "tech"

    # 3) 关键词提取：首现排序 + 去子串 + 上限
    kws = extract_keywords("固态电池中试线投产，能量密度宣称提升两成", "")
    assert kws[0] == "固态电池" and "电池" not in kws, kws
    assert "中试线" in kws and "能量密度" in kws, kws
    assert len(extract_keywords("新能源 政策 补贴 电池 芯片 智驾 关税 续航 市场", "")) == 5

    # 4) 空输入兜底
    assert classify("", "") == "other"
    assert extract_keywords("", "") == []

    # 5) 组长种子数据回归：8 条新闻的分类必须全部复现（最强验收）
    seed_path = REPO_ROOT / "fixtures" / "seed" / "news.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    mismatches = [
        (row["title"], classify(row["title"], row["content"]), row["category"])
        for row in seed
        if classify(row["title"], row["content"]) != row["category"]
    ]
    assert not mismatches, mismatches

    # 6) 种子召回新闻：category=risk 且关键词必含「召回」
    recall = next(row for row in seed if "召回" in row["title"])
    recall_kws = extract_keywords(recall["title"], recall["content"])
    assert classify(recall["title"], recall["content"]) == "risk"
    assert "召回" in recall_kws, recall_kws

    print(f"[selftest] seed {len(seed)}/{len(seed)} 分类全部复现；召回→risk 硬规则通过")
    print(f"[selftest] 召回新闻关键词示例: {recall_kws}")
