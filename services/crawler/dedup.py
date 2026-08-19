# -*- coding: utf-8 -*-
"""B2 · 去重模块（批次内判重 + 跨任务查库判重）

方案①（已与组长对齐）：B 直接连中台同一个数据库，自己完成查重与入库。
- 库地址解析与中台 app/config.py 完全一致：环境变量 > services/api/.env > 仓库根 .env > 默认值
- sqlite 相对路径（默认 sqlite:///./zhixuntong.db）锚定到 services/api/（中台运行目录），
  保证 B 无论从哪个目录启动，都和 A 打开同一个库文件
- 本模块只读不写：查 news.content_hash 判重并打标记；插入是 B8 的职责
- 去重语义（对齐中台 Mock 行为）：重复条目不插库、不计新增，
  在返回结果里标记 is_duplicate=True 并计入 duplicated 统计

依赖：sqlalchemy（中台 requirements 已含）；fixtures 模式无需网络。
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import sqlalchemy as sa

from base import BaseSpider, NewsItem

# 目录定位：services/crawler/dedup.py → services/api、仓库根
CRAWLER_DIR = Path(__file__).resolve().parent
API_DIR = CRAWLER_DIR.parent / "api"
REPO_ROOT = CRAWLER_DIR.parents[1]

# 与中台 app/config.py 的默认值一致（契约：.env.example）
DEFAULT_DATABASE_URL = "sqlite:///./zhixuntong.db"

# verbose=True 时打印调试日志；答辩时保持 False，控制台只输出锁死格式日志
verbose = False


def _log(message: str) -> None:
    """调试日志开关：默认关闭，避免污染锁死的控制台输出格式。"""
    if verbose:
        print(message)


# ---------------------------------------------------------------------------
# news 表定义：与冻结契约（services/api/app/models.py 的 News 模型）同构。
# 只消费契约字段，不自造；中台 create_all 已建表时本定义仅用于查询，不会重复建。
# ---------------------------------------------------------------------------

news_table = sa.Table(
    "news",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("title", sa.String(512), nullable=False),
    sa.Column("published_at", sa.DateTime, nullable=False, index=True),
    sa.Column("source", sa.String(64), nullable=False, index=True),
    sa.Column("source_url", sa.String(1024), nullable=False),
    sa.Column("category", sa.String(32), nullable=False, index=True),
    sa.Column("company", sa.String(128), nullable=True),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
    sa.Column("keywords", sa.JSON, default=list),
    sa.Column("is_duplicate", sa.Boolean, default=False),
)

_engine: Optional[sa.Engine] = None  # 模块级引擎缓存（同进程复用连接池）


# ---------------------------------------------------------------------------
# 数据库连接
# ---------------------------------------------------------------------------

def _read_env_files(*paths: Path) -> dict:
    """极简 .env 解析：只取 KEY=VALUE，忽略注释与空行。后读的文件覆盖先读的。"""
    env: dict = {}
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def resolve_database_url() -> str:
    """解析数据库地址，优先级与中台 pydantic-settings 一致：
    系统环境变量 > services/api/.env > 仓库根 .env > 默认值。
    """
    # 文件优先级：根 .env 先读、api/.env 后读覆盖（与中台 env_file 元组顺序一致）
    url = _read_env_files(REPO_ROOT / ".env", API_DIR / ".env").get("DATABASE_URL", "")
    url = os.environ.get("DATABASE_URL") or url or DEFAULT_DATABASE_URL
    return _anchor_sqlite(url)


def _anchor_sqlite(url: str) -> str:
    """sqlite 相对路径锚定到 services/api/（中台运行目录）。

    中台以 services/api 为工作目录启动，`sqlite:///./x.db` 实际落在该目录；
    B 从仓库根独立运行时若不锚定，会打开另一个文件导致跨任务去重失效。
    绝对路径与内存库原样返回。
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url  # MySQL 等其他数据库地址，不动
    raw = url[len(prefix):]
    if not raw or raw == ":memory:" or raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        return url  # 内存库 / 绝对路径（POSIX 或 Windows 盘符），不动
    return prefix + str((API_DIR / raw).resolve())


def get_engine(url: Optional[str] = None) -> sa.Engine:
    """获取数据库引擎；不传 url 时用解析出的共享库地址（带缓存）。

    sqlite 与中台一样加 check_same_thread=False，
    保证被中台 local 模式加载时可在 FastAPI 线程池中使用。
    """
    global _engine
    if url is None:
        if _engine is None:
            url = resolve_database_url()
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
            _engine = sa.create_engine(url, future=True, connect_args=connect_args)
        return _engine
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return sa.create_engine(url, future=True, connect_args=connect_args)


def ensure_news_table(engine: sa.Engine) -> None:
    """确保 news 表存在（checkfirst：中台已建表则跳过，DDL 与契约同构无冲突）。"""
    news_table.metadata.create_all(engine, tables=[news_table], checkfirst=True)


# ---------------------------------------------------------------------------
# 判重逻辑
# ---------------------------------------------------------------------------

def query_existing_hashes(engine: sa.Engine, hashes: Iterable[str], chunk: int = 500) -> set:
    """查库：给定哈希集合中，哪些已存在于 news 表（分块 IN 查询防超长 SQL）。"""
    hashes = [h for h in hashes if h]
    found: set = set()
    if not hashes:
        return found
    with engine.connect() as conn:
        for start in range(0, len(hashes), chunk):
            batch = hashes[start : start + chunk]
            rows = conn.execute(
                sa.select(news_table.c.content_hash).where(news_table.c.content_hash.in_(batch))
            ).fetchall()
            found.update(row[0] for row in rows)
    return found


@dataclass
class DedupResult:
    """去重结果。

    fresh：待插入的新条目（is_duplicate=False，保持原始顺序）
    all_items：全部条目（重复的已标 is_duplicate=True，供 CrawlResult.items 返回）
    duplicated：重复总数 = 批内重复 + 库中已存在
    """

    fresh: list
    all_items: list
    duplicated: int


def dedup(items: list, engine: Optional[sa.Engine] = None) -> DedupResult:
    """双层去重入口：先批次内判重，再查库判重（跨任务持久化）。

    - 只标记不删除：重复条目保留在 all_items 中（is_duplicate=True），不进 fresh
    - 传入 engine 则查库（并确保 news 表存在）；不传则只做批次内判重
    - 幂等：入口处统一重置 is_duplicate，重复调用结果一致
    """
    seen_in_batch: set = set()
    batch_dup = 0
    fresh: list = []

    # 第一层：批次内判重（同一批里同 hash 的第二条起算重复）
    for item in items:
        item.is_duplicate = False  # 幂等：清掉历史标记
        if not item.content_hash:  # 防御：漏算哈希的条目现场补算
            item.content_hash = BaseSpider.make_hash(item.title, item.source_url)
        if item.content_hash in seen_in_batch:
            item.is_duplicate = True
            batch_dup += 1
            continue
        seen_in_batch.add(item.content_hash)
        fresh.append(item)

    # 第二层：查库判重（上一任务/上次运行已入库的同 hash 条目）
    db_dup = 0
    if engine is not None and fresh:
        ensure_news_table(engine)  # 中台未启动过时兜底建表；已存在则跳过
        existing = query_existing_hashes(engine, (item.content_hash for item in fresh))
        kept: list = []
        for item in fresh:
            if item.content_hash in existing:
                item.is_duplicate = True
                db_dup += 1
                continue
            kept.append(item)
        fresh = kept

    duplicated = batch_dup + db_dup
    _log(f"[db] dedup batch_dup={batch_dup} db_dup={db_dup} fresh={len(fresh)}")
    return DedupResult(fresh=fresh, all_items=list(items), duplicated=duplicated)


# ---------------------------------------------------------------------------
# B2 自测：临时 sqlite 文件，不碰共享库、不访问网络
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    verbose = True

    # 1) sqlite 相对路径锚定：必须落到 services/api/ 下与中台同库
    anchored = _anchor_sqlite("sqlite:///./zhixuntong.db")
    assert anchored.replace("\\", "/").endswith("services/api/zhixuntong.db"), anchored
    assert _anchor_sqlite("sqlite:////abs/path.db") == "sqlite:////abs/path.db"
    assert _anchor_sqlite("sqlite:///:memory:") == "sqlite:///:memory:"
    assert _anchor_sqlite("mysql+pymysql://u:p@h/db") == "mysql+pymysql://u:p@h/db"
    print(f"[selftest] resolved_shared_url={resolve_database_url()}")

    # 2) 临时库端到端：预置 2 条历史数据，构造 4 条批次（1库重复 + 1新 + 1批内重复 + 1库重复）
    tmp_db = Path(tempfile.gettempdir()) / "zxt_dedup_selftest.db"
    tmp_db.unlink(missing_ok=True)
    engine = get_engine(f"sqlite:///{tmp_db}")
    ensure_news_table(engine)

    make_hash = BaseSpider.make_hash

    def history_row(title: str, url: str) -> dict:
        """构造一条已入库的历史新闻（模拟上一次任务的产物）。"""
        return {
            "title": title,
            "published_at": datetime(2026, 8, 10, 9, 0, 0),
            "source": "ev_news",
            "source_url": url,
            "category": "risk",
            "company": None,
            "content": "历史入库的新闻正文，长度超过八十个字的占位内容。" + "详略。" * 20,
            "content_hash": make_hash(title, url),
            "keywords": [],
            "is_duplicate": False,
        }

    with engine.begin() as conn:
        conn.execute(
            sa.insert(news_table).values(
                [
                    history_row("上季度已存在的新闻甲", "https://example.com/n/exists-1"),
                    history_row("上季度已存在的新闻乙", "https://example.com/n/exists-2"),
                ]
            )
        )

    def news_item(title: str, url: str) -> NewsItem:
        """构造一条本次采集到的标准化新闻。"""
        return NewsItem(
            title=title,
            published_at=datetime(2026, 8, 18, 9, 0, 0),
            source="ev_news",
            source_url=url,
            category="other",
            content="本次采集到的新闻正文，长度超过八十个字的占位内容。" + "详略。" * 20,
            content_hash=make_hash(title, url),
        )

    batch = [
        news_item("上季度已存在的新闻甲", "https://example.com/n/exists-1"),  # 库中重复
        news_item("全新新闻丙", "https://example.com/n/new-1"),               # 新
        news_item("全新新闻丙", "https://example.com/n/new-1"),               # 批内重复
        news_item("上季度已存在的新闻乙", "https://example.com/n/exists-2"),  # 库中重复
    ]

    result = dedup(batch, engine)
    assert len(result.fresh) == 1, result
    assert result.duplicated == 3, result
    assert result.all_items[0].is_duplicate and result.all_items[1].is_duplicate is False
    assert result.all_items[2].is_duplicate and result.all_items[3].is_duplicate
    print(f"[selftest] pass1 fresh={len(result.fresh)} duplicated={result.duplicated}")

    # 3) B2 验收场景：fresh 入库后同一批再跑一次 → 新增 0、重复 4
    with engine.begin() as conn:
        conn.execute(
            sa.insert(news_table).values(
                [
                    {
                        "title": item.title,
                        "published_at": item.published_at,
                        "source": item.source,
                        "source_url": item.source_url,
                        "category": item.category,
                        "company": item.company,
                        "content": item.content,
                        "content_hash": item.content_hash,
                        "keywords": item.keywords,
                        "is_duplicate": False,
                    }
                    for item in result.fresh
                ]
            )
        )
    rerun = dedup(batch, engine)
    assert len(rerun.fresh) == 0 and rerun.duplicated == 4, rerun
    print(f"[selftest] pass2 fresh={len(rerun.fresh)} duplicated={rerun.duplicated}")

    # 4) 批次内独立可用（不传 engine，纯内存判重）
    only_batch = dedup(batch[:3])  # 甲(库重复但没查库) + 丙 + 丙
    assert len(only_batch.fresh) == 2 and only_batch.duplicated == 1, only_batch

    engine.dispose()
    tmp_db.unlink(missing_ok=True)
    print("[selftest] ok 跨任务持久化去重 + 批次内去重 均通过")
