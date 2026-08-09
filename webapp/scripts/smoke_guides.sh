#!/bin/bash
# 报考说明 API 抽查：元数据 + PDF 下载
sleep 3
B=http://127.0.0.1:8000/api/v1/guides
echo "== 元数据 =="
curl -s --noproxy '*' "$B" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("total:", d["total"], "| note:", d["note"][:40], "...")
for g in d["groups"]:
    print("[%s] %s" % (g["key"], g["title"]))
    for it in g["items"]:
        print("  - %s: avail=%s size=%s tag=%s" % (it["id"], it["available"], it["size_bytes"], it["tag"]))
'
echo "== PDF 抽查（招生简章）=="
curl -s --noproxy '*' -o /tmp/guide_test.pdf -w "HTTP %{http_code}, %{size_download} bytes, %{content_type}\n" "$B/zhaosheng-jianzhang/pdf"
file /tmp/guide_test.pdf
echo "== 未知 id 应 404 =="
curl -s --noproxy '*' -o /dev/null -w "HTTP %{http_code}\n" "$B/../etc/passwd/pdf"
curl -s --noproxy '*' -o /dev/null -w "HTTP %{http_code}\n" "$B/no-such-id/pdf"
