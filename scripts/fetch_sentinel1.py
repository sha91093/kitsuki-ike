"""GEEからSentinel-1データを取得し、池ごとの水面面積を算出・CSVに保存する。

Usage:
    python fetch_sentinel1.py                          # 直近14日・両軌道
    python fetch_sentinel1.py --date 2026-03-01        # 指定日付
    python fetch_sentinel1.py --days-back 60           # 直近60日間の全撮影日を処理
    python fetch_sentinel1.py --orbits ascending       # 昇交軌道のみ取得
    python fetch_sentinel1.py --orbits ascending --pond-ids 3,7   # 試験導入（1〜2池のみ）

CSVは撮影日ごとに1ファイルで、降交・昇交の両方の行を `orbit` 列で書き分けて保持する。
既存CSVがある場合は (pond_id, orbit) をキーにマージするため、
後から昇交軌道だけを追加取得しても既存の降交データは失われない。
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import ee
import pandas as pd

from utils import (
    CSV_FIELDNAMES,
    DATA_DIR,
    GEE_ASSET,
    ORBITS,
    POND_LIST_CSV,
    get_csv_path,
    initialize_gee,
    normalize_orbit,
    orbit_sort_key,
    setup_logging,
)
from mosaic_and_analyze import get_available_dates, get_mosaic, calculate_water_areas

logger = setup_logging(__name__)


def load_pond_list() -> pd.DataFrame:
    if not POND_LIST_CSV.exists():
        raise FileNotFoundError(f"池リストCSVが見つかりません: {POND_LIST_CSV}")
    df = pd.read_csv(POND_LIST_CSV, dtype={"simple_id": str})
    for col in ("simple_id", "name", "tiiki", "ooaza", "area_ha"):
        if col not in df.columns:
            raise ValueError(f"池リストCSVに '{col}' カラムが必要です")
    return df


def read_existing_rows(csv_path: Path) -> dict:
    """既存CSVを {(pond_id, orbit): row} で読み込む。無ければ空辞書。"""
    if not csv_path.exists():
        return {}

    rows = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = (row.get("orbit") or "").strip()
            # orbit 列が無い / 空の古いCSVは降交軌道とみなす
            if not raw:
                orbit = "DESCENDING"
            else:
                try:
                    orbit = normalize_orbit(raw)
                except ValueError:
                    logger.warning(f"{csv_path}: 未知の軌道 '{raw}' をそのまま保持します")
                    orbit = raw
            row["orbit"] = orbit
            rows[(str(row["pond_id"]), orbit)] = row
    return rows


def write_rows(csv_path: Path, rows: dict):
    """{(pond_id, orbit): row} を軌道→池ID順に並べてCSVへ書き出す。"""
    ordered = sorted(
        rows.values(),
        key=lambda r: (
            orbit_sort_key(r.get("orbit", "DESCENDING")),
            int(r["pond_id"]) if str(r["pond_id"]).isdigit() else 0,
            str(r["pond_id"]),
        ),
    )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in ordered:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDNAMES})


def build_rows(date_str: str, orbit: str, areas: dict, pond_df: pd.DataFrame) -> dict:
    """算出済みの面積辞書から {(pond_id, orbit): row} を組み立てる。"""
    rows = {}
    for _, row in pond_df.iterrows():
        pond_id = str(row["simple_id"])
        rows[(pond_id, orbit)] = {
            "date": date_str,
            "pond_id": pond_id,
            "pond_name": row["name"],
            "tiiki": row["tiiki"],
            "ooaza": row["ooaza"],
            "area_ha": row["area_ha"],
            "water_area_m2": round(areas.get(pond_id, 0.0), 1),
            "satellite": "Sentinel-1",
            "orbit": orbit,
        }
    return rows


def process_date(date_str: str, ponds_fc: ee.FeatureCollection, pond_df: pd.DataFrame,
                 orbits: list) -> bool:
    """1日分・指定軌道のデータを処理して既存CSVにマージ保存する。

    Returns:
        CSVを更新した場合 True
    """
    csv_path = get_csv_path(date_str)
    existing = read_existing_rows(csv_path)
    target_ids = [str(pid) for pid in pond_df["simple_id"]]

    updated = False
    for orbit in orbits:
        if all((pid, orbit) in existing for pid in target_ids):
            logger.info(f"{date_str} [{orbit}]: 取得済みのためスキップします")
            continue

        logger.info(f"{date_str} [{orbit}]: 処理開始")
        try:
            mosaic = get_mosaic(date_str, orbit)
            areas = calculate_water_areas(mosaic, ponds_fc)
        except ValueError as e:
            logger.warning(str(e))
            continue

        existing.update(build_rows(date_str, orbit, areas, pond_df))
        updated = True
        logger.info(f"{date_str} [{orbit}]: {len(target_ids)} 池のデータを取得しました")

    if updated:
        write_rows(csv_path, existing)
        logger.info(f"{date_str}: 計 {len(existing)} 行を保存しました → {csv_path}")

    return updated


def main():
    parser = argparse.ArgumentParser(description="Sentinel-1 水面面積取得スクリプト")
    parser.add_argument("--date", help="処理対象日 (YYYY-MM-DD)")
    parser.add_argument("--days-back", type=int, default=14, help="直近N日分を処理（--date未指定時）")
    parser.add_argument(
        "--orbits",
        default=",".join(ORBITS),
        help="取得対象の軌道をカンマ区切りで指定 (descending,ascending)",
    )
    parser.add_argument(
        "--pond-ids",
        help="対象池を simple_id のカンマ区切りで限定（試験導入用。未指定なら全池）",
    )
    args = parser.parse_args()

    orbits = [normalize_orbit(o) for o in args.orbits.split(",") if o.strip()]
    if not orbits:
        parser.error("--orbits に有効な軌道が指定されていません")
    logger.info(f"対象軌道: {orbits}")

    initialize_gee()
    pond_df = load_pond_list()

    if args.pond_ids:
        wanted = {p.strip() for p in args.pond_ids.split(",") if p.strip()}
        pond_df = pond_df[pond_df["simple_id"].isin(wanted)]
        if pond_df.empty:
            parser.error(f"--pond-ids に一致する池がありません: {sorted(wanted)}")
        logger.info(f"対象池を限定: {list(pond_df['simple_id'])}")

    ponds_fc = ee.FeatureCollection(GEE_ASSET)
    bounds = ponds_fc.geometry().bounds()
    ponds_fc = ponds_fc.filterBounds(bounds)

    if args.date:
        dates_by_orbit = {orbit: [args.date] for orbit in orbits}
    else:
        logger.info(f"直近 {args.days_back} 日間の撮影日を検索中...")
        dates_by_orbit = get_available_dates(days_back=args.days_back, orbits=orbits)

    # 同日に両軌道の撮影がある場合、CSVは1回だけ開いてまとめて更新する
    orbits_by_date = {}
    for orbit in orbits:
        for date_str in dates_by_orbit.get(orbit, []):
            orbits_by_date.setdefault(date_str, []).append(orbit)

    for date_str in sorted(orbits_by_date):
        process_date(date_str, ponds_fc, pond_df, orbits_by_date[date_str])

    logger.info("処理完了")


if __name__ == "__main__":
    main()
