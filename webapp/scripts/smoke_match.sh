#!/usr/bin/env bash
python3 - <<'EOF'
import json, urllib.request, urllib.parse
base = 'http://127.0.0.1:8000/api/v1'
qs = urllib.parse.urlencode({'year': 2026, 'category': '普通类', 'subject': '物理学科类',
                             'batch': '本科批', 'score': 600, 'rank': 12000,
                             'page_size': 5})
d = json.load(urllib.request.urlopen(base + '/match?' + qs))
print('keys:', list(d.keys()))
print('error:', d.get('error'))
print('total:', d.get('total'))
print('examinee:', json.dumps(d.get('examinee'), ensure_ascii=False))
bc = d.get('batch_context') or {}
print('score_kind:', bc.get('score_kind'), '| warning:', bc.get('warning'))
print('publication:', json.dumps(bc.get('publication'), ensure_ascii=False)[:250])
items = d.get('items', [])
print('items:', len(items), '| totals:', json.dumps(d.get('totals'), ensure_ascii=False))
for u in items[:3]:
    print(' ', u.get('school_name'), u.get('major_name'),
          'risk=', u.get('risk'), 'flags=', u.get('flags'))
EOF
