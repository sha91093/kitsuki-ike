"""data/water_area/ 以下のCSVを集計して docs/data.json を生成する。

出力する data.json は池ごとに以下を持つ:

- `timeseries` : 降交軌道の全観測（従来どおり。地図・一覧画面が参照する）
- `orbit_data`: 軌道別・年別の観測（グラフ画面のタブ表示用）

  ```json
  "orbit_data": {
    "descending": { "2025": [ { "date": "2025-06-01", "area_m2": 14823.0 }, ... ] },
    "ascending":  { "2026": [ ... ] }
  }
  ```

  観測はあるが水面が検出されなかった日（0㎡ = 撮影範囲外の可能性が高い）は
  `orbit_data` からは除外する。

Usage:
    python aggregate_data.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from utils import DATA_DIR, DOCS_DIR, ORBITS, POND_LIST_CSV, setup_logging

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
    # orbit 列が無い / 空の古いCSVは降交軌道として扱う
    if "orbit" not in combined.columns:
        combined["orbit"] = "DESCENDING"
    combined["orbit"] = combined["orbit"].fillna("DESCENDING").astype(str).str.strip().str.upper()
    combined = combined.sort_values(["date", "orbit"])
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


def build_orbit_data(group: pd.DataFrame) -> dict:
    """1池分のレコードを {軌道キー: {年: [観測, ...]}} に整理する。

    水面面積が0の日（撮影範囲外とみなす）は除外し、
    観測が1件も無い軌道はキーごと省略する。
    """
    orbit_data = {}
    for orbit in ORBITS:
        rows = group[group["orbit"] == orbit].sort_values("date")
        by_year = {}
        for _, row in rows.iterrows():
            area = float(row["water_area_m2"])
            if area <= 0:
                continue
            year = row["date"][:4]
            by_year.setdefault(year, []).append({
                "date": row["date"],
                "area_m2": area,
            })
        if by_year:
            orbit_data[orbit.lower()] = {y: by_year[y] for y in sorted(by_year)}
    return orbit_data


def build_data_json(df: pd.DataFrame) -> dict:
    """pond_id ごとに時系列データを集計してJSONオブジェクトを構築する。"""
    meta = load_pond_meta()

    if df.empty:
        ponds = [
            {
                "id": pid,
                **m,
                "timeseries": [],
                "orbit_data": {},
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
        # timeseries は従来どおり降交軌道のみ（地図・一覧画面との互換のため）
        descending = group[group["orbit"] == "DESCENDING"]
        timeseries = [
            {"date": row["date"], "water_area_m2": row["water_area_m2"]}
            for _, row in descending.iterrows()
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
            "orbit_data": build_orbit_data(group),
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
    if not df.empty:
        for orbit, n in df["orbit"].value_counts().items():
            logger.info(f"  {orbit}: {n} 件")

    data = build_data_json(df)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"data.json 生成完了: {out_path} ({len(data['ponds'])} 池)")


if __name__ == "__main__":
    main()
