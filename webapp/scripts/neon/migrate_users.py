"""一次性把 SQLite 用户库（users.db）迁到 PostgreSQL 可写库。

用法（在 webapp/backend 下）：
    APP_DB_URL='postgresql://gaokao_app_rw:...@<host>/<db>?sslmode=require' \
        .venv/bin/python ../scripts/neon/migrate_users.py data/users.db [--dry-run]

- 保留原 id（JWT 里存的是 user id，id 不变则已登录用户的 token 继续有效，前提是 JWT_SECRET 也不变）。
- 目标表非空时拒绝执行，避免重复导入或覆盖线上新注册的用户。
- 导入后把 BIGSERIAL 序列推到 max(id)，否则下一个注册会撞主键。
- 不打印邮箱、密码哈希等内容，只打印行数。
- Agent 任务库（agent.db）不迁：任务只保留 24 小时，属于临时数据。
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
os.environ.setdefault("GAOKAO_DSN", "postgresql://unused@localhost/unused")  # 仅为满足 config import

from app import sqlstore, user_db  # noqa: E402

TABLES = {
    "users": ["id", "email", "username", "password_hash", "created_at", "last_login_at"],
    "user_data": ["user_id", "data", "updated_at"],
    "outcome_feedback": [
        "id", "user_id", "examinee_year", "category", "subject", "batch", "examinee_rank",
        "plan_total", "outcome", "admitted_order", "admitted_risk", "admitted_school",
        "admitted_major", "note", "created_at",
    ],
}
SEQUENCES = {"users": "id", "outcome_feedback": "id"}


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    if not sqlstore.IS_PG:
        sys.exit("需要设置 APP_DB_URL（目标 PostgreSQL）")

    src = sqlite3.connect(f"file:{args[0]}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = {t: [tuple(r[c] for c in cols) for r in src.execute(f"SELECT {', '.join(cols)} FROM {t} ORDER BY 1")]
            for t, cols in TABLES.items()}
    src.close()
    for t, data in rows.items():
        print(f"源 {t}: {len(data)} 行")

    user_db.init_db()
    with sqlstore.connect("") as conn:
        for t in TABLES:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            if n:
                raise SystemExit(f"目标表 {t} 已有 {n} 行，拒绝导入（如确需重导，请先人工清空）")
        for t, cols in TABLES.items():
            marks = ", ".join("?" for _ in cols)
            for row in rows[t]:
                conn.execute(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({marks})", row)
        for t, col in SEQUENCES.items():
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{t}', '{col}'), "
                f"COALESCE((SELECT MAX({col}) FROM {t}), 0) + 1, false)"
            )
        for t in TABLES:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            assert n == len(rows[t]), (t, n, len(rows[t]))
            print(f"目标 {t}: {n} 行")
        if dry_run:
            raise _Rollback
    print("导入完成")


class _Rollback(Exception):
    pass


if __name__ == "__main__":
    try:
        main()
    except _Rollback:
        print("--dry-run：已回滚，目标库未改动")
