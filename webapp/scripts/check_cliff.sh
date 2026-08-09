#!/bin/bash
# 临时验证：断崖变易单元的稳档文案（R=1355，药科大学类）
curl -s 'http://127.0.0.1:8000/api/v1/match?year=2027&category=%E6%99%AE%E9%80%9A%E7%B1%BB&subject=%E7%89%A9%E7%90%86%E5%AD%A6%E7%A7%91%E7%B1%BB&batch=%E6%9C%AC%E7%A7%91%E6%89%B9&rank=1355&major_keyword=%E8%8D%AF%E5%AD%A6&risk=%E7%A8%B3' | python3 -c '
import json, sys
d = json.load(sys.stdin)
for i in d["items"]:
    print(i["school_name"], i["major_name"], "best=", i["best_rank"], "last=", i["last_year_rank"])
    print("  reason:", i["risk_reason"])
'
