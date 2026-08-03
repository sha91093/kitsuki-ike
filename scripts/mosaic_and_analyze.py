"""Sentinel-1 モザイク処理・SAR閾値分析"""
import ee
from utils import GEE_ASSET, ORBITS, SAR_THRESHOLD_DB, normalize_orbit, setup_logging

logger = setup_logging(__name__)


def _base_collection(orbit: str) -> ee.ImageCollection:
    """指定軌道のSentinel-1 IW/VVコレクション（池ポリゴンの範囲に限定）を返す。"""
    orbit = normalize_orbit(orbit)
    bounds = ee.FeatureCollection(GEE_ASSET).geometry().bounds()
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filter(ee.Filter.eq("orbitProperties_pass", orbit))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filterBounds(bounds)
    )


def get_mosaic(date_str: str, orbit: str = "DESCENDING") -> ee.Image:
    """指定日・指定軌道のSentinel-1データをモザイク合成して返す。"""
    orbit = normalize_orbit(orbit)
    date_start = ee.Date(date_str)
    date_end = date_start.advance(1, "day")

    collection = _base_collection(orbit).filterDate(date_start, date_end)

    count = collection.size().getInfo()
    logger.info(f"{date_str} [{orbit}]: {count} 枚のSentinel-1画像が見つかりました")
    if count == 0:
        raise ValueError(f"{date_str} に対象のSentinel-1 {orbit} 軌道データが見つかりません")

    return collection.select("VV").mosaic()


def calculate_water_areas(mosaic: ee.Image, ponds: ee.FeatureCollection) -> dict:
    """各池ポリゴンの水面面積（㎡）を算出して辞書で返す。

    Returns:
        {pond_id: water_area_m2} の辞書
    """
    water_mask = mosaic.lt(SAR_THRESHOLD_DB)
    water_area_image = water_mask.multiply(ee.Image.pixelArea())

    def compute_area(feature):
        area = water_area_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=feature.geometry(),
            scale=10,
            maxPixels=1e9,
        ).get("VV")
        return feature.set("water_area_m2", area)

    results = ponds.map(compute_area)
    features = results.getInfo()["features"]

    areas = {}
    for f in features:
        pond_id = str(f["properties"].get("simple_id", ""))
        water_area = f["properties"].get("water_area_m2")
        if water_area is None:
            water_area = 0.0
        areas[pond_id] = float(water_area)

    return areas


def get_available_dates(days_back: int = 30, orbits=None) -> dict:
    """直近 days_back 日間の撮影日一覧を軌道別に返す。

    Returns:
        {"DESCENDING": ["YYYY-MM-DD", ...], "ASCENDING": [...]} の辞書
    """
    from datetime import datetime, timedelta

    if orbits is None:
        orbits = ORBITS
    orbits = [normalize_orbit(o) for o in orbits]

    end = datetime.utcnow()
    start = end - timedelta(days=days_back)

    result = {}
    for orbit in orbits:
        collection = _base_collection(orbit).filterDate(
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        )
        dates = collection.aggregate_array("system:time_start").getInfo()
        result[orbit] = sorted(
            set(
                datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
                for ms in dates
            )
        )
        logger.info(f"[{orbit}] 撮影日 {len(result[orbit])} 件: {result[orbit]}")

    return result
