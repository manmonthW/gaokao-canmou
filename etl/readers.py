import os, re, glob, subprocess, tempfile
import openpyxl
import xlrd
from config import BASE_DIR, DATA_DIRS, OCR_LANGS, OCR_DPI


class EncryptedFile(Exception):
    pass


def iter_files():
    for d in DATA_DIRS:
        root = os.path.join(BASE_DIR, d)
        for p in sorted(glob.glob(os.path.join(root, "*"))):
            if p.endswith(":Zone.Identifier"):
                continue
            base = os.path.basename(p)
            # 跳过 Excel 临时锁文件（~$ 前缀）等非数据文件
            if base.startswith("~$"):
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext in (".xlsx", ".xls", ".pdf"):
                yield p


def read_spreadsheet(path):
    """返回 [(sheet_name, rows)]；加密/损坏文件抛 EncryptedFile。"""
    ext = os.path.splitext(path)[1].lower()
    out = []
    if ext == ".xlsx":
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        except Exception as e:  # CDFV2 Encrypted -> BadZipFile 等
            raise EncryptedFile(f"{path}: {e}")
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            out.append((ws.title, rows))
        wb.close()
    elif ext == ".xls":
        wb = xlrd.open_workbook(path)
        for sh in wb.sheets():
            rows = [[sh.cell(r, c).value for c in range(sh.ncols)]
                    for r in range(sh.nrows)]
            out.append((sh.name, rows))
    return out


def _ocr_png(png):
    r = subprocess.run(["tesseract", png, "stdout", "-l", OCR_LANGS],
                       capture_output=True, text=True)
    return r.stdout


def read_pdf(path):
    """渲染每页为 PNG 并 OCR，返回 [(page_no, text)]。"""
    pages = []
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "p")
        subprocess.run(["pdftoppm", "-r", str(OCR_DPI), "-png", path, base],
                       check=True)
        for png in sorted(glob.glob(base + "-*.png")):
            num = int(re.search(r"-(\d+)\.png$", png).group(1))
            pages.append((num, _ocr_png(png)))
    return pages
