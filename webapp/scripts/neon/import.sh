#!/usr/bin/env bash
# 把分析库导入 Neon，并建好只读 / 可写两个角色。
#
# 用法：
#   NEON_OWNER_URL='postgresql://<owner>:<pw>@<host>/<db>?sslmode=require' \
#   RO_PASSWORD="$(openssl rand -hex 24)" RW_PASSWORD="$(openssl rand -hex 24)" \
#   webapp/scripts/neon/import.sh <dump.sql>
#
# - NEON_OWNER_URL 用 Neon 控制台里的**直连**串（不带 -pooler），导入走长事务。
# - dump 须是纯文本 pg_dump，且已包含 0013–0017 迁移和对应 ETL 数据；脚本导完会检查。
#   推荐导出方式（在当前正式库上）：
#     pg_dump -d gaokao -F p --no-owner --no-privileges --clean --if-exists > gaokao_full.sql
# - 密码只经环境变量传给 psql 变量，不出现在命令行参数和输出里。
# - 可重复执行（dump 带 --clean --if-exists 时会先删后建分析表；app schema 不受影响）。
set -euo pipefail

DUMP="${1:?用法: import.sh <dump.sql>}"
: "${NEON_OWNER_URL:?需要 NEON_OWNER_URL}"
: "${RO_PASSWORD:?需要 RO_PASSWORD}"
: "${RW_PASSWORD:?需要 RW_PASSWORD}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PSQL=(psql "$NEON_OWNER_URL" -v ON_ERROR_STOP=1 -q)

echo "== 1/3 导入 $DUMP"
# pg_dump 16.10+ 会写 \restrict 行，老版本 psql 不认识；过滤掉不影响数据
grep -v -E '^\\(un)?restrict ' "$DUMP" | "${PSQL[@]}" >/dev/null

echo "== 2/3 角色与权限"
"${PSQL[@]}" -v ro_password="$RO_PASSWORD" -v rw_password="$RW_PASSWORD" -f "$HERE/roles.sql" >/dev/null

echo "== 3/3 检查"
"${PSQL[@]}" -tA -F ' ' <<'SQL'
SELECT rpad(t, 26), COALESCE(n::text, '缺表') FROM (VALUES
  ('admission_scores'), ('score_rank'), ('school_profiles'), ('school_hot_profiles'),
  ('major_catalog'), ('subject_requirements'), ('major_admission_summary'),
  ('major_name_map'), ('major_eval_map'), ('major_strengths'), ('school_disciplines'),
  ('major_trend'), ('major_trend_alias')
) AS v(t)
LEFT JOIN LATERAL (
  SELECT (xpath('/row/n/text()', query_to_xml(format('SELECT count(*) AS n FROM public.%I', t), false, true, '')))[1]::text::bigint AS n
  WHERE to_regclass('public.' || t) IS NOT NULL
) c ON true;
SQL
echo "（行数为 0 或“缺表”说明 dump 不完整：对应 ETL 没有导出进来，相关页面会显示为空）"
