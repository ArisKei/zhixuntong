# 智讯通

先看这一份：**[小白协作说明书](docs/小白协作说明书.md)**  
（组长做了什么、组员做什么、怎么整合，都在里面。）

---

## 组长快速启动中台

需要 Python 3.9+。

```powershell
cd D:\DABIANPRO\services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run.ps1
```

- 健康检查：http://127.0.0.1:8000/health  
- 接口文档：http://127.0.0.1:8000/docs  
- 账号：`demo` / `demo123`

**Token 怎么拿：** 先调 `POST /api/auth/login`，复制返回的 `access_token`，点右上角 Authorize 粘贴。

**演示顺序：** login → crawler/start(`demo_recall`) → news → alert/evaluate → notify/dingtalk

## 目录谁负责

| 人 | 目录 |
|---|---|
| 组长 A | `services/api`、`packages/schemas`、`docs/` |
| 成员 B | `services/crawler` |
| 成员 C | `services/rag` |
| 成员 D | `services/ai` |
| 成员 E | `apps/web`、`services/notify` |
