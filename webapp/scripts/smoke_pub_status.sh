#!/usr/bin/env bash
# 验证 D4 发布状态查询的批次别名展开：查「本科提前批」应能取到 A/B 段登记，不再出现「未登记」警告
set -e
API=http://127.0.0.1:8000/api/v1

PY='
import json,sys
d=json.load(sys.stdin)
bc=d.get("batch_context",{})
pub=bc.get("publication",[])
print("publication rows:",len(pub))
for p in pub: print(" ",p)
print("warning:",bc.get("warning","(none)"))
print("items:",len(d.get("items",[])))
'

echo "=== 2027 考生 普通类 物理学科类 本科批（用户场景：考生年无登记，应回退历史录取年） ==="
curl -s -G "$API/match" \
  --data-urlencode "year=2027" --data-urlencode "category=普通类" \
  --data-urlencode "subject=物理学科类" --data-urlencode "batch=本科批" \
  --data-urlencode "rank=1355" | python3 -c "$PY"

echo
echo "=== 2027 考生 普通类 物理学科类 本科提前批 ==="
curl -s -G "$API/match" \
  --data-urlencode "year=2027" --data-urlencode "category=普通类" \
  --data-urlencode "subject=物理学科类" --data-urlencode "batch=本科提前批" \
  --data-urlencode "rank=12000" | python3 -c "$PY"

echo
echo "=== 2026 普通类 物理学科类 本科批（对照组） ==="
curl -s -G "$API/match" \
  --data-urlencode "year=2026" --data-urlencode "category=普通类" \
  --data-urlencode "subject=物理学科类" --data-urlencode "batch=本科批" \
  --data-urlencode "rank=12000" | python3 -c "$PY"
