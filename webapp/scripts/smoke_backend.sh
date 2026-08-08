#!/usr/bin/env bash
# 后端冒烟测试：meta 应含 major_flags；matrix 端点；match 带 flags/batch_context
sleep 3
echo "== backend log tail =="
tail -n 5 /home/ekewang/projects/gaokao/ln/webapp/scripts/backend.log
echo "== GET /api/v1/meta (major_flags) =="
curl -s http://127.0.0.1:8000/api/v1/meta | python3 -c "import json,sys; d=json.load(sys.stdin); print('major_flags:', json.dumps(d.get('major_flags'), ensure_ascii=False)[:400])" || echo META_FAIL
echo "== GET /api/v1/data-status/matrix =="
curl -s "http://127.0.0.1:8000/api/v1/data-status/matrix" | python3 -c "import json,sys; d=json.load(sys.stdin); print('matrix rows:', len(d.get('matrix',[])), 'unregistered:', len(d.get('unregistered',[])))" || echo MATRIX_FAIL
echo "== GET /api/v1/match smoke =="
python3 - <<'EOF'
import json, urllib.request, urllib.parse
meta = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/meta'))
cat = (meta.get('categories') or ['普通类'])[0]
batches = meta.get('batches') or []
batch = next((b for b in batches if '普通' in b), batches[0] if batches else '普通批')
qs = urllib.parse.urlencode({'year': 2026, 'category': cat, 'subject': '物理学科类', 'batch': batch, 'score': 600, 'rank': 12000, 'page_size': 3})
d = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/match?' + qs))
print('items:', len(d.get('items', [])))
print('batch_context:', json.dumps(d.get('batch_context'), ensure_ascii=False)[:400])
print('excluded_by_subject:', d.get('excluded_by_subject'))
u = d.get('items', [])
print('first unit flags:', u[0].get('flags') if u else None)
EOF
