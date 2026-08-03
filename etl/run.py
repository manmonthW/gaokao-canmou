import os, argparse, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import readers
from meta import infer_meta, title_blob
from transform import parse_sheet, parse_pdf_text
import load
from config import BASE_DIR


def process(path, dry=False, conn=None):
    filename = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    print("\n" + "=" * 70)
    print("FILE:", filename)

    if ext in (".xlsx", ".xls"):
        try:
            sheets = readers.read_spreadsheet(path)
        except readers.EncryptedFile as e:
            print("  [ENCRYPTED] 跳过:", e)
            if not dry:
                load.load_file(conn, filename, ext.lstrip("."),
                               {}, [], status="encrypted",
                               note="加密文件，需密码后补录")
            return
        all_recs = []
        sheets_meta = []
        for sheet, rows in sheets:
            blob = title_blob(rows, sheet)
            meta = infer_meta(blob, filename)
            meta["sheet"] = sheet
            recs, ok = parse_sheet(rows)
            for r in recs:
                r.update({k: meta.get(k) for k in
                          ("year", "category", "batch",
                           "is_collection", "subject")})
            all_recs += recs
            sheets_meta.append((sheet, meta, len(recs)))
            print(f"  SHEET {sheet}: meta={meta} rows={len(recs)}")
        if dry:
            if all_recs:
                print("  SAMPLE:", all_recs[0])
        else:
            load.load_file(conn, filename, ext.lstrip("."),
                           sheets_meta[0][1] if sheets_meta else {},
                           all_recs,
                           sheet=";".join(s for s, _, _ in sheets_meta))
        print(f"  >> 总记录数: {len(all_recs)}")

    elif ext == ".pdf":
        pages = readers.read_pdf(path)
        blob = " ".join(t for _, t in pages[:1])
        meta = infer_meta(blob, filename)
        recs = parse_pdf_text(pages, meta)
        for r in recs:
            r.update({k: meta.get(k) for k in
                      ("year", "category", "batch",
                       "is_collection", "subject")})
        print(f"  PDF pages={len(pages)} records={len(recs)} meta={meta}")
        if dry:
            if recs:
                print("  SAMPLE:", recs[0])
        else:
            load.load_file(conn, filename, "pdf", meta, recs, raw_pages=pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="只解析打印，不写库")
    ap.add_argument("--no-pdf", action="store_true",
                    help="跳过 PDF（OCR 较慢），仅处理表格")
    args = ap.parse_args()

    conn = None if args.dry_run else load.get_conn()
    n = 0
    errs = 0
    for path in readers.iter_files():
        if args.no_pdf and os.path.splitext(path)[1].lower() == ".pdf":
            continue
        try:
            process(path, dry=args.dry_run, conn=conn)
        except Exception as e:
            errs += 1
            print(f"  [ERROR] {os.path.basename(path)}: {e}")
        n += 1
    print(f"\n处理文件总数: {n}  失败: {errs}")


if __name__ == "__main__":
    main()
