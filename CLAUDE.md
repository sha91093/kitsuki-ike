# 杵築市池水面面積モニタリングシステム

## プロジェクト概要

Google Earth Engine (GEE) のセンチネル1（SAR）データを用いて、杵築市内30か所の池の水面面積を自動算出し、水位変動を時系列で監視するシステム。

## 技術スタック

- **データソース**: Sentinel-1 SAR（降交軌道のみ）via Google Earth Engine
- **GEEアセット**: `projects/kitsuki-kato/assets/kitsuki_ike2026`（池ポリゴン30か所）
- **言語**: Python（GEE処理）、JavaScript/HTML（フロントエンド）
- **ライブラリ**: `earthengine-api`, `pandas`, `plotly`, `geopandas`, `leaflet.js`
- **自動化**: GitHub Actions（Sentinel-1撮影日ごとに自動更新）

## GEE 認証

### GitHub Actions 用

GEE サービスアカウントキー（JSON）を GitHub Secrets に登録が必要：

- Secret名: `GEE_SERVICE_ACCOUNT_KEY`
- 内容: GEEサービスアカウントのJSONキーファイル全体
- サービスアカウントには `projects/kitsuki-kato` へのアクセス権が必要

### ローカル開発用

```bash
earthengine authenticate
```

または環境変数 `GOOGLE_APPLICATION_CREDENTIALS` でサービスアカウントJSONを指定。

## ディレクトリ構成

```
kitsuki-ike/
├── CLAUDE.md
├── 杵築池リスト名前入り.csv          # 池ID・池名・地域名マスタ
├── data/
│   └── water_area/
│       └── YYYY/
│           └── MM/
│               └── YYYYMMDD.csv      # 撮影日ごとの水面面積データ
├── docs/
│   ├── index.html                    # 地図インターフェース（池選択→グラフ表示）
│   ├── data.json                     # フロントエンド用集計データ
│   └── assets/
│       ├── style.css
│       └── app.js
├── scripts/
│   ├── fetch_sentinel1.py            # GEEからデータ取得・水面面積算出
│   ├── mosaic_and_analyze.py         # モザイク処理・SAR閾値分析
│   ├── aggregate_data.py             # CSV集計・JSON生成
│   └── utils.py                      # 共通ユーティリティ
├── requirements.txt
└── .github/
    └── workflows/
        └── update_water_area.yml     # GitHub Actions定義
```

## 処理フロー

### 1. データ取得（`fetch_sentinel1.py`）

1. GEEに接続（サービスアカウント認証）
2. `COPERNICUS/S1_GRD` コレクションからデータ取得
   - 軌道方向: **降交（DESCENDING）のみ**
   - 偏波: VV
   - 対象範囲: 杵築市（池ポリゴンのバウンディングボックス）
3. 撮影範囲が2つに分かれるため **モザイク処理**で結合
4. 池ポリゴン（30か所）ごとに水面ピクセルを抽出・面積算出

### 2. モザイク処理（`mosaic_and_analyze.py`）

```python
# Sentinel-1は撮影パスが2つに分かれる → 同日データをモザイク合成
images = ee.ImageCollection('COPERNICUS/S1_GRD') \
    .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')) \
    .filter(ee.Filter.date(date_start, date_end)) \
    .mosaic()
```

### 3. 水面面積算出（SAR閾値法）

- Sentinel-1 VVバンドの後方散乱係数で水域を判別
- 水面は後方散乱が低い（通常 **-16 dB 以下** を閾値として使用）
- 各池ポリゴン内の水面ピクセル数 × ピクセル解像度（10m × 10m）= 水面面積（㎡）

```python
water_mask = image.select('VV').lt(-16)  # 閾値は現地検証で調整
water_area = water_mask.multiply(ee.Image.pixelArea())
```

### 4. データ保存形式（CSV）

```csv
date,pond_id,pond_name,region,water_area_m2,satellite,orbit
2026-01-15,001,○○池,山香町,12345.6,Sentinel-1A,DESCENDING
```

### 5. 時系列グラフ

- 過去3年間 + 最新データの折れ線グラフ
- X軸: 撮影日、Y軸: 水面面積（㎡）または推定水位（m）
- `plotly` でインタラクティブグラフ生成 → HTMLに埋め込み

### 6. HTMLインターフェース

- **Leaflet.js** で杵築市の地図を表示
- 池ポリゴンをクリック → 対象池の時系列グラフを表示
- `docs/index.html` → GitHub Pages でホスティング可能

## GitHub Actions スケジュール

```yaml
# .github/workflows/update_water_area.yml
on:
  schedule:
    - cron: '0 3 * * 1,4'  # 月・木 (Sentinel-1降交の概ねの周期)
  workflow_dispatch:        # 手動実行も可能
```

Sentinel-1の降交軌道データが追加されるたびに：
1. GEEから最新データ取得・解析
2. CSV更新
3. `docs/data.json` 更新
4. GitHub Pages へデプロイ

## 必要な事前設定

1. **GEEサービスアカウント作成**
   - [Google Cloud Console](https://console.cloud.google.com/) でサービスアカウント作成
   - Earth Engine API を有効化
   - GEEプロジェクト `kitsuki-kato` にサービスアカウントを追加

2. **GitHub Secrets 設定**
   - `GEE_SERVICE_ACCOUNT_KEY`: サービスアカウントJSONの内容

3. **GitHub Pages 有効化**
   - Settings → Pages → Source: `docs/` フォルダを指定

4. **池リストCSV配置**
   - `杵築池リスト名前入り.csv` をリポジトリルートに配置
   - 必須カラム: `id`（ポリゴンID）、`name`（池名）、`region`（地域名）

## 注意事項

- Sentinel-1の降交軌道データのみ使用（過去データとの一貫性のため）
- モザイク処理は同日・同軌道の画像を対象とする
- SAR閾値（-16 dB）は現地の実測データと照合して調整が必要
- GEE の無料枠制限に注意（大量のエクスポートは有料プランが必要な場合あり）
- 池ポリゴンの `id` フィールド名はGEEアセットの実際のフィールド名に合わせること

## ローカル開発環境セットアップ

```bash
pip install -r requirements.txt
earthengine authenticate
python scripts/fetch_sentinel1.py --date 2026-03-01
```
