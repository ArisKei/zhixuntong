# 成员 B：采集服务

契约：`packages/schemas/crawler.py`、`docs/openapi.yaml`。

## 安装依赖

项目要求 Python 3.9+。在仓库根目录执行：

```powershell
python -m pip install -r services/crawler/requirements.txt
```

其中 Selenium 仅供 `live` 模式的浏览器采集通道使用；运行 live 模式还需要本机安装 Chrome。默认 `CRAWL_MODE=fixture`，不会访问网络。

实现入口：

```python
# services/crawler/runner.py
def run_crawl(source_id: str) -> CrawlResult: ...
```

## 运行与中台对接

离线自测（使用临时 SQLite，不访问网络、不修改共享数据库）：

```powershell
python services/crawler/runner.py
```

中台对接时，在中台 `.env` 中设置 `CRAWLER_MODE=local`。B 的采集模式使用另一个变量 `CRAWL_MODE`：

- `CRAWL_MODE=fixture`：默认，读取 `fixtures/html`。
- `CRAWL_MODE=live`：访问真实站点，浏览器通道需要 Selenium 和 Chrome。

未切换到 `local` 前，中台仍可使用 `CRAWLER_MODE=mock` 独立运行。
