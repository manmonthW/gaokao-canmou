#!/usr/bin/env bash
# A4 验证：2026 本科提前批（库内为 A/B 段）应与 2025 本科提前批合并为同一单元
set -e
python3 - <<'EOF'
import json, urllib.request, urllib.parse
qs = urllib.parse.urlencode({'year': 2026, 'category': '普通类',
                             'subject': '物理学科类', 'batch': '本科提前批',
                             'rank': 12000, 'page_size': 8})
d = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/match?' + qs))
print('total:', d['totals']['total'], 'items:', len(d['items']))
both = 0
for i in d['items']:
    print(f"  batch={i['batch']:<10} n_years={i['n_years']} has_both_years={i['has_both_years']} {i['school_name'][:14]} {(i['major_name'] or '')[:14]}")
    if i['has_both_years']:
        both += 1
        # 口径统一：两年都有位次 ⇒ n_years 必为 2
        assert i['n_years'] == 2, i
print('A4 merge ok, has_both_years count:', both)
EOF
