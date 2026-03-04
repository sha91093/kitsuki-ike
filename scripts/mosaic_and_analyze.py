"""Sentinel-1 モザイク処理・SAR閾値分析"""
import ee
from utils import GEE_ASSET, SAR_THRESHOLD_DB, setup_logging

logger = setup_logging(__name__)


def get_mosaic(date_str: str) -> ee.Image:
    """指定日のSentinel-1降交軌道データをモザイク合成して返す。"""
    date_start = ee.Date(date_str)
    date_end = date_start.advance(1, "day")

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filterDate(date_start, date_end)
    )

    count = collection.size().getInfo()
    logger.info(f"{date_str}: {count} 枚のSentinel-1画像が見つかりました")
    if count == 0:
        raise ValueError(f"{date_str} に対象のSentinel-1降交軌道データが見つかりません")

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


def get_available_dates(days_back: int = 30) -> list:
    """直近 days_back 日間に存在するSentinel-1降交軌道の撮影日一覧を返す。"""
    from datetime import datetime, timedelta

    end = datetime.utcnow()
    start = end - timedelta(days=days_back)

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filterDate(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    )

    dates = collection.aggregate_array("system:time_start").getInfo()
    unique_dates = sorted(
        set(
            datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
            for ms in dates
        )
    )
    return unique_dates
