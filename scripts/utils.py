"""共通ユーティリティ"""
import os
import logging
from pathlib import Path
from datetime import datetime


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)


def initialize_gee():
    """GEE認証。サービスアカウントキーが環境変数で指定されている場合はそれを使用。"""
    import ee

    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path and os.path.exists(key_path):
        credentials = ee.ServiceAccountCredentials(None, key_file=key_path)
        ee.Initialize(credentials)
    else:
        ee.Initialize()


def get_csv_path(date_str: str, base_dir: str = None) -> Path:
    """撮影日文字列 (YYYY-MM-DD) からCSVファイルパスを生成。"""
    if base_dir is None:
        base_dir = Path(__file__).parent.parent / "data" / "water_area"
    else:
        base_dir = Path(base_dir)

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return base_dir / dt.strftime("%Y") / dt.strftime("%m") / f"{dt.strftime('%Y%m%d')}.csv"


REPO_ROOT = Path(__file__).parent.parent
POND_LIST_CSV = REPO_ROOT / "杵築池リスト名前入り.csv"
DATA_DIR = REPO_ROOT / "data" / "water_area"
DOCS_DIR = REPO_ROOT / "docs"
GEE_ASSET = "projects/kitsuki-kato/assets/kitsuki_ike2026"
SAR_THRESHOLD_DB = -16
