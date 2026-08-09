#!/usr/bin/env bash
# P1–P6 产品层冒烟：估位 / 区间匹配 / 同档排序 / 反馈闭环 / 征集参考
python3 - <<'EOF'
import json, urllib.request, urllib.parse

BASE = 'http://127.0.0.1:8000/api/v1'

def get(path, params=None):
    url = BASE + path + (('?' + urllib.parse.urlencode(params)) if params else '')
    return json.load(urllib.request.urlopen(url))

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req))

def line(title):
    print('\n==', title, '==')

meta = get('/meta')
# 产品层能力面向普通类考生；categories[0] 可能是体育类/艺术类，固定取普通类
cat = '普通类' if '普通类' in (meta.get('categories') or []) else (meta.get('categories') or ['普通类'])[0]
batches_by_cat = meta.get('batches_by_category') or {}
batch = next((b for b in batches_by_cat.get(cat, []) if '本科' in b),
             (batches_by_cat.get(cat) or ['本科批'])[0])

# ---- P1b 线差法估位 ----
line('P1b /locate/estimate-rank')
d = get('/locate/estimate-rank', {'category': cat, 'subject': '物理学科类',
                                  'score': 580, 'mock_line': 430, 'batch': batch})
print(json.dumps(d, ensure_ascii=False)[:500])

# ---- P1a 区间匹配（rank_lo / rank_hi 双档） ----
line('P1a /match 区间模式')
d = get('/match', {'year': 2027, 'category': cat, 'subject': '物理学科类',
                   'batch': batch, 'rank_lo': 11000, 'rank_hi': 13000,
                   'page_size': 5})
print('totals:', json.dumps(d.get('totals'), ensure_ascii=False))
print('totals_lo:', json.dumps(d.get('totals_lo'), ensure_ascii=False))
u = d.get('items', [])
print('items:', len(u))
if u:
    it = u[0]
    print('first item risk/risk_lo:', it.get('risk'), '/', it.get('risk_lo'),
          '| has school_tier:', 'school_tier' in it, '| city_tier:', it.get('city_tier'))

# ---- 冲稳保边界治理：safe_band / over_safe / over_reach ----
line('边界治理标记（safe_band 三分段 + 过深/超冲）')
assert all(c.get('safe_band') in ('标准保底', '极稳垫底', '过深保底') for c in u if c['risk'] == '保'), '保档必须携带子档'
assert all((c.get('safe_band') == '过深保底') == bool(c.get('over_safe')) for c in u if c['risk'] == '保'), 'over_safe 与过深保底子档必须一致'
assert all(c['risk'] == '冲' for c in u if c.get('over_reach')), 'over_reach 只应出现在冲档'
print('首页一致性 OK（首页为保档最贴近项，超冲/过深示例见下方分区采样）')
# 最接近匹配排序：保池首页＝最浅（最好）保底，不应出现 over_safe；
# 过深项沉到保池尾部（totals保 11973 → page 239）；冲档超冲在冲区尾部页采样
dd = get('/match', {'year': 2027, 'category': cat, 'subject': '物理学科类',
                    'batch': batch, 'rank_lo': 11000, 'rank_hi': 13000,
                    'page_size': 50, 'page': 1})
tail = dd.get('items', [])
assert all(c['risk'] == '保' for c in tail), f'page=1 应仍在保池，实际档位: {sorted(set(c["risk"] for c in tail))}'
assert not any(c.get('over_safe') for c in tail), '最接近匹配排序下，首页不应出现过深保底'
print('首页 over_safe 为空 OK（最浅保底在前）; 首页示例:', tail[0]['school_name'], 'best=', tail[0]['best_rank'])
dd = get('/match', {'year': 2027, 'category': cat, 'subject': '物理学科类',
                    'batch': batch, 'rank_lo': 11000, 'rank_hi': 13000,
                    'page_size': 50, 'page': 239})
tail = dd.get('items', [])
assert all(c['risk'] == '保' for c in tail), f'page=239 应仍在保池，实际档位: {sorted(set(c["risk"] for c in tail))}'
ov = [c for c in tail if c.get('over_safe')]
assert ov, '保池尾部（最远端）应存在 over_safe 项'
print('保池尾部 over_safe 示例:', ov[0]['school_name'], 'best=', ov[0]['best_rank'], '(R_hi×3=', 13000 * 3, ')')
dc = get('/match', {'year': 2027, 'category': cat, 'subject': '物理学科类',
                    'batch': batch, 'rank_lo': 11000, 'rank_hi': 13000,
                    'page_size': 50, 'page': 304})
citems = dc.get('items', [])
assert all(c['risk'] == '冲' for c in citems), f'page=304 应仍在冲区，实际档位: {sorted(set(c["risk"] for c in citems))}'
far = [c for c in citems if c.get('over_reach')]
assert far, '冲档区尾部应存在 over_reach 项'
print('冲区 over_reach 示例:', far[0]['school_name'], 'best=', far[0]['best_rank'], '(R_hi×0.8=', int(13000 * 0.8), ')')

# ---- P5 同档排序偏好 ----
line('P5 pref_sort=level vs certainty（同档内排序）')
base = {'year': 2027, 'category': cat, 'subject': '物理学科类',
        'batch': batch, 'rank': 12000, 'risk': '稳', 'page_size': 6}
a = get('/match', {**base, 'pref_sort': 'certainty'})
b = get('/match', {**base, 'pref_sort': 'level'})
c = get('/match', {**base, 'pref_sort': 'city'})
for name, x in [('certainty', a), ('level', b), ('city', c)]:
    seq = [(i.get('school_tier'), i.get('city_tier'), i.get('rank_diff_last')) for i in x.get('items', [])]
    print(name, '->', seq)
# 最接近匹配原则：certainty 序列的 |位次差| 必须非递减
near = [abs(i['rank_diff_last']) for i in a.get('items', []) if i.get('rank_diff_last') is not None]
assert near == sorted(near), f'certainty 应按接近度升序: {near}'

# ---- P4 反馈闭环（匿名提交 + 汇总） ----
line('P4 POST /feedback（匿名）+ summary')
r = post('/feedback', {'examinee_year': 2026, 'category': cat, 'subject': '物理学科类',
                       'batch': batch, 'examinee_rank': 12000, 'plan_total': 60,
                       'outcome': 'admitted', 'admitted_order': 7,
                       'admitted_risk': '稳', 'admitted_school': '冒烟测试大学',
                       'admitted_major': '冒烟专业', 'note': 'smoke'})
print('post:', r)
bad = post('/feedback', {'examinee_year': 2026, 'outcome': 'admitted'})
print('post(admitted 无序号) ->', bad)
s = get('/feedback/summary')
print('summary:', json.dumps(s, ensure_ascii=False))

# ---- D2b 选科要求（2027 官方三表） ----
line('D2b 选科要求硬过滤 + 行级展示')
x = get('/match', {'year': 2027, 'category': cat, 'subject': '物理学科类', 'batch': batch,
                   'rank_lo': 11000, 'rank_hi': 13000, 'electives': '化学,生物',
                   'page': 1, 'page_size': 5})
assert x.get('subject_requirements_loaded'), '选科要求应已入库'
assert (x.get('excluded_re') or 0) > 0, '要求思想政治的单元应被排除'
print('物理类+化学/生物: excluded:', x['excluded_by_subject'],
      '(首选', x.get('excluded_first'), '/ 再选', x.get('excluded_re'), ')',
      '| 首页 subject_req:', [i.get('subject_req') for i in x.get('items', [])])
h = get('/match', {'year': 2027, 'category': cat, 'subject': '历史学科类', 'batch': batch,
                   'rank': 3000, 'electives': '政治,地理', 'page': 1, 'page_size': 5})
assert (h.get('excluded_first') or 0) > 0, '历史类应排除首选物理的单元'
print('历史类+政治/地理: excluded:', h['excluded_by_subject'],
      '(首选', h.get('excluded_first'), '/ 再选', h.get('excluded_re'), ')')
h0 = get('/match', {'year': 2027, 'category': cat, 'subject': '历史学科类', 'batch': batch,
                    'rank': 3000, 'page': 1, 'page_size': 5})
assert (h0.get('excluded_first') or 0) > 0, '首选过滤应无条件生效（未填再选）'
assert (h0.get('excluded_re') or 0) == 0, '未填再选不应排除再选不符'
print('历史类·未填再选: excluded:', h0['excluded_by_subject'],
      '(首选', h0.get('excluded_first'), '/ 再选', h0.get('excluded_re'), ')')

# ---- P6 往年征集参考 ----
line('P6 /datacenter/collection-reference')
d = get('/datacenter/collection-reference', {'category': cat, 'subject': '物理学科类',
                                             'rank': 40000})
print('band:', d.get('band'), '| items:', len(d.get('items', [])))
print('note:', d.get('note'))
if d.get('items'):
    print('sample:', json.dumps(d['items'][0], ensure_ascii=False))
d2 = get('/datacenter/collection-reference', {'category': cat})
print('no-rank items:', len(d2.get('items', [])))
EOF
