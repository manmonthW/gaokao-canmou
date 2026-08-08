#!/usr/bin/env bash
# 全量单测（P1–P6 产品层 + 既有算法层）
set -e
cd /home/ekewang/projects/gaokao/ln/webapp/backend
./.venv/bin/python -m pytest tests -q
