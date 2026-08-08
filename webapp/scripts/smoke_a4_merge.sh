#!/usr/bin/env bash
# A4 合并效果抽查：提前批应存在 2025+2026 合并出的两年单元
set -e
python3 - <<'EOF'
import json, urllib.request, urllib.parse
qs = urllib.parse.urlencode({'year': 2026, 'category': '普通类',
                             'subject': '物理学科类', 'batch': '本科提前批',
                             'rank': 12000, 'has_both_years': 'true', 'page_size': 6})
d = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/match?' + qs))
print('has_both_years=true total:', d['totals']['total'])
for i in d['items']:
    yrs = ' / '.join(f"{y['year']}:{y['lowest_rank']}" for y in i['yearly'])
    print(f"  batch={i['batch']} n_years={i['n_years']} {i['school_name'][:14]} {yrs}")
assert d['totals']['total'] > 0, '未找到跨年合并单元，A4 归一未生效'
print('A4 cross-year merge verified')
EOF
