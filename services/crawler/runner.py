# -*- coding: utf-8 -*-
"""B9+B10 · run_crawl 入口（契约签名，A 的 local 模式直接加载本文件）

契约（packages/schemas/crawler.py、services/crawler/README.md）：

    def run_crawl(source_id: str) -> CrawlResult

source_id 取值：miit_policy | ev_news | oem_news | all | demo_recall
（名称契约冻结，不自造；未知值 → failed 任务 + 明确错误信息）

全链路编排：
    建任务(running) → 逐源跑 spider → save_items(去重+入库+[db]日志)
    → complete_task(回写统计) → [crawl] finished 日志 → 返回 CrawlResult

B10 容错：单源失败不影响其他源——
    失败源：跳过入库、写 job_log(error)、error_message 汇总进任务行
    全部失败：status=failed；部分失败：status=success + error_message 记录失败源

运行模式（AGENTS.md 约定）：默认 CRAWL_MODE=fixture（离线可跑）；
demo_recall 恒为 fixture（答辩主线不依赖外网），并只保留「召回」新闻（对齐 A 的 Mock 语义）。

加载方式说明：A 用 importlib 从本文件路径加载（spec_from_file_location），
因此模块顶部先把 services/crawler 与 packages 目录塞进 sys.path，
保证 base/dedup/storage/schemas 等兄弟模块在任何进程里都能导入。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# --- sys.path 引导（被 A 的 importlib 加载时也能找到兄弟模块与契约包） ---
CRAWLER_DIR = Path(__file__).resolve().parent
REPO_ROOT = CRAWLER_DIR.parents[1]
for _path in (str(CRAWLER_DIR), str(REPO_ROOT / "packages")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import sqlalchemy as sa  # noqa: E402

import dedup as _dedup  # noqa: E402
from base import MODE_FIXTURE, MODE_LIVE, BaseSpider, NewsItem  # noqa: E402
from dedup import API_DIR, _read_env_files, get_engine  # noqa: E402
from ev_news import EvNewsSpider  # noqa: E402
from miit_policy import MiitPolicySpider  # noqa: E402
from oem_news import OemNewsSpider  # noqa: E402
from schemas.crawler import CrawlResult, CrawlerTaskOut  # noqa: E402  契约包（与 A 共享模块缓存）
from schemas.news import NewsOut  # noqa: E402
from storage import (  # noqa: E402
    complete_task,
    create_task,
    ensure_tables,
    fetch_news_ids,
    log_job,
    save_items,
)

# 数据源注册表：source_id → Spider 类（名称契约冻结）
SPIDERS: dict[str, type[BaseSpider]] = {
    "miit_policy": MiitPolicySpider,
    "ev_news": EvNewsSpider,
    "oem_news": OemNewsSpider,
}

# demo_recall 的筛选口径：标题含「召回」（与 A 的 Mock 同语义，保住答辩主线）
DEMO_RECALL_KEYWORD = "召回"


def resolve_mode() -> str:
    """解析运行模式：环境变量 CRAWL_MODE > .env 文件 > 默认 fixture（离线可跑）。"""
    from_files = _read_env_files(REPO_ROOT / ".env", API_DIR / ".env").get("CRAWL_MODE", "")
    mode = os.environ.get("CRAWL_MODE") or from_files or MODE_FIXTURE
    return mode if mode in (MODE_FIXTURE, MODE_LIVE) else MODE_FIXTURE


def _resolve_sources(source_id: str) -> list[tuple[str, type[BaseSpider], str | None]]:
    """source_id → [(source_id, Spider类, 结果筛选关键词)]。

    筛选关键词仅 demo_recall 使用（恒 fixture + 只留召回新闻）。
    未知 source_id 返回空列表，由 run_crawl 落 failed 任务。
    """
    requested = (source_id or "all").strip()
    if requested in ("all", ""):
        return [(sid, cls, None) for sid, cls in SPIDERS.items()]
    if requested == "demo_recall":
        return [("demo_recall", SPIDERS["ev_news"], DEMO_RECALL_KEYWORD)]
    if requested in SPIDERS:
        return [(requested, SPIDERS[requested], None)]
    return []


def run_crawl(source_id: str = "all") -> CrawlResult:
    """契约入口：一次采集的完整编排（建任务 → 逐源采集入库 → 回写统计 → 返回结果）。

    - 逐源 save_items：每源独立打 [db] 日志、独立去重入库
    - 单源失败：跳过该源继续其他源（B10），失败信息写 job_log + error_message
    - items 返回全部解析条目（重复的标 is_duplicate=True，id 为库中真实行 id）
    """
    requested = (source_id or "all").strip()
    mode = resolve_mode()
    engine = get_engine()
    ensure_tables(engine)

    started_at = datetime.now()
    task_id = create_task(engine, requested)

    totals = {"fetched": 0, "parsed": 0, "dropped_short": 0, "inserted": 0, "duplicated": 0}
    all_items: list[NewsItem] = []
    errors: list[str] = []
    succeeded_sources = 0

    sources = _resolve_sources(requested)
    for source_key, spider_cls, filter_keyword in sources:
        try:
            # demo_recall 恒 fixture（答辩不依赖外网）；其余源按解析出的模式跑
            spider_mode = MODE_FIXTURE if filter_keyword else mode
            spider = spider_cls(mode=spider_mode)
            items, stats = spider.run()
            if filter_keyword:  # demo_recall：只留召回新闻，统计对齐 A 的 Mock 口径
                items = [i for i in items if filter_keyword in i.title]
                stats.fetched = len(items)
                stats.parsed = len(items)
                stats.dropped_short = 0
            out_items, inserted, duplicated = save_items(engine, items)
            all_items.extend(out_items)
            totals["fetched"] += stats.fetched
            totals["parsed"] += stats.parsed
            totals["dropped_short"] += stats.dropped_short
            totals["inserted"] += inserted
            totals["duplicated"] += duplicated
            succeeded_sources += 1
        except Exception as exc:  # B10：单源失败不影响其他源
            message = f"source={spider_cls.source_id} failed: {exc}"
            errors.append(message)
            log_job(engine, message, level="error", extra={"source_id": spider_cls.source_id})
            continue

    # 任务状态：全部失败或未知 source_id → failed；部分失败 → success + 错误备注
    if not sources:
        status = "failed"
        errors.append(f"unknown source_id: {requested}")
        log_job(engine, errors[-1], level="error", extra={"source_id": requested})
    elif succeeded_sources == 0:
        status = "failed"
    else:
        status = "success"
    error_message = "; ".join(errors) or None

    complete_task(
        engine,
        task_id,
        fetched=totals["fetched"],
        parsed=totals["parsed"],
        dropped_short=totals["dropped_short"],
        inserted=totals["inserted"],
        duplicated=totals["duplicated"],
        status=status,
        error_message=error_message,
    )

    # 组装契约返回值：items 回填库中真实 id（重复条目也能对上已有行）
    id_by_hash = fetch_news_ids(engine, [i.content_hash for i in all_items])
    items_out = [
        NewsOut(
            id=id_by_hash.get(item.content_hash, 0),
            title=item.title,
            published_at=item.published_at,
            source=item.source,
            source_url=item.source_url,
            category=item.category,
            company=item.company,
            content=item.content,
            content_hash=item.content_hash,
            keywords=item.keywords,
            is_duplicate=item.is_duplicate,
        )
        for item in all_items
    ]

    # 锁死格式日志（答辩用，格式不可改）
    print(f"[crawl] finished task_id={task_id}")
    engine.dispose()
    return CrawlResult(
        task_id=task_id,
        source_id=requested,
        status=status,
        fetched=totals["fetched"],
        parsed=totals["parsed"],
        dropped_short=totals["dropped_short"],
        inserted=totals["inserted"],
        duplicated=totals["duplicated"],
        error_message=error_message,
        started_at=started_at,
        finished_at=datetime.now(),
        items=items_out,
    )


# ---------------------------------------------------------------------------
# B9+B10 自测：临时库（DATABASE_URL 环境变量切换，不碰共享库）、不访问网络
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    from dedup import news_table
    from storage import crawler_task_table, job_log_table

    def switch_db(path: Path) -> None:
        """切换自测库：改环境变量并清掉 dedup 的引擎缓存（下次 get_engine 用新地址）。"""
        _dedup._engine = None
        os.environ["DATABASE_URL"] = f"sqlite:///{path}"

    tmp_db = Path(tempfile.gettempdir()) / "zxt_runner_selftest.db"
    tmp_db.unlink(missing_ok=True)
    switch_db(tmp_db)

    # 1) 单源：miit_policy → success，6 条入库，契约字段齐全
    result = run_crawl("miit_policy")
    assert result.status == "success" and result.source_id == "miit_policy", result
    assert result.inserted == 6 and result.duplicated == 0, result.model_dump()
    assert len(result.items) == 6
    assert all(i.id > 0 for i in result.items), "items 应回填库中真实 id"
    assert all(i.category == "policy" for i in result.items)
    assert result.error_message is None and result.finished_at is not None
    # A 的消费路径复验：LocalCrawlerClient 正是这么消费返回值的
    CrawlerTaskOut.model_validate(result)

    # 2) all：三源合计 20 条；miit 的 6 条已在第 1 步入库 → 查库判重生效（跨任务去重）
    result_all = run_crawl("all")
    assert result_all.status == "success", result_all.error_message
    assert result_all.inserted == 14 and result_all.duplicated == 6, result_all.model_dump()
    assert result_all.fetched == 20 and result_all.parsed == 20
    assert len(result_all.items) == 20

    # 3) B2 验收（全链路）：同批再跑 all → 新增 0、重复 20，重复条目带标记
    result_rerun = run_crawl("all")
    assert result_rerun.inserted == 0 and result_rerun.duplicated == 20, result_rerun.model_dump()
    assert len(result_rerun.items) == 20
    assert all(i.is_duplicate for i in result_rerun.items)

    # 4) demo_recall：恒 fixture + 只留召回 → 命中已入库的召回新闻（1 条 risk）
    result_demo = run_crawl("demo_recall")
    assert result_demo.status == "success" and result_demo.source_id == "demo_recall"
    assert result_demo.inserted == 0 and result_demo.duplicated == 1  # all 已插入过召回新闻
    assert len(result_demo.items) == 1
    demo_item = result_demo.items[0]
    assert demo_item.category == "risk" and demo_item.company == "XX汽车"
    assert "召回" in demo_item.title and demo_item.is_duplicate

    # 5) 未知 source_id → failed 任务 + 明确错误信息
    result_bad = run_crawl("no_such_source")
    assert result_bad.status == "failed" and "unknown source_id" in (result_bad.error_message or "")

    # 6) 主库任务行落库校验：最新一条 = no_such_source（failed）；news 共 6+14=20 条
    engine = _dedup.get_engine()
    with engine.connect() as conn:
        task_row = conn.execute(
            sa.select(
                crawler_task_table.c.status,
                crawler_task_table.c.inserted,
            ).order_by(crawler_task_table.c.id.desc())
        ).first()
        news_count = conn.execute(sa.select(sa.func.count()).select_from(news_table)).scalar()
    assert task_row[0] == "failed" and task_row[1] == 0, task_row
    assert news_count == 20, news_count
    engine.dispose()

    # 7) B10 验收：一个源 URL 配错（列表页请求失败），另外两个仍成功
    #    走真实失败路径：fetch 抛异常 → run() 冒泡 → runner 源级容错接住
    class _BrokenSpider(MiitPolicySpider):
        """模拟配错 URL 的坏源：列表页请求直接失败（连接被拒）。"""

        def fetch(self, url: str, *, is_list: bool = False, page: int = 1) -> str:
            raise ConnectionError("connection refused (simulated)")

    tmp_db2 = Path(tempfile.gettempdir()) / "zxt_runner_selftest2.db"
    tmp_db2.unlink(missing_ok=True)
    switch_db(tmp_db2)
    saved_miit = SPIDERS["miit_policy"]
    SPIDERS["miit_policy"] = _BrokenSpider
    try:
        result_partial = run_crawl("all")
        assert result_partial.status == "success", result_partial.error_message
        assert result_partial.inserted == 14, result_partial.model_dump()  # 8(ev)+6(oem)，miit 丢失
        assert "miit_policy" in (result_partial.error_message or "")
        engine = _dedup.get_engine()
        with engine.connect() as conn:
            err_rows = conn.execute(
                sa.select(job_log_table.c.level).where(job_log_table.c.job_name == "crawler")
            ).fetchall()
        assert ("error",) in err_rows, err_rows
        engine.dispose()

        # 8) 全部失败 → status=failed
        saved_ev = SPIDERS["ev_news"]
        saved_oem = SPIDERS["oem_news"]
        SPIDERS["ev_news"] = _BrokenSpider
        SPIDERS["oem_news"] = _BrokenSpider
        try:
            tmp_db3 = Path(tempfile.gettempdir()) / "zxt_runner_selftest3.db"
            tmp_db3.unlink(missing_ok=True)
            switch_db(tmp_db3)
            result_allfail = run_crawl("all")
            assert result_allfail.status == "failed", result_allfail.model_dump()
            assert result_allfail.inserted == 0
            _dedup.get_engine().dispose()
            tmp_db3.unlink(missing_ok=True)
        finally:
            SPIDERS["ev_news"] = saved_ev
            SPIDERS["oem_news"] = saved_oem
    finally:
        SPIDERS["miit_policy"] = saved_miit

    tmp_db2.unlink(missing_ok=True)
    tmp_db.unlink(missing_ok=True)
    print("[selftest] B9+B10 验收通过：单源/all/demo_recall/未知源/部分失败/全部失败 全OK")
