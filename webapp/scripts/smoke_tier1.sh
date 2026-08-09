#!/bin/bash
# 第一梯队冒烟：报考说明扩容 / 选科组合 / 保研率
sleep 3
B=http://127.0.0.1:8000/api/v1

echo "== 1. 报考说明（应 17 份全 available）=="
curl -s --noproxy '*' "$B/guides" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("total:", d["total"])
missing = [(g["key"], it["id"]) for g in d["groups"] for it in g["items"] if not it["available"]]
print("groups:", [(g["key"], len(g["items"])) for g in d["groups"]])
print("missing:", missing if missing else "无")
'

echo "== 2. 子目录 PDF 下载抽查（军校体检规定）=="
curl -s --noproxy '*' -o /tmp/tj.pdf -w "HTTP %{http_code}, %{size_download} bytes\n" "$B/guides/junxiao-tijian/pdf"
file /tmp/tj.pdf

echo "== 3. 选科组合元数据 =="
curl -s --noproxy '*' "$B/meta/subject-combos" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("items:", len(d["items"]), "| overview_available:", d["overview_available"])
print("all available:", all(i["available"] for i in d["items"]))
wl = [i for i in d["items"] if i["first"] == "物理"]
print("物理组合:", [(i["id"], i["coverage"]) for i in wl])
'

echo "== 4. 组合分析图 + 总览图 =="
curl -s --noproxy '*' -o /tmp/combo.jpg -w "combo: HTTP %{http_code}, %{size_download} bytes, %{content_type}\n" "$B/meta/subject-combos/wl-hx-sw/image"
curl -s --noproxy '*' -o /tmp/ov.png -w "overview: HTTP %{http_code}, %{size_download} bytes, %{content_type}\n" "$B/meta/subject-combos/overview/image"
curl -s --noproxy '*' -o /dev/null -w "未知id: HTTP %{http_code}\n" "$B/meta/subject-combos/no-such/image"

echo "== 5. 保研率：搜索接口 =="
curl -s --noproxy '*' --get "$B/search/schools" --data-urlencode "q=大连理工" -d "limit=3" | python3 -c '
import json, sys
for r in json.load(sys.stdin):
    print(r["name"], "| postgrad_rate:", r["postgrad_rate"])
'

echo "== 6. 保研率：院校详情 profile =="
CODE=$(curl -s --noproxy '*' --get "$B/search/schools" --data-urlencode "q=浙江大学" -d "limit=1" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["code"] if d else "")')
echo "浙江大学 code=$CODE"
curl -s --noproxy '*' "$B/schools/$CODE" | python3 -c '
import json, sys
p = json.load(sys.stdin).get("profile") or {}
print("postgrad_rate:", p.get("postgrad_rate"))
'
