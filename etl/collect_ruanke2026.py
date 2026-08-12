#!/usr/bin/env python3
"""采集软科中国大学专业排名 2026（bcmr）→ etl/data/ruanke2026.csv

数据源（第三方·仅供参考）：https://www.shanghairanking.cn/rankings/bcmr/2026
内部 API（由 JS bundle 挖掘得到）：
  GET /api/pub/v1/bcmr/rank?year=2026&majorCode=<code>  每专业排名全量
  GET /api/pub/v1/bcmr/major?year=2026                  专业目录索引（含 univPublished）

范围限定：仅采集库内 major_catalog（表 major_catalog，列 code/name）中的专业。
原始 JSON 存档于 major/ruanke2026/api/（不入 git），支持断点续采（已有非空文件跳过）。
限速：每请求 sleep ≥1s。

输出列：school_name, major_name, major_code, rank, tier, data_year=2026
  tier 取 API grade 字段（A+/A/B+/B 等评级）。
"""
import csv
import json
import time
from pathlib import Path

import psycopg2
import requests

from config import DSN

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "major" / "ruanke2026" / "api"
OUT = ROOT / "etl" / "data" / "ruanke2026.csv"
YEAR = "2026"
BASE = "https://www.shanghairanking.cn/api/pub/v1/bcmr"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Referer": f"https://www.shanghairanking.cn/rankings/bcmr/{YEAR}",
    "Accept": "application/json, text/plain, */*",
}
SLEEP = 1.0
MAX_RETRY = 3


def fetch(url: str, params: dict, path: Path) -> dict:
    """GET 并存档 JSON；断点续采：已有非空且可解析文件直接复用。"""
    if path.exists() and path.stat().st_size > 0:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"http {r.status_code}")
            body = r.json()
            if body.get("code") != 200:
                raise RuntimeError(f"api code={body.get('code')} msg={body.get('msg')}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
            return body
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = SLEEP * attempt * 2
            print(f"  retry {attempt}/{MAX_RETRY} {params} -> {e}; sleep {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"fetch failed {params}: {last_err}")


def load_catalog() -> dict:
    """major_catalog code->name（库内专业限定集合）。"""
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("select code, name from major_catalog order by code;")
            rows = cur.fetchall()
    finally:
        conn.close()
    return {code: name for code, name in rows}


def main():
    API_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    print(f"major_catalog: {len(catalog)} majors")

    # 先取软科专业索引（存档 major_index.json），用于交叉核对 code/名称
    idx = fetch(f"{BASE}/major", {"year": YEAR}, API_DIR / "major_index.json")
    rk_majors = {}  # code -> (name, univPublished)

    def walk(nodes):
        for n in nodes or []:
            if n.get("children"):
                walk(n["children"])
            elif len(n.get("code", "")) >= 6:
                rk_majors[n["code"]] = (n.get("name", ""), n.get("univPublished", 0))

    walk(idx["data"])
    print(f"ruanke index leaf majors: {len(rk_majors)}")

    # 仅库内专业
    targets = [(code, name) for code, name in sorted(catalog.items())]
    in_index = [(c, n) for c, n in targets if c in rk_majors]
    not_in_index = [(c, n) for c, n in targets if c not in rk_majors]
    print(f"catalog majors in ruanke index: {len(in_index)}; not in index: {len(not_in_index)}")

    rows = []
    ok = empty = failed = 0
    fails = []
    for i, (code, name) in enumerate(in_index, 1):
        path = API_DIR / f"rank_{code}.json"
        try:
            body = fetch(f"{BASE}/rank", {"year": YEAR, "majorCode": code}, path)
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            fails.append((code, name, str(e)))
            print(f"[{i}/{len(in_index)}] {code} {name}: FAIL {e}")
            continue
        listings = (body.get("data") or {}).get("rankings") or []
        if not listings:
            empty += 1
        for it in listings:
            rows.append({
                "school_name": it.get("univNameCn", ""),
                "major_name": name,
                "major_code": code,
                "rank": it.get("ranking", ""),
                "tier": it.get("grade", ""),
                "data_year": YEAR,
            })
        if i % 50 == 0 or i == len(in_index):
            print(f"[{i}/{len(in_index)}] rows={len(rows)} ok={ok} empty={empty} failed={failed}")
        time.sleep(SLEEP)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["school_name", "major_name", "major_code",
                                          "rank", "tier", "data_year"])
        w.writeheader()
        w.writerows(rows)

    schools = {r["school_name"] for r in rows}
    majors_hit = {r["major_code"] for r in rows}
    print(f"rows={len(rows)} schools={len(schools)} majors_with_rank={len(majors_hit)}")
    print(f"fetched_ok={ok} empty={empty} failed={failed} not_in_index={len(not_in_index)}")
    if not_in_index:
        print("not_in_index sample:", not_in_index[:10])
    if fails:
        print("fails sample:", fails[:10])
        (API_DIR / "_fetch_failures.json").write_text(
            json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
