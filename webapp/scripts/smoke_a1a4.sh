#!/usr/bin/env bash
# A1–A4 冒烟：classification_note / 保稳分界（safe_line）/ 区间文案 / sensitivity 端点
set -e
BASE=http://127.0.0.1:8000/api/v1
python3 - <<'EOF'
import json, urllib.request, urllib.parse
BASE = 'http://127.0.0.1:8000/api/v1'

def get(path, params):
    return json.load(urllib.request.urlopen(BASE + path + '?' + urllib.parse.urlencode(params)))

params = dict(year=2026, category='普通类', subject='物理学科类', batch='本科批',
              rank=12000, page_size=5)

print('== 1. match: classification_note ==')
d = get('/match', params)
note = d.get('classification_note')
assert note, 'classification_note 缺失'
print('method:', note['method'][:60])
print('safe_margin:', note['safe_margin'])
print('backtest.margin_coverage:', note['backtest']['margin_coverage'][:80])

print('== 2. match: safe_line 与区间文案 ==')
for it in d['items']:
    print(f"  {it['risk']} | safe_line={it.get('safe_line')} | {it['risk_reason'][:50]}")

print('== 3. 保档严格性：保档项位次必须 <= safe_line ==')
bao = get('/match', {**params, 'risk': '保', 'page_size': 10})
for it in bao['items']:
    assert it['safe_line'] and 12000 <= it['safe_line'], it
print('  ok, n=', len(bao['items']), 'totals=', bao['totals'])

print('== 4. sensitivity ==')
s = get('/match/sensitivity', params)
assert 'scenarios' in s, s.get('error')
for sc in s['scenarios']:
    t = sc['totals']
    print(f"  {sc['label']:<14} rank={sc['rank']:>7}  保={t['保']:>6} 稳={t['稳']:>6} 冲={t['冲']:>6}")
print('note:', s['note'][:50])

print('== 5. A4: 提前批 A/B 段别名（若有该批数据） ==')
m = get('/meta', {})
batches = m.get('batches') or []
tb = [b for b in batches if '提前' in b]
print('  提前批相关批次:', tb)

print('ALL SMOKE PASSED')
EOF
