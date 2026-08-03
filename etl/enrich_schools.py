#!/usr/bin/env python3
"""
院校信息补全脚本：为 school_profiles 补充 official website 与 intro（学校简介）。

数据源：
- website：DuckDuckGo 搜索，仅采信“结果标题包含校名”的 *.edu.cn 官方域名，归一为官网首页；
           首轮无命中再带 官方网站 / site:.edu.cn 补搜；仍无则留空并写入 enrich_review.jsonl 待人工。
- intro：抓取“百度百科”词条页 <meta name=description>，内容准确、简洁；抓取失败则回退到
         库内结构化字段拼装的模板简介。整体控制在 ~140 字以内。

用法：
  .venv/bin/python enrich_schools.py                 # 续跑：跳过已 enriched 的
  .venv/bin/python enrich_schools.py --limit 12      # 试跑前 12 所
  .venv/bin/python enrich_schools.py --force         # 全部重跑（含已 enriched）
  .venv/bin/python enrich_schools.py --limit 20 --dry-run

进度/结果写 enrich_log.jsonl；缺失官网写 enrich_review.jsonl。
"""
import os
import re
import ssl
import time
import json
import argparse
import urllib.request
import urllib.parse
import psycopg2
from urllib.parse import urlparse
from ddgs import DDGS

WRITER_DSN = os.environ.get(
    "WRITER_DSN",
    "postgresql://gaokao_writer:gk_wr_7b21de@localhost:5432/gaokao",
)
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enrich_log.jsonl")
REVIEW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enrich_review.jsonl")

BLOCKED_NET = (
    "baidu.com", "baike.baidu.com", "tieba.baidu.com", "wikipedia.org",
    "zhihu.com", "weibo.com", "douban.com", "qq.com", "sina.com.cn",
    "sohu.com", "163.com", "youtube.com", "facebook.com", "bilibili.com",
    "gov.cn", "edu.cn.cn", "wenku.baidu.com",
)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def log(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def is_official(href: str) -> bool:
    if not href:
        return False
    try:
        net = urlparse(href).netloc.lower()
    except Exception:
        return False
    if any(b in net for b in BLOCKED_NET):
        return False
    return "edu.cn" in net


def to_homepage(href: str) -> str:
    p = urlparse(href)
    return f"{p.scheme}://{p.netloc}/"


def http_get(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN"})
        return urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def extract_baike_meta(html: str) -> str:
    m = re.search(r'<meta name="description" content="([^"]+)"', html)
    if not m:
        return ""
    s = m.group(1).strip()
    # 去掉可能的结尾省略/分类标签噪音
    return s


def trim_intro(s: str, max_len=140) -> str:
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    # 尽量在句号处断句
    idx = cut.rfind("。")
    if idx and idx > max_len * 0.5:
        return s[:idx + 1]
    return cut + "…"


def baike_intro(name: str) -> str:
    # 直连词条页；失败则回退模板，不额外搜索（避免拖慢全量）。
    url = "https://baike.baidu.com/item/" + urllib.parse.quote(name)
    meta = extract_baike_meta(http_get(url))
    if meta:
        return trim_intro(meta)
    return ""


def select_official(results, name):
    """仅当结果标题包含校名时才采信（高置信），返回官网首页或 None。"""
    matched = []
    for r in results:
        href = r.get("href", "")
        if not is_official(href):
            continue
        title = r.get("title", "") or ""
        if name in title:
            matched.append(href)
    if not matched:
        return None
    matched.sort(key=lambda h: (len(urlparse(h).netloc.split(".")), len(urlparse(h).path or "/")))
    return to_homepage(matched[0])


def build_template_intro(meta) -> str:
    """抓取失败时回退：仅用库内结构化字段拼装。"""
    name = meta["name"] or ""
    loc_parts = []
    if meta["province"]:
        loc_parts.append(meta["province"])
    if meta["city"] and meta["city"] != meta["province"]:
        loc_parts.append(meta["city"])
    loc = "".join(loc_parts)
    labels = []
    if meta["affiliation"]:
        labels.append("隶属" + meta["affiliation"])
    if meta["nature"]:
        labels.append(meta["nature"])
    if meta["type"]:
        labels.append(meta["type"])
    if meta["level"]:
        labels.append(meta["level"])
    tpl = f"{name}是{loc}的{'、'.join(labels)}院校" if labels else f"{name}是一所院校"
    honor = []
    if meta["is_985"]:
        honor.append("985工程")
    if meta["is_211"]:
        honor.append("211工程")
    if meta["is_dfc"]:
        honor.append("双一流")
    if honor:
        tpl += "，是国家" + "、".join(honor) + "建设高校"
    tpl += "。"
    return tpl


def search(q, retries=3):
    for attempt in range(retries):
        try:
            results = DDGS().text(q, max_results=10)
            if results:
                return results
        except Exception as e:
            wait = 2 + attempt * 3
            print(f"  [warn] search '{q}' failed: {e}; retry in {wait}s", flush=True)
            time.sleep(wait)
    return []


def fetch_targets(conn, force, limit):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.code, s.name,
               p.province, p.city, p.affiliation, p.level, p.nature, p.type,
               p.is_985, p.is_211, p.is_dfc, p.enriched_at
        FROM schools s
        LEFT JOIN school_profiles p ON p.code = s.code
        ORDER BY s.code
        """
    )
    rows = cur.fetchall()
    targets = []
    for r in rows:
        (code, name, prov, city, affil, level, nature, typ,
         is985, is211, isdfc, enriched) = r
        if not force and enriched is not None:
            continue
        targets.append({
            "code": code, "name": name, "province": prov, "city": city,
            "affiliation": affil, "level": level, "nature": nature, "type": typ,
            "is_985": is985, "is_211": is211, "is_dfc": isdfc,
        })
    if limit:
        targets = targets[:limit]
    return targets


def upsert(conn, t, website, intro):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO school_profiles (code, name, website, intro, enriched_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (code) DO UPDATE
            SET website = EXCLUDED.website,
                intro   = EXCLUDED.intro,
                enriched_at = now()
        """,
        (t["code"], t["name"], website, intro),
    )
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="重跑已 enriched 的")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0, help="跳过前 N 个目标（用于并行分片）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写库")
    ap.add_argument("--sleep", type=float, default=0.6, help="每次搜索间隔(秒)")
    args = ap.parse_args()

    conn = psycopg2.connect(WRITER_DSN)
    targets = fetch_targets(conn, args.force, 0)
    if args.offset:
        targets = targets[args.offset:]
    if args.limit:
        targets = targets[:args.limit]
    print(f"待处理: {len(targets)} 所", flush=True)
    if args.dry_run:
        for t in targets[:20]:
            print(" -", t["code"], t["name"])
        conn.close()
        return

    done = 0
    failed = 0
    for i, t in enumerate(targets, 1):
        name = t["name"] or t["code"]
        print(f"[{i}/{len(targets)}] {t['code']} {name}", flush=True)
        results = search(f"{name} 官网")
        website = select_official(results, name)
        if website is None:
            website = select_official(search(f"{name} 官方网站"), name)
        if website is None:
            website = select_official(search(f'{name} 官网 site:.edu.cn'), name)
        intro = baike_intro(name) or build_template_intro(t)
        ok = bool(website or intro)
        if ok and not args.dry_run:
            try:
                upsert(conn, t, website, intro)
            except Exception as e:
                print(f"  [err] upsert failed: {e}", flush=True)
                ok = False
        log(LOG_PATH, {
            "code": t["code"], "name": name, "website": website,
            "intro": intro, "intro_src": "baike" if intro and intro != build_template_intro(t) else "template",
            "ok": ok,
        })
        if website is None:
            log(REVIEW_PATH, {"code": t["code"], "name": name, "reason": "no_confident_website"})
        if ok:
            done += 1
            tag = " [缺官网,待人工]" if website is None else ""
            print(f"  -> {website or '(无官网)'}{tag}", flush=True)
        else:
            failed += 1
            print(f"  -> 无官网且无简介，跳过标记（可后续重试）", flush=True)
        if args.sleep:
            time.sleep(args.sleep)

    print(f"\n完成: 成功 {done}，失败 {failed}，日志: {LOG_PATH}", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
