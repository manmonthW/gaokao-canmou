#!/usr/bin/env bash
# 跑回测（A1 定 margin 参数）；须从 backend 目录启动以加载 .env 的 GAOKAO_DSN
cd /home/ekewang/projects/gaokao/ln/webapp/backend
./.venv/bin/python ../scripts/backtest_match.py 2>&1 | tee /home/ekewang/projects/gaokao/ln/webapp/scripts/backtest_report.txt
