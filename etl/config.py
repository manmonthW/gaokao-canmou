import os

# 本机 PostgreSQL 16 连接串（建库时已创建用户/库 gaokao）
DSN = os.environ.get("GAOKAO_DSN",
                     "postgresql://gaokao:gaokao123@localhost:5432/gaokao")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIRS = ["2024", "2025", "2026", "2027"]
OCR_LANGS = "chi_sim+eng"
OCR_DPI = 200
