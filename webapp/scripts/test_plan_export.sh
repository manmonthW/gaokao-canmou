#!/bin/bash
# 复测：score/rank/last_year_score 为空字符串时导出应不再 422
sleep 1
BODY='{"plan_name":"测试方案","examinee":{"year":2027,"category":"普通类","subject":"物理学科类","batch":"本科批","score":"","rank":""},"items":[{"risk":"稳","school_code":"0260","school_name":"太原理工大学","major_code":"01","major_name":"计算机科学与技术","last_year":2026,"last_year_score":"","last_year_rank":12345,"rank_diff_last":""}]}'
curl -s --noproxy '*' -o /tmp/plan_test.xlsx -w "HTTP %{http_code}, %{size_download} bytes\n" \
  -X POST http://127.0.0.1:8000/api/v1/plan/export \
  -H "Content-Type: application/json" -d "$BODY"
file /tmp/plan_test.xlsx
# 对照：正常数值也应照常工作
BODY2='{"plan_name":"正常","examinee":{"year":2027,"category":"普通类","subject":"物理学科类","batch":"本科批","score":580.5,"rank":30000},"items":[{"risk":"冲","school_name":"大连理工","major_name":"软件工程","last_year_rank":25000}]}'
curl -s --noproxy '*' -o /tmp/plan_test2.xlsx -w "HTTP %{http_code}, %{size_download} bytes\n" \
  -X POST http://127.0.0.1:8000/api/v1/plan/export \
  -H "Content-Type: application/json" -d "$BODY2"
file /tmp/plan_test2.xlsx
