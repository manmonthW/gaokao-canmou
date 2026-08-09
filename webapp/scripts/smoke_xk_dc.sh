#!/bin/bash
# 选科要求三表 API 抽查
B=http://127.0.0.1:8000/api/v1/datacenter
echo "== summary =="
curl -s --noproxy '*' "$B/subject-requirements/summary" | python3 -m json.tool
echo "== 默认第一页（前2行）=="
curl -s --noproxy '*' "$B/subject-requirements?page=1&page_size=2" | python3 -m json.tool
echo "== 军校表 jx =="
curl -s --noproxy '*' "$B/subject-requirements?table=jx&page_size=2" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("total:", d["total"]); [print(i["school_name"], i["major_name"], i["first_req"], i["re_req"]) for i in d["items"]]'
echo "== 院校+专业+首选组合：大连理工·物理 =="
curl -s --noproxy '*' --get "$B/subject-requirements" --data-urlencode "school=大连理工" --data-urlencode "first_req=物理" --data-urlencode "table=bk" -d "page_size=3" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("total:", d["total"]); [print(i["school_name"], i["major_name"], "|", i["first_req"], "|", i["re_req"]) for i in d["items"]]'
