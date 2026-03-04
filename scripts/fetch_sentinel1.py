"""GEEからSentinel-1データを取得し、池ごとの水面面積を算出・CSVに保存する。

Usage:
    python fetch_sentinel1.py                    # 最新撮影日を自動検出
    python fetch_sentinel1.py --date 2026-03-01  # 指定日付
    python fetch_sentinel1.py --days-back 60     # 直近60日間の全日付を処理
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import ee
import pandas as pd

from utils import (
    DATA_DIR,
    GEE_ASSET,
    POND_LIST_CSV,
    get_csv_path,
    initialize_gee,
    setup_logging,
)
from mosaic_and_analyze import get_available_dates, get_mosaic, calculate_water_areas

logger = setup_logging(__name__)


def load_pond_list() -> pd.DataFrame:
    if not POND_LIST_CSV.exists():
        raise FileNotFoundError(f"池リストCSVが見つかりません: {POND_LIST_CSV}")
    df = pd.read_csv(POND_LIST_CSV, dtype={"id": str})
    for col in ("id", "name", "region"):
        if col not in df.columns:
            raise ValueError(f"池リストCSVに '{col}' カラムが必要です")
    return df


def process_date(date_str: str, ponds_fc: ee.FeatureCollection, pond_df: pd.DataFrame):
    """1日分のデータを処理してCSVに保存する。"""
    csv_path = get_csv_path(date_str)
    if csv_path.exists():
        logger.info(f"{date_str}: CSVが既に存在します。スキップします ({csv_path})")
        return

    logger.info(f"{date_str}: 処理開始")
    try:
        mosaic = get_mosaic(date_str)
        areas = calculate_water_areas(mosaic, ponds_fc)
    except ValueError as e:
        logger.warning(str(e))
        return

    rows = []
    for _, row in pond_df.iterrows():
        pond_id = str(row["id"])
        water_area = areas.get(pond_id, 0.0)
        rows.append({
            "date": date_str,
            "pond_id": pond_id,
            "pond_name": row["name"],
            "region": row["region"],
            "water_area_m2": round(water_area, 1),
            "satellite": "Sentinel-1",
            "orbit": "DESCENDING",
        })

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "pond_id", "pond_name", "region", "water_area_m2", "satellite", "orbit"],
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"{date_str}: {len(rows)} 池のデータを保存しました → {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Sentinel-1 水面面積取得スクリプト")
    parser.add_argument("--date", help="処理対象日 (YYYY-MM-DD)")
    parser.add_argument("--days-back", type=int, default=14, help="直近N日分を処理（--date未指定時）")
    args = parser.parse_args()

    initialize_gee()
    pond_df = load_pond_list()

    ponds_fc = ee.FeatureCollection(GEE_ASSET)
    bounds = ponds_fc.geometry().bounds()
    ponds_fc = ponds_fc.filterBounds(bounds)

    if args.date:
        dates = [args.date]
    else:
        logger.info(f"直近 {args.days_back} 日間の撮影日を検索中...")
        dates = get_available_dates(days_back=args.days_back)
        logger.info(f"対象日: {dates}")

    for date_str in dates:
        process_date(date_str, ponds_fc, pond_df)

    logger.info("処理完了")


if __name__ == "__main__":
    main()
