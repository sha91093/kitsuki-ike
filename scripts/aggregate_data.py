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


def load_pond_meta() -> dict:
    """池リストCSVからメタデータを {simple_id -> dict} で返す。"""
    if not POND_LIST_CSV.exists():
        return {}
    pond_df = pd.read_csv(POND_LIST_CSV, dtype={"simple_id": str})
    meta = {}
    for _, row in pond_df.iterrows():
        pid = str(row["simple_id"])
        meta[pid] = {
            "name": row.get("name", ""),
            "tiiki": row.get("tiiki", ""),
            "ooaza": row.get("ooaza", ""),
            "area_ha": float(row["area_ha"]) if pd.notna(row.get("area_ha")) else None,
            "lat": float(row["latitude"]) if "latitude" in row and pd.notna(row.get("latitude")) else None,
            "lng": float(row["longitude"]) if "longitude" in row and pd.notna(row.get("longitude")) else None,
        }
    return meta


def build_data_json(df: pd.DataFrame) -> dict:
    """pond_id ごとに時系列データを集計してJSONオブジェクトを構築する。"""
    meta = load_pond_meta()

    if df.empty:
        ponds = [
            {
                "id": pid,
                **m,
                "timeseries": [],
            }
            for pid, m in sorted(meta.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
        ]
        return {
            "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "ponds": ponds,
        }

    ponds = []
    for pond_id, group in df.groupby("pond_id", sort=False):
        group = group.sort_values("date")
        m = meta.get(str(pond_id), {})
        timeseries = [
            {"date": row["date"], "water_area_m2": row["water_area_m2"]}
            for _, row in group.iterrows()
        ]
        ponds.append({
            "id": str(pond_id),
            "name": m.get("name", group.iloc[0].get("pond_name", "")),
            "tiiki": m.get("tiiki", group.iloc[0].get("tiiki", "")),
            "ooaza": m.get("ooaza", group.iloc[0].get("ooaza", "")),
            "area_ha": m.get("area_ha"),
            "lat": m.get("lat"),
            "lng": m.get("lng"),
            "timeseries": timeseries,
        })

    ponds.sort(key=lambda p: int(p["id"]) if p["id"].isdigit() else p["id"])

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
