"""data/water_area/ 以下のCSVを集計して docs/data.json を生成する。

Usage:
    python aggregate_data.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from utils import DATA_DIR, DOCS_DIR, POND_LIST_CSV, setup_logging

logger = setup_logging(__name__)


def load_all_csvs() -> pd.DataFrame:
    """data/water_area/ 以下の全CSVを読み込んで結合する。"""
    csv_files = sorted(DATA_DIR.glob("**/*.csv"))
    if not csv_files:
        logger.warning(f"CSVファイルが見つかりません: {DATA_DIR}")
        return pd.DataFrame()

    dfs = []
    for path in csv_files:
        try:
            df = pd.read_csv(path, dtype={"pond_id": str})
            dfs.append(df)
        except Exception as e:
            logger.warning(f"CSV読み込みエラー ({path}): {e}")

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")
    combined = combined.sort_values("date")
    return combined


def build_data_json(df: pd.DataFrame) -> dict:
    """pond_id ごとに時系列データを集計してJSONオブジェクトを構築する。"""
    if df.empty:
        pond_list = []
        if POND_LIST_CSV.exists():
            pond_df = pd.read_csv(POND_LIST_CSV, dtype={"id": str})
            for _, row in pond_df.iterrows():
                pond_list.append({
                    "id": str(row["id"]),
                    "name": row["name"],
                    "region": row["region"],
                    "timeseries": [],
                })
        return {
            "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "ponds": pond_list,
        }

    ponds = []
    for pond_id, group in df.groupby("pond_id", sort=False):
        group = group.sort_values("date")
        first = group.iloc[0]
        timeseries = [
            {"date": row["date"], "water_area_m2": row["water_area_m2"]}
            for _, row in group.iterrows()
        ]
        ponds.append({
            "id": pond_id,
            "name": first.get("pond_name", ""),
            "region": first.get("region", ""),
            "timeseries": timeseries,
        })

    ponds.sort(key=lambda p: p["id"])

    return {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "ponds": ponds,
    }


def main():
    logger.info("CSV集計開始")
    df = load_all_csvs()
    logger.info(f"読み込んだレコード数: {len(df)}")

    data = build_data_json(df)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"data.json 生成完了: {out_path} ({len(data['ponds'])} 池)")


if __name__ == "__main__":
    main()
