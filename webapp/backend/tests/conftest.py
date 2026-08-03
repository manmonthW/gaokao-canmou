"""pytest 配置：保证 app 可在无真实数据库连接的情况下被 import。

db.py 已改为懒加载连接池（import 阶段不连库）；此处仅在缺失时兜底设置
GAOKAO_DSN，避免 config 在 import 时因缺变量而抛错。测试通过 monkeypatch
替换 app.db.fetch_all / fetch_one，不触达真实数据库。
"""
import os

os.environ.setdefault(
    "GAOKAO_DSN",
    "postgresql://dummy:dummy@localhost:5432/dummy",
)
