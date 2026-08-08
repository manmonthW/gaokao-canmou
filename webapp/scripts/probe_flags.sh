#!/usr/bin/env bash
# 探查打标关键词在库内的分布（只读），供 load_major_flags.py 规则设计
set -e
cd /home/ekewang/projects/gaokao/ln
export PGPASSWORD=gaokao123
PSQL="psql -U gaokao -h localhost -d gaokao"

echo "== major_name 含「合作」=="
$PSQL -c "SELECT major_name, count(*) FROM admission_scores WHERE major_name LIKE '%合作%' GROUP BY major_name ORDER BY count DESC LIMIT 15;"
echo "== major_name 含「定向」=="
$PSQL -c "SELECT major_name, count(*) FROM admission_scores WHERE major_name LIKE '%定向%' GROUP BY major_name ORDER BY count DESC LIMIT 15;"
echo "== major_name 含「预科」=="
$PSQL -c "SELECT major_name, count(*) FROM admission_scores WHERE major_name LIKE '%预科%' GROUP BY major_name ORDER BY count DESC LIMIT 15;"
echo "== major_name 含「民族」=="
$PSQL -c "SELECT major_name, count(*) FROM admission_scores WHERE major_name LIKE '%民族%' GROUP BY major_name ORDER BY count DESC LIMIT 15;"
echo "== school_name 括号地名（异地校区候选）=="
$PSQL -c "SELECT school_name, count(*) FROM admission_scores WHERE school_name ~ '\((威海|深圳|盘锦|烟台|秦皇岛|宁波|苏州|温州|汕头|珠海|嘉兴|泰安|威海校区|深圳校区)\)' OR school_name LIKE '%分校%' GROUP BY school_name ORDER BY count DESC LIMIT 20;"
