#!/usr/bin/env bash
# 等待 3 个 enrichment worker 结束后，跑一次续跑(resume)以补齐偶发失败，并输出最终统计。
PIDS=$(cat /tmp/worker_pids 2>/dev/null)
for p in $PIDS; do
  while kill -0 "$p" 2>/dev/null; do sleep 20; done
done
echo "ALL WORKERS DONE at $(date)" 

cd /home/ekewang/projects/gaokao/ln/webapp/backend
./.venv/bin/python /home/ekewang/projects/gaokao/ln/etl/enrich_schools.py --sleep 0.3 >/tmp/enrich_finish.log 2>&1
echo "RESUME PASS DONE at $(date)" >> /tmp/enrich_finish.log

# 最终统计
PW=$(PGPASSWORD=gk_wr_7b21de psql -U gaokao_writer -h localhost -d gaokao -t -c "SELECT count(*) FROM school_profiles WHERE enriched_at IS NOT NULL;" | tr -d ' ')
REV=$(wc -l < /home/ekewang/projects/gaokao/ln/etl/enrich_review.jsonl 2>/dev/null || echo 0)
echo "FINAL enriched=$PW  missing_website_review=$REV" >> /tmp/enrich_finish.log
