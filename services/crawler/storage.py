# -*- coding: utf-8 -*-
"""B8 · 入库模块（news 表 + crawler_task 表写入）

职责（任务卡 B8）：
- 只通过契约（packages/schemas）定义的字段写入，不自造字段
- 写 crawler_task 统计：抓取数/清洗数/新增/重复（fetched/parsed/dropped_short/inserted/duplicated）
- 锁死日志格式（答辩用）：
    [db] inserted=4 duplicated=14     ← save_items 打印
    [crawl] finished task_id=...      ← B9 runner 打印

复用关系：
- 引擎与库地址解析复用 dedup.resolve_database_url / get_engine（与中台同一个库）
- news 表定义复用 dedup.news_table（与冻结契约同构）
- 去重复用 dedup.dedup（批内 + 查库双层判重）

三个原语（B9 runner 编排调用）：
1. create_task(engine, source_id)            → 建 crawler_task 行（running），返回 task_id
2. save_items(engine, items)                 → 去重 + 插入 news，返回 (全部条目含重复标记, inserted, duplicated)
3. complete_task(engine, task_id, **fields)  → 回写统计并完结任务（success/failed）
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa

from base import NewsItem
from dedup import dedup, ensure_news_table, news_table

# ---------------------------------------------------------------------------
# crawler_task 表定义：与冻结契约（services/api/app/models.py 的 CrawlerTask）同构
# ---------------------------------------------------------------------------

crawler_task_table = sa.Table(
    "crawler_task",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("task_id", sa.String(32), unique=True, nullable=False, index=True),
    sa.Column("source_id", sa.String(64), nullable=False),
    sa.Column("status", sa.String(16), nullable=False, default="pending"),
    sa.Column("fetched", sa.Integer, default=0),
    sa.Column("parsed", sa.Integer, default=0),
    sa.Column("dropped_short", sa.Integer, default=0),
    sa.Column("inserted", sa.Integer, default=0),
    sa.Column("duplicated", sa.Integer, default=0),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Column("started_at", sa.DateTime, nullable=True),
    sa.Column("finished_at", sa.DateTime, nullable=True),
)

# job_log 表定义：与冻结契约（services/api/app/models.py 的 JobLog）同构。
# A 每次采集调 start 时会写一条 info 日志；B 在「单源失败」时补写 error 日志（任务卡 B10）。
job_log_table = sa.Table(
    "job_log",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("job_name", sa.String(64), nullable=False, index=True),
    sa.Column("level", sa.String(16), default="info"),
    sa.Column("message", sa.Text, nullable=False),
    sa.Column("extra", sa.JSON, nullable=True),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)


def ensure_tables(engine: sa.Engine) -> None:
    """确保 news / crawler_task / job_log 三张表存在（checkfirst：中台已建则跳过）。"""
    ensure_news_table(engine)
    crawler_task_table.metadata.create_all(
        engine, tables=[crawler_task_table, job_log_table], checkfirst=True
    )


# ---------------------------------------------------------------------------
# 三个原语
# ---------------------------------------------------------------------------

def new_task_id() -> str:
    """生成任务号：12 位十六进制（与中台 Mock 的 uuid4().hex[:12] 同风格）。"""
    return uuid4().hex[:12]


def create_task(engine: sa.Engine, source_id: str, task_id: str | None = None) -> str:
    """建 crawler_task 行（status=running, started_at=now），返回 task_id。"""
    task_id = task_id or new_task_id()
    with engine.begin() as conn:
        conn.execute(
            sa.insert(crawler_task_table).values(
                task_id=task_id,
                source_id=source_id,
                status="running",
                started_at=datetime.now(),
            )
        )
    return task_id


def save_items(engine: sa.Engine, items: list[NewsItem]) -> tuple[list[NewsItem], int, int]:
    """去重（批内+查库）→ 插入新条目 → 返回 (全部条目含重复标记, inserted, duplicated)。

    - 重复条目不插库（news.content_hash 唯一约束兜底），只在返回列表里标 is_duplicate=True
    - 打印锁死日志：[db] inserted=N duplicated=M
    """
    ensure_tables(engine)
    result = dedup(items, engine)  # 双层去重：fresh 待插，all_items 全量标记

    if result.fresh:
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

    # 锁死格式日志（答辩用，格式不可改）
    print(f"[db] inserted={len(result.fresh)} duplicated={result.duplicated}")
    return result.all_items, len(result.fresh), result.duplicated


def complete_task(
    engine: sa.Engine,
    task_id: str,
    *,
    fetched: int = 0,
    parsed: int = 0,
    dropped_short: int = 0,
    inserted: int = 0,
    duplicated: int = 0,
    status: str = "success",
    error_message: str | None = None,
) -> None:
    """回写任务统计并完结（status: success | failed，finished_at=now）。"""
    with engine.begin() as conn:
        conn.execute(
            sa.update(crawler_task_table)
            .where(crawler_task_table.c.task_id == task_id)
            .values(
                fetched=fetched,
                parsed=parsed,
                dropped_short=dropped_short,
                inserted=inserted,
                duplicated=duplicated,
                status=status,
                error_message=error_message,
                finished_at=datetime.now(),
            )
        )


def log_job(
    engine: sa.Engine, message: str, *, level: str = "info", extra: dict | None = None
) -> None:
    """写 job_log（任务卡 B10：单源失败时记 error 日志；格式对齐 A 的 write_job_log）。"""
    with engine.begin() as conn:
        conn.execute(
            sa.insert(job_log_table).values(
                job_name="crawler", level=level, message=message, extra=extra
            )
        )


def fetch_news_ids(engine: sa.Engine, hashes: list[str]) -> dict[str, int]:
    """按 content_hash 查 news 表已有行的 id（B9 组装 CrawlResult.items 时回填真实 id）。"""
    hashes = [h for h in hashes if h]
    if not hashes:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(news_table.c.id, news_table.c.content_hash).where(
                news_table.c.content_hash.in_(hashes)
            )
        ).fetchall()
    return {row[1]: row[0] for row in rows}


# ---------------------------------------------------------------------------
# B8 自测：临时 sqlite 文件，不碰共享库、不访问网络
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from base import BaseSpider

    # 1) 建任务：task_id 风格 + running 状态落库
    tmp_db = Path(tempfile.gettempdir()) / "zxt_storage_selftest.db"
    tmp_db.unlink(missing_ok=True)
    engine = sa.create_engine(f"sqlite:///{tmp_db}", future=True)
    ensure_tables(engine)

    task_id = create_task(engine, "ev_news")
    assert len(task_id) == 12 and task_id == task_id.lower(), task_id
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(crawler_task_table.c.status, crawler_task_table.c.started_at)
        ).fetchone()
    assert row.status == "running" and row.started_at is not None, row

    # 2) save_items：2 新 + 1 批内重复 → inserted=2 duplicated=1，重复条目带标记
    make_hash = BaseSpider.make_hash

    def item(title: str, url: str) -> NewsItem:
        return NewsItem(
            title=title,
            published_at=datetime(2026, 8, 18, 9, 0, 0),
            source="ev_news",
            source_url=url,
            category="tech",
            company=None,
            content="这是一条用于入库自测的新闻正文，长度超过八十个字。" + "内容详实。" * 15,
            keywords=["技术", "电池"],
            content_hash=make_hash(title, url),
        )

    batch = [item("新闻甲", "https://example.com/n/1"), item("新闻乙", "https://example.com/n/2"), item("新闻甲", "https://example.com/n/1")]
    all_items, inserted, duplicated = save_items(engine, batch)
    assert inserted == 2 and duplicated == 1, (inserted, duplicated)
    assert [i.is_duplicate for i in all_items] == [False, False, True]

    # 3) 完结任务：统计回写 + finished_at
    complete_task(engine, task_id, fetched=3, parsed=3, dropped_short=0, inserted=2, duplicated=1)
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(
                crawler_task_table.c.status,
                crawler_task_table.c.fetched,
                crawler_task_table.c.inserted,
                crawler_task_table.c.duplicated,
                crawler_task_table.c.finished_at,
            )
        ).fetchone()
    assert row.status == "success" and row.fetched == 3, row
    assert row.inserted == 2 and row.duplicated == 1 and row.finished_at is not None, row

    # 4) news 表契约字段落库校验（含 keywords JSON 往返）
    with engine.connect() as conn:
        news_row = conn.execute(
            sa.select(
                news_table.c.title,
                news_table.c.source,
                news_table.c.category,
                news_table.c.keywords,
                news_table.c.is_duplicate,
                news_table.c.content_hash,
            ).order_by(news_table.c.id)
        ).fetchall()
    assert len(news_row) == 2
    assert news_row[0].title == "新闻甲" and news_row[0].source == "ev_news"
    assert news_row[0].keywords == ["技术", "电池"], news_row[0].keywords
    assert news_row[0].is_duplicate is False
    assert news_row[0].content_hash == make_hash("新闻甲", "https://example.com/n/1")

    # 5) B2 验收场景（经 storage 全链路）：同批再跑一次 → inserted=0 duplicated=3（批内1+库里2）
    _, inserted2, duplicated2 = save_items(engine, batch)
    assert inserted2 == 0 and duplicated2 == 3, (inserted2, duplicated2)

    # 6) 失败路径：新任务直接 failed + 错误信息回写
    fail_id = create_task(engine, "ev_news")
    complete_task(engine, fail_id, status="failed", error_message="source unreachable")
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(crawler_task_table.c.status, crawler_task_table.c.error_message).where(
                crawler_task_table.c.task_id == fail_id
            )
        ).fetchone()
    assert row.status == "failed" and row.error_message == "source unreachable", row

    engine.dispose()
    tmp_db.unlink(missing_ok=True)
    print("[selftest] B8 验收通过：入库/统计/去重标记/失败路径 全部OK")
