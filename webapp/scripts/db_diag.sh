#!/usr/bin/env bash
# 诊断数据库位置：docker 容器 / 本机 postgres 服务
echo "== docker ps =="
docker ps -a 2>&1 | head -10 || true
echo "== pg service =="
service postgresql status 2>&1 | head -5 || true
pg_lsclusters 2>/dev/null || true
echo "== any postgres process =="
ps aux 2>/dev/null | grep -i [p]ostgres | head -5 || echo "no postgres process"
echo "== listening 5432 =="
ss -ltn 2>/dev/null | grep 5432 || echo "nothing on 5432"
