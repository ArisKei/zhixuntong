# 成员 B：采集服务

契约：`packages/schemas/crawler.py`、`docs/openapi.yaml`。

实现入口：

```python
# services/crawler/runner.py
def run_crawl(source_id: str) -> CrawlResult: ...
```

中台对接：组长把 `CRAWLER_MODE=local` 即可加载本文件。未完成前中台走 mock，不阻塞你。
