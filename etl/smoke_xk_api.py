#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 层抽查：确认 /api/v1/match 返回 subject_match_level / subject_status。"""
import json
import urllib.parse
import urllib.request
from collections import Counter

BASE = "http://127.0.0.1:8000/api/v1"
url = BASE + "/match?" + urllib.parse.urlencode({
    "year": 2027, "category": "普通类", "subject": "物理学科类",
    "batch": "本科批", "rank_lo": 11000, "rank_hi": 13000,
    "electives": "化学,生物", "page": 1, "page_size": 50})
d = json.load(urllib.request.urlopen(url))
items = d.get("items", [])
lv = Counter(i.get("subject_match_level") for i in items)
st = Counter(i.get("subject_status") for i in items)
print("excluded:", d.get("excluded_by_subject"),
      "first:", d.get("excluded_first"), "re:", d.get("excluded_re"))
print("match_level:", dict(lv))
print("status:", dict(st))
assert items and "subject_match_level" in items[0], "新字段缺失"
for i in items[:5]:
    print("  ", i["school_name"], "|", i["major_name"],
          "| level=", i.get("subject_match_level"),
          "| req=", i.get("subject_req"), "| status=", i.get("subject_status"))
print("API 抽查 OK")
