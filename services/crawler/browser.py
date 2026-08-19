# -*- coding: utf-8 -*-
"""B11 · Selenium 无头浏览器取数模块（工信部创宇盾 WAF 的 live 通道）

背景（B11 连通性实测结论）：
- 工信部 www.miit.gov.cn 部署创宇盾（365cyd/Knownsec）WAF：
  requests 裸连与浏览器 UA 均 403，session 重试无效（TLS/浏览器指纹级拦截）
- 第一电动 / 比亚迪：requests + 浏览器头即可（走 base._fetch_live，不经过本模块）

设计：
- 懒加载单例 driver：首次 fetch 才启动 Chrome，整个采集周期复用同一会话
  （首页通过后 cookie 留在会话里，后续详情页同样放行）
- headless=new + 反自动化特征：最大化过 WAF 概率
- fetch(url)：driver.get → 等待 <body> 出现 → 额外等 JS 渲染 → 返回 page_source
- 限速由调用方（BaseSpider._fetch_live_browser）负责，本模块不管节奏
- 依赖缺失时抛 BrowserUnavailableError（源级容错接住 → job_log error，不影响其他源）
"""

from __future__ import annotations

import tempfile
from pathlib import Path


class BrowserUnavailableError(RuntimeError):
    """Selenium/Chrome 环境不可用（未安装依赖或本机无 Chrome）。"""


_driver = None  # 模块级单例：整个进程复用同一浏览器会话

# 页面加载后额外等待秒数：给前端 JS 渲染列表留时间
_RENDER_WAIT = 1.5


def _create_driver():
    """启动无头 Chrome；环境缺失时抛 BrowserUnavailableError。"""
    try:
        from selenium import webdriver
    except ImportError as exc:
        raise BrowserUnavailableError(f"selenium 未安装: {exc}") from exc

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # 新版无头：行为更接近真实浏览器
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=zh-CN")
    # 关闭后台行为：不写崩溃统计/不自动更新/不后台联网（也避免污染运行目录）
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-background-networking")
    # 独立临时 profile：不碰系统 Chrome 的用户配置
    options.add_argument(f"--user-data-dir={Path(tempfile.mkdtemp(prefix='zxt_chrome_'))}")
    # 去掉 navigator.webdriver 等自动化特征（创宇盾会探测）
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.set_capability("pageLoadStrategy", "eager")  # DOM 就绪即返回，不等全部资源

    try:
        driver = webdriver.Chrome(options=options)  # Selenium Manager 自动配 chromedriver
    except Exception as exc:  # WebDriverException 等
        raise BrowserUnavailableError(f"Chrome 启动失败: {exc}") from exc

    # CDP 层再抹一层自动化标记
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
    except Exception:
        pass  # CDP 失败不致命：多数探测已被 options 覆盖
    return driver


def fetch(url: str) -> str:
    """用无头 Chrome 取页面渲染后的 HTML（单例会话复用）。"""
    global _driver
    if _driver is None:
        _driver = _create_driver()
    import time

    _driver.get(url)
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(_driver, 15).until(
            lambda d: d.find_element(By.TAG_NAME, "body")
        )
    except Exception:
        pass  # body 等待超时也继续：eager 策略下 page_source 通常已可用
    if _RENDER_WAIT:
        time.sleep(_RENDER_WAIT)
    return _driver.page_source


def quit() -> None:
    """关闭浏览器会话（进程退出前调用；未启动时是空操作）。"""
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


# ---------------------------------------------------------------------------
# B11 自测：无头 Chrome 实取工信部列表页，验证创宇盾可过
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    URL = "https://www.miit.gov.cn/jgsj/zbys/gzdt/index.html"
    try:
        html = fetch(URL)
    except BrowserUnavailableError as exc:
        print(f"[selftest] SKIP: 浏览器环境不可用（{exc}）")
        raise SystemExit(0)

    hit = "装备工业一司" in html
    blocked = "365cyd" in html or "error_403" in html
    links = html.count("/jgsj/zbys/gzdt/art/")
    print(f"[selftest] miit via headless-chrome: bytes={len(html)} "
          f"expect_hit={hit} waf_block={blocked} art_links={links}")
    assert hit and not blocked, "创宇盾拦截仍未通过"
    assert links >= 5, f"列表页文章链接过少: {links}"
    quit()
    print("[selftest] B11 浏览器通道验收通过：工信部创宇盾可过，列表可解析")
