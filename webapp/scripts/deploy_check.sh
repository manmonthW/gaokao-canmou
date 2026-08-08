#!/usr/bin/env bash
# 部署检查：后端 venv / 前端脚本 / 依赖状态
cd /home/ekewang/projects/gaokao/ln/webapp
echo "== backend dir =="
ls backend/
echo "== backend venv python =="
ls backend/.venv/bin/python 2>/dev/null || ls .venv/bin/python 2>/dev/null || echo "no venv found"
echo "== frontend scripts =="
node -e "console.log(JSON.stringify(require('./frontend/package.json').scripts, null, 2))"
echo "== uvicorn installed? =="
(backend/.venv/bin/python -c "import uvicorn, fastapi; print('backend deps OK')" 2>/dev/null) || \
(python3 -c "import uvicorn, fastapi; print('system deps OK')" 2>/dev/null) || echo "need install"
