#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报考说明页优化：将 2026allmaterial 下的官方 PDF 提取文字，重新排版为
精美、易读的 HTML 文章（自包含样式），输出到 webapp/backend/static/guides/{id}.html。

- 文本型 PDF：用 PyMuPDF 抽取文字，按标题/段落/列表结构化为 HTML。
- 扫描型 PDF（无文本层）：用 PyMuPDF 渲染页面为图片，tesseract(chi_sim) OCR。
- 生成后由后端 GET /guides/{id}/html 直接返回；页面内含「下载原文 PDF」按钮。

用法：
  python3 etl/build_guide_html.py            # 全量生成
  python3 etl/build_guide_html.py --id zhaosheng-jianzhang   # 单篇调试
  python3 etl/build_guide_html.py --force    # 覆盖已存在文件
"""
import os
import re
import sys
import argparse
import html as _html

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "backend"))
from app.routers import guides as G  # 复用 _GROUPS / _PDF_ROOT

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "webapp", "backend", "static", "guides")

# 网页/页眉页脚噪声（辽宁考试院网页导出 PDF 常见）
CHROME_PATTERNS = [
    "组织机构", "政务公开", "网报中心", "查询中心", "成绩证明", "招考杂志",
    "站内搜索", "首页", "正文", "时间：", "普通高考", "考生须知", "招考指南",
    "辽宁省教育招生考试", "辽宁招生考试之窗", "返回顶部", "打印", "关闭",
]

CN_NUM = "一二三四五六七八九十"
HEADING_RE = re.compile(r"^\s*([一二三四五六七八九十]+)、")
PART_RE = re.compile(r"^第[一二三四五六七八九十]+部分")
CASE_RE = re.compile(r"^案例[一二三四五六七八九十]+")
SUBHEAD_RE = re.compile(r"^(考生情况|退档原因|志愿填报|原因分析|提示|建议|点评|教训)[：:】]")
BULLET_RE = re.compile(r"^\s*[-·•—]\s+")
DATE_RE = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日")
NUM_LIST_RE = re.compile(r"^\s*[(（]?\d+[)）.、]")  # 1. (1) ① 等编号子项
CIRCLED_RE = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]")
SECTION_RE = re.compile(r"^\d+\s+[一-龥]{2,6}$")  # "1 北京" 省市分节标题


def is_chrome(line):
    s = line.strip()
    if not s:
        return True
    # 含多个 "/ " 的网站面包屑行
    if s.count("/") >= 3:
        return True
    for p in CHROME_PATTERNS:
        if p in s:
            return True
    return False


def has_text_layer(pdf_path):
    """判断 PDF 是否有可抽取文本层（非扫描件）。"""
    import fitz
    doc = fitz.open(pdf_path)
    ok = any(doc[p].get_text("text").strip() for p in range(doc.page_count))
    doc.close()
    return ok


def extract_text(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    pages = [doc[p].get_text("text") for p in range(doc.page_count)]
    doc.close()
    return "\n".join(pages)


def split_blocks(text, title=""):
    """把原始文本切成结构化块：('h2'|'h3'|'p'|'li', content)。"""
    lines = [ln.rstrip() for ln in text.splitlines()]
    blocks = []
    buf = []
    title_norm = re.sub(r"\s+", "", title or "")

    def flush_p():
        nonlocal buf
        if buf:
            s = " ".join(buf).strip()
            if s:
                blocks.append(("p", s))
            buf = []

    for raw in lines:
        line = raw.strip()
        if not line or is_chrome(line):
            continue
        # 网页导出 PDF 残留：日期行、与标题重复的首行
        if DATE_RE.match(line):
            continue
        if title_norm and re.sub(r"\s+", "", line) == title_norm:
            continue
        # 标题识别
        if HEADING_RE.match(line):
            flush_p(); blocks.append(("h2", re.sub(r"^\s*", "", line))); continue
        if PART_RE.match(line):
            flush_p(); blocks.append(("h2", line)); continue
        if CASE_RE.match(line):
            flush_p(); blocks.append(("h2", line)); continue
        if SUBHEAD_RE.match(line):
            flush_p(); blocks.append(("h3", line)); continue
        if SECTION_RE.match(line):
            flush_p(); blocks.append(("h3", line)); continue
        if BULLET_RE.match(line):
            flush_p(); blocks.append(("li", BULLET_RE.sub("", line))); continue
        if CIRCLED_RE.match(line) or NUM_LIST_RE.match(line):
            flush_p(); blocks.append(("li", CIRCLED_RE.sub("", NUM_LIST_RE.sub("", line)).strip())); continue
        # 普通正文行
        if blocks and blocks[-1][0] == "li":
            # PDF 换行导致的列表项续行：并入上一 li
            blocks[-1] = (blocks[-1][0], blocks[-1][1] + " " + line)
            continue
        buf.append(line)
    flush_p()
    return blocks


def render_blocks(blocks):
    out = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for kind, content in blocks:
        esc = _html.escape(content)
        if kind == "h2":
            close_ul(); out.append(f"<h2>{esc}</h2>")
        elif kind == "h3":
            close_ul(); out.append(f"<h3>{esc}</h3>")
        elif kind == "li":
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{esc}</li>")
        else:  # p
            close_ul(); out.append(f"<p>{esc}</p>")
    close_ul()
    return "\n".join(out)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --accent:#2456c7; --ink:#1f2329; --muted:#6b7280; --line:#e8ebf0; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
         color:var(--ink); background:#f5f6f8; line-height:1.9; -webkit-font-smoothing:antialiased; }}
  .topbar {{ position:sticky; top:0; z-index:10; background:rgba(255,255,255,.92); backdrop-filter:blur(8px);
            border-bottom:1px solid var(--line); padding:12px 20px; display:flex; align-items:center; gap:12px; }}
  .topbar .src {{ font-size:13px; color:var(--muted); }}
  .topbar .spacer {{ flex:1; }}
  .btn {{ display:inline-flex; align-items:center; gap:6px; border:1px solid var(--accent); color:var(--accent);
         background:#fff; padding:7px 14px; border-radius:8px; font-size:14px; text-decoration:none; cursor:pointer; }}
  .btn:hover {{ background:var(--accent); color:#fff; }}
  .btn--solid {{ background:var(--accent); color:#fff; }}
  .wrap {{ max-width:780px; margin:0 auto; padding:32px 20px 80px; }}
  .doc-head {{ border-bottom:2px solid var(--accent); padding-bottom:18px; margin-bottom:24px; }}
  .doc-head h1 {{ font-size:26px; margin:0 0 10px; line-height:1.4; }}
  .doc-meta {{ font-size:13px; color:var(--muted); }}
  .doc-meta .tag {{ display:inline-block; background:#eef3ff; color:var(--accent); border-radius:999px;
                   padding:2px 10px; margin-right:8px; font-size:12px; }}
  .lead {{ background:#f0f5ff; border-left:4px solid var(--accent); padding:14px 18px; border-radius:8px;
          color:#364152; font-size:15px; margin:18px 0 28px; }}
  .lead b {{ color:var(--accent); }}
  .points {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
  .points span {{ font-size:13px; color:var(--muted); border:1px solid var(--line);
                 border-radius:999px; padding:3px 10px; }}
  h2 {{ font-size:20px; margin:34px 0 12px; padding-left:12px; border-left:4px solid var(--accent);
        line-height:1.5; }}
  h3 {{ font-size:16px; margin:22px 0 8px; color:#2b3445; }}
  p {{ margin:12px 0; font-size:15.5px; }}
  ul {{ margin:12px 0; padding-left:0; list-style:none; }}
  li {{ position:relative; padding:8px 14px 8px 30px; margin-bottom:8px; background:#fff;
        border:1px solid var(--line); border-radius:8px; font-size:15px; }}
  li::before {{ content:"•"; position:absolute; left:12px; top:8px; color:var(--accent); font-weight:700; }}
  .ocr-note {{ background:#fff7e6; border:1px solid #ffe1a8; color:#8a5a00; font-size:13px;
              padding:10px 14px; border-radius:8px; margin:16px 0; }}
  @media print {{ body{{background:#fff;}} .topbar{{display:none;}} .wrap{{max-width:none;}} }}
</style>
</head>
<body>
  <div class="topbar">
    <span class="src">辽宁志愿参谋 · 报考说明</span>
    <span class="spacer"></span>
    <a class="btn" href="{pdf_url}" target="_blank">⬇ 下载原文 PDF</a>
    <button class="btn btn--solid" onclick="window.print()">打印 / 存为 PDF</button>
  </div>
  <div class="wrap">
    <div class="doc-head">
      <h1>{title}</h1>
      <div class="doc-meta"><span class="tag">{tag}</span>官方文件 · 原文排版再加工</div>
      <div class="points">{points_html}</div>
    </div>
    {lead_html}
    {ocr_note}
    {body_html}
  </div>
</body>
</html>
"""


EMBED_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --accent:#2456c7; --ink:#1f2329; --muted:#6b7280; --line:#e8ebf0; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink); background:#f5f6f8; }}
  .topbar {{ position:sticky; top:0; z-index:10; background:rgba(255,255,255,.94); backdrop-filter:blur(8px);
            border-bottom:1px solid var(--line); padding:12px 20px; display:flex; align-items:center; gap:12px; }}
  .topbar .src {{ font-size:13px; color:var(--muted); }}
  .topbar .spacer {{ flex:1; }}
  .btn {{ display:inline-flex; align-items:center; gap:6px; border:1px solid var(--accent); color:var(--accent);
         background:#fff; padding:7px 14px; border-radius:8px; font-size:14px; text-decoration:none; cursor:pointer; }}
  .btn:hover {{ background:var(--accent); color:#fff; }}
  .btn--solid {{ background:var(--accent); color:#fff; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:24px 16px 40px; }}
  .doc-head {{ border-bottom:2px solid var(--accent); padding-bottom:16px; margin-bottom:18px; }}
  .doc-head h1 {{ font-size:24px; margin:0 0 8px; line-height:1.4; }}
  .doc-meta {{ font-size:13px; color:var(--muted); }}
  .doc-meta .tag {{ display:inline-block; background:#eef3ff; color:var(--accent); border-radius:999px; padding:2px 10px; margin-right:8px; }}
  .note {{ background:#fff7e6; border:1px solid #ffe1a8; color:#8a5a00; font-size:14px; padding:12px 16px; border-radius:8px; margin:0 0 16px; }}
  .frame {{ width:100%; height:calc(100vh - 230px); border:1px solid var(--line); border-radius:10px; background:#fff; }}
</style>
</head>
<body>
  <div class="topbar">
    <span class="src">辽宁志愿参谋 · 报考说明</span>
    <span class="spacer"></span>
    <a class="btn" href="{pdf_url}" target="_blank">⬇ 下载原文 PDF</a>
  </div>
  <div class="wrap">
    <div class="doc-head">
      <h1>{title}</h1>
      <div class="doc-meta"><span class="tag">{tag}</span>官方文件 · 扫描件原文呈现</div>
    </div>
    <div class="note">⚠ 本文为<b>扫描件</b>，系统暂无法稳定提取文字，以下为<b>原文影像</b>呈现；如需高清版请点击右上角「下载原文 PDF」。</div>
    <iframe class="frame" src="{pdf_url}#toolbar=1&view=FitH" title="{title}"></iframe>
  </div>
</body>
</html>
"""


def build_one(it):
    pdf_path = os.path.join(G._PDF_ROOT, it["filename"])
    if not os.path.exists(pdf_path):
        print(f"  [跳过] 文件缺失: {it['filename']}")
        return False
    pdf_url = f"/api/v1/guides/{it['id']}/pdf"
    points_html = "".join(f"<span>{_html.escape(p)}</span>" for p in it["points"])
    lead_html = f'<div class="lead"><b>导读：</b>{_html.escape(it["summary"])}</div>' if it.get("summary") else ""

    # 扫描件（无文本层）：直接嵌入原文 PDF，保证准确
    if not has_text_layer(pdf_path):
        html_doc = EMBED_TEMPLATE.format(
            title=_html.escape(it["title"]), tag=_html.escape(it["tag"]), pdf_url=pdf_url)
        out_path = os.path.join(OUT_DIR, it["id"] + ".html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        print(f"  [生成·嵌入PDF] {it['id']}.html (扫描件)")
        return True

    text = extract_text(pdf_path)
    blocks = split_blocks(text, title=it["title"])
    body_html = render_blocks(blocks)
    html_doc = HTML_TEMPLATE.format(
        title=_html.escape(it["title"]),
        tag=_html.escape(it["tag"]),
        points_html=points_html,
        lead_html=lead_html,
        ocr_note="",
        body_html=body_html,
        pdf_url=pdf_url,
    )
    out_path = os.path.join(OUT_DIR, it["id"] + ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"  [生成] {it['id']}.html  ({len(body_html)} 字节正文)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="仅生成指定 id")
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    for g in G._GROUPS:
        for it in g["items"]:
            if args.id and it["id"] != args.id:
                continue
            out_path = os.path.join(OUT_DIR, it["id"] + ".html")
            if os.path.exists(out_path) and not args.force and not args.id:
                # 全量模式：跳过已存在（除非 --force）
                continue
            if build_one(it):
                count += 1
    print(f"\n完成：共生成 {count} 篇 HTML 至 {OUT_DIR}")


if __name__ == "__main__":
    main()
