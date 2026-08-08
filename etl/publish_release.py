#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_release.py —— 数据发布流水线（D5 时效性 SLA）。

把「官方发布 → 数据库可查」固化成一条可重复执行的流水线，
任一步失败即中止，保证 draft 不会带着问题被发布。

子命令：
  check                只读体检：发布矩阵时效性 + 各表行数 + 位次覆盖
  prepare  --version X [--skip-backfill] [--skip-verify]
                       1) 回填 lowest_rank  2) verify_all 对账  3) 建 draft 发布
  publish  --version X [--publisher NAME]
                       draft → published（唯一对外可见的切换动作）
  rollback --version X published → rolled_back

运行（写库角色）:
  python3 etl/publish_release.py check
  python3 etl/publish_release.py prepare --version 2026.2
  python3 etl/publish_release.py publish --version 2026.2 --publisher ops
"""
import argparse
import subprocess
import sys

import psycopg2

from config import DSN

ETL_DIR = "etl"


def _stats(cur):
    out = {}
    for t in ("admission_scores", "schools", "school_profiles",
              "score_rank", "batch_control_line", "subject_requirements"):
        cur.execute(f"SELECT count(*) FROM {t}")
        out[t] = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM admission_scores WHERE flags <> '{}'")
    out["flagged_rows"] = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*), count(lowest_rank) FROM admission_scores "
        "WHERE score_kind='投档最低分' AND lowest_score IS NOT NULL")
    n, with_rank = cur.fetchone()
    out["rank_coverage"] = f"{with_rank}/{n}" if n else "0/0"
    return out


def _freshness(cur):
    """官方已发布但库内无对应录取行的批次（时效性缺口）。"""
    cur.execute(
        """SELECT p.year, p.category, p.subject, p.batch, p.stage,
                  COALESCE(a.cnt, 0) AS cnt
           FROM admission_publication_status p
           LEFT JOIN (
             SELECT year, category, subject, batch, count(*) AS cnt
             FROM admission_scores
             GROUP BY 1,2,3,4
           ) a ON a.year=p.year AND a.category=p.category
              AND a.subject=p.subject AND a.batch=p.batch
           WHERE p.status IN ('部分发布','已完成')
           ORDER BY p.year, p.category, p.subject, p.batch""")
    return cur.fetchall()


def cmd_check(cur, conn):
    print("== 表行数/覆盖 ==")
    for k, v in _stats(cur).items():
        print(f"   {k}: {v}")
    print("\n== 时效性矩阵（官方已发布但库内无数据的批次）==")
    gaps = [r for r in _freshness(cur) if r[5] == 0]
    if not gaps:
        print("   （无缺口）")
    for y, c, s, b, st, cnt in gaps:
        print(f"   [缺口] {y} {c} {s} {b} ({st})")
    print("\n== 当前发布 ==")
    cur.execute("SELECT version, status, published_at FROM data_releases "
                "ORDER BY id DESC LIMIT 5")
    for v, st, at in cur.fetchall():
        print(f"   {v} [{st}] {at}")


def _run_step(name, argv):
    print(f"\n---- 步骤: {name} ----")
    r = subprocess.run(argv, cwd=ETL_DIR)
    if r.returncode != 0:
        print(f"[中止] {name} 退出码 {r.returncode}，流水线停止，未改动发布状态")
        sys.exit(r.returncode)


def cmd_prepare(cur, conn, args):
    cur.execute("SELECT 1 FROM data_releases WHERE version=%s", (args.version,))
    if cur.fetchone():
        print(f"[中止] 版本 {args.version} 已存在")
        sys.exit(1)
    if not args.skip_backfill:
        _run_step("回填 lowest_rank", ["python3", "backfill_lowest_rank.py"])
    if not args.skip_verify:
        _run_step("verify_all 对账", ["python3", "verify_all.py"])

    cur.execute("SELECT DISTINCT year FROM admission_scores ORDER BY year")
    years = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT category FROM admission_scores ORDER BY 1")
    cats = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT batch FROM admission_scores ORDER BY 1")
    batches = [r[0] for r in cur.fetchall()]
    stats = _stats(cur)
    summary = "; ".join(f"{k}={v}" for k, v in stats.items())
    cur.execute(
        """INSERT INTO data_releases
           (version, covered_years, covered_categories, covered_batches,
            status, quality_summary)
           VALUES (%s, %s, %s, %s, 'draft', %s)""",
        (args.version, years, cats, batches, summary))
    conn.commit()
    print(f"\ndraft 已创建: {args.version}")
    print(f"质量摘要: {summary}")
    print("下一步人工抽查后执行: "
          f"python3 etl/publish_release.py publish --version {args.version}")


def cmd_publish(cur, conn, args):
    cur.execute("SELECT status FROM data_releases WHERE version=%s",
                (args.version,))
    row = cur.fetchone()
    if not row or row[0] != "draft":
        print(f"[中止] 版本 {args.version} 不存在或状态不是 draft")
        sys.exit(1)
    cur.execute(
        "UPDATE data_releases SET status='published', publisher=%s, "
        "published_at=now() WHERE version=%s",
        (args.publisher, args.version))
    conn.commit()
    print(f"已发布: {args.version}（Web 端 /data-status 将切换到该版本）")


def cmd_rollback(cur, conn, args):
    cur.execute(
        "UPDATE data_releases SET status='rolled_back' "
        "WHERE version=%s AND status='published'", (args.version,))
    conn.commit()
    print(f"已回滚: {args.version}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p = sub.add_parser("prepare")
    p.add_argument("--version", required=True)
    p.add_argument("--skip-backfill", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    p = sub.add_parser("publish")
    p.add_argument("--version", required=True)
    p.add_argument("--publisher", default="ops")
    p = sub.add_parser("rollback")
    p.add_argument("--version", required=True)
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    try:
        if args.cmd == "check":
            cmd_check(cur, conn)
        elif args.cmd == "prepare":
            cmd_prepare(cur, conn, args)
        elif args.cmd == "publish":
            cmd_publish(cur, conn, args)
        elif args.cmd == "rollback":
            cmd_rollback(cur, conn, args)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
